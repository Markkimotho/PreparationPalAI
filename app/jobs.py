"""SQLite ingestion queue with leases, heartbeats and workspace-scoped access."""
import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from prometheus_client import Gauge, Counter

from app.config import get_base_settings
from app.workspace import workspace_id, identity_id, request_id
from app.upload_safety import validate_upload

router = APIRouter(prefix='/api/kb/jobs', tags=['Ingestion jobs'])
BACKLOG = Gauge('preparationpalai_ingestion_jobs', 'Ingestion jobs by state', ['state'])
WORKER_HEARTBEAT = Gauge('preparationpalai_worker_heartbeat_timestamp', 'Worker heartbeat timestamp')
JOB_RESULTS = Counter('preparationpalai_ingestion_results_total', 'Ingestion outcomes', ['status'])


@contextmanager
def database():
    path = Path(get_base_settings().jobs_dir)
    path.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path / 'jobs.sqlite3', timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, workspace TEXT, owner TEXT, kind TEXT, payload TEXT,
                state TEXT, attempts INTEGER, lease REAL, updated REAL, result TEXT, error TEXT)''')
            db.execute('CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, heartbeat REAL)')
            if 'run_token' not in {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}:
                db.execute("ALTER TABLE jobs ADD COLUMN run_token TEXT DEFAULT ''")
            yield db
    finally:
        db.close()


def enqueue(kind, payload):
    job_id = uuid.uuid4().hex
    with database() as db:
        count = db.execute("SELECT count(*) FROM jobs WHERE workspace=? AND state IN ('pending','running')", (workspace_id.get(),)).fetchone()[0]
        if count >= 20:
            raise HTTPException(429, 'Workspace ingestion queue is full; retry later.')
        db.execute('INSERT INTO jobs (id,workspace,owner,kind,payload,state,attempts,lease,updated,result,error) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (job_id, workspace_id.get(), identity_id.get(), kind, json.dumps(payload),
                    'pending', 0, 0, time.time(), '{}', ''))
    return dict(id=job_id, state='pending')


def snapshot(row):
    return dict(id=row['id'], state=row['state'], attempts=row['attempts'],
                result=json.loads(row['result']), error=row['error'])


@router.get('')
def list_jobs():
    with database() as db:
        return {'jobs': [snapshot(r) for r in db.execute(
            'SELECT * FROM jobs WHERE workspace=? ORDER BY updated DESC LIMIT 30', (workspace_id.get(),))]}


@router.get('/{job_id}')
def get_job(job_id: str):
    with database() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=? AND workspace=?', (job_id, workspace_id.get())).fetchone()
        if not row:
            raise HTTPException(404, 'Job not found')
        return snapshot(row)


@router.post('/{job_id}/retry')
def retry_job(job_id: str):
    with database() as db:
        changed = db.execute("UPDATE jobs SET state='pending', attempts=0, error='', updated=? WHERE id=? AND workspace=? AND state='failed'",
                             (time.time(), job_id, workspace_id.get())).rowcount
        if not changed:
            raise HTTPException(409, 'No failed job available to retry in this workspace')
    return get_job(job_id)


@router.post('/upload', status_code=202)
async def upload_jobs(files: list[UploadFile] = File(...)):
    settings = get_base_settings()
    if len(files) > settings.upload_max_files:
        raise HTTPException(413, 'Too many files')
    queued = []
    for file in files:
        name = Path((file.filename or 'file').replace('\\', '/')).name
        data = await file.read(settings.upload_max_bytes + 1)
        try:
            validate_upload(data, name, file.content_type or 'application/octet-stream')
        except ValueError:
            raise HTTPException(415, 'Upload violates file type, signature or size limits') from None
        folder = Path(settings.jobs_dir) / 'files' / workspace_id.get()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (uuid.uuid4().hex + Path(name).suffix.lower())
        path.write_bytes(data)
        try:
            queued.append(enqueue('file', dict(path=str(path.resolve()), source=name)))
        except Exception:
            path.unlink(missing_ok=True)
            raise
    return {'jobs': queued}


@router.post('/scrape', status_code=202)
def scrape_job(body: dict):
    topic = body.get('topic', '')
    if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 500:
        raise HTTPException(422, 'A topic of 1–500 characters is required')
    return {'jobs': [enqueue('scrape', dict(topic=topic.strip(), num_results=3))]}


def claim():
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        now = time.time()
        db.execute("UPDATE jobs SET state='failed', error='Worker interrupted repeatedly; retry manually' WHERE state='running' AND lease<? AND attempts>=3", (now,))
        row = db.execute("SELECT * FROM jobs WHERE (state='pending' OR (state='running' AND lease<?)) AND attempts<3 ORDER BY updated LIMIT 1", (now,)).fetchone()
        if not row:
            return None
        run_token = uuid.uuid4().hex
        db.execute("UPDATE jobs SET state='running', attempts=attempts+1, lease=?, updated=?, run_token=? WHERE id=?",
                   (now + get_base_settings().job_lease_seconds, now, run_token, row['id']))
        return {**dict(row), 'run_token': run_token}


def heartbeat(worker_id, job_id=None, run_token=None):
    now = time.time()
    with database() as db:
        db.execute('INSERT OR REPLACE INTO workers VALUES (?,?)', (worker_id, now))
        if job_id:
            db.execute('UPDATE jobs SET lease=? WHERE id=? AND state=\'running\' AND run_token=?',
                (now + get_base_settings().job_lease_seconds, job_id, run_token))
        counts = dict(db.execute('SELECT state, count(*) FROM jobs GROUP BY state').fetchall())
    WORKER_HEARTBEAT.set(now)
    for state in ('pending', 'running', 'failed', 'completed'):
        BACKLOG.labels(state).set(counts.get(state, 0))


def run_once(worker_id='embedded'):
    heartbeat(worker_id)
    job = claim()
    if not job:
        return False
    stop = threading.Event()
    def renew():
        while not stop.wait(10):
            heartbeat(worker_id, job['id'], job['run_token'])
    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    token = workspace_id.set(job['workspace'])
    rtoken = request_id.set(job['id'])
    try:
        from app.extraction import extract
        from app.scraper import search_and_scrape
        from app.vectorstore import ingest_documents
        payload = json.loads(job['payload'])
        docs = extract(payload['path'], source_name=payload['source']) if job['kind'] == 'file' else search_and_scrape(**payload)
        if not docs:
            raise ValueError('No readable content')
        added = ingest_documents(docs)
        with database() as db:
            db.execute("UPDATE jobs SET state='completed', result=?, updated=?, lease=0 WHERE id=? AND run_token=?",
                       (json.dumps(dict(chunks_added=added)), time.time(), job['id'], job['run_token']))
        JOB_RESULTS.labels('success').inc()
    except Exception:
        # Raw parser/provider exceptions can contain private document fragments.
        with database() as db:
            db.execute("UPDATE jobs SET state='failed', error='Ingestion failed. Check readiness or retry with another file.', updated=?, lease=0 WHERE id=? AND run_token=?",
                       (time.time(), job['id'], job['run_token']))
        JOB_RESULTS.labels('error').inc()
        logging.getLogger('app.jobs').exception('ingestion_failed')
    finally:
        workspace_id.reset(token)
        request_id.reset(rtoken)
        stop.set()
        thread.join(timeout=1)
    return True


def queue_status():
    with database() as db:
        counts = dict(db.execute('SELECT state, count(*) FROM jobs GROUP BY state').fetchall())
        last = db.execute('SELECT COALESCE(MAX(heartbeat),0) FROM workers').fetchone()[0]
    for state in ('pending', 'running', 'failed', 'completed'):
        BACKLOG.labels(state).set(counts.get(state, 0))
    WORKER_HEARTBEAT.set(last)
    return {'worker': last > time.time() - 45, 'pending': counts.get('pending', 0), 'running': counts.get('running', 0)}


def worker_loop(stop):
    worker = uuid.uuid4().hex
    while not stop.is_set():
        try:
            if not run_once(worker):
                stop.wait(2)
        except Exception:
            logging.getLogger('app.jobs').exception('worker_failed')
            stop.wait(5)


if __name__ == '__main__':
    import signal
    from app.diagnostics import configure_logging
    configure_logging()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    worker_loop(stopped)
