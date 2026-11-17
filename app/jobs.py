"""Ingestion queue with leases, heartbeats and workspace-scoped access (SQLite files or Postgres)."""
import json
import logging
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from prometheus_client import Gauge, Counter

from app.config import get_base_settings
from app.jobs_store import SqliteStore, get_store
from app.workspace import workspace_id, identity_id, request_id
from app.upload_safety import validate_upload

router = APIRouter(prefix='/api/kb/jobs', tags=['Ingestion jobs'])
BACKLOG = Gauge('preparationpalai_ingestion_jobs', 'Ingestion jobs by state', ['state'])
WORKER_HEARTBEAT = Gauge('preparationpalai_worker_heartbeat_timestamp', 'Worker heartbeat timestamp')
JOB_RESULTS = Counter('preparationpalai_ingestion_results_total', 'Ingestion outcomes', ['status'])


def store():
    """The queue store for the configured storage backend."""
    return get_store()


def database():
    """SQLite connection context (self-hosted files). Kept for tools and tests that touch the file directly."""
    return SqliteStore().database()


def enqueue(kind, payload):
    job_id = uuid.uuid4().hex
    if store().count_open(workspace_id.get()) >= 20:
        raise HTTPException(429, 'Workspace ingestion queue is full; retry later.')
    store().insert(job_id, workspace_id.get(), identity_id.get(), kind, payload)
    return dict(id=job_id, state='pending')


def snapshot(row):
    return dict(id=row['id'], state=row['state'], attempts=row['attempts'],
                result=row['result'], error=row['error'])


@router.get('')
def list_jobs():
    return {'jobs': [snapshot(r) for r in store().list(workspace_id.get())]}


@router.get('/{job_id}')
def get_job(job_id: str):
    row = store().get(workspace_id.get(), job_id)
    if not row:
        raise HTTPException(404, 'Job not found')
    return snapshot(row)


@router.post('/{job_id}/retry')
def retry_job(job_id: str):
    if not store().retry(workspace_id.get(), job_id):
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
    return store().claim(get_base_settings().job_lease_seconds)


def heartbeat(worker_id, job_id=None, run_token=None):
    counts = store().heartbeat(worker_id, job_id, run_token, get_base_settings().job_lease_seconds)
    WORKER_HEARTBEAT.set(time.time())
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
        from app.metered import job_scope
        # The meter wraps the whole job so a learner without credits costs us no extraction work.
        with job_scope(job['workspace'], 'kb_upload' if job['kind'] == 'file' else 'kb_scrape'):
            docs = extract(payload['path'], source_name=payload['source']) if job['kind'] == 'file' else search_and_scrape(**payload)
            if not docs:
                raise ValueError('No readable content')
            added = ingest_documents(docs)
        store().complete(job['id'], job['run_token'], dict(chunks_added=added), time.time())
        JOB_RESULTS.labels('success').inc()
    except Exception as exc:
        # Raw parser/provider exceptions can contain private document fragments.
        message = exc.detail if getattr(exc, 'status_code', None) == 402 else 'Ingestion failed. Check readiness or retry with another file.'
        store().fail(job['id'], job['run_token'], message, time.time())
        JOB_RESULTS.labels('error').inc()
        logging.getLogger('app.jobs').exception('ingestion_failed')
    finally:
        workspace_id.reset(token)
        request_id.reset(rtoken)
        stop.set()
        thread.join(timeout=1)
    return True


def queue_status():
    counts, last = store().status()
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
