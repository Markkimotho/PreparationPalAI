"""Storage for the ingestion queue: SQLite files (self-hosted) or Postgres (hosted).

Both stores expose the same methods and return rows as plain dicts with `result` already
parsed and `payload` as a JSON string, so `app/jobs.py` does not care which one it uses.
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from app import db
from app.config import get_base_settings

MAX_ATTEMPTS = 3
INTERRUPTED = 'Worker interrupted repeatedly; retry manually'


class SqliteStore:
    @contextmanager
    def database(self):
        path = Path(get_base_settings().jobs_dir)
        path.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path / 'jobs.sqlite3', timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, workspace TEXT, owner TEXT, kind TEXT, payload TEXT,
                    state TEXT, attempts INTEGER, lease REAL, updated REAL, result TEXT, error TEXT)''')
                conn.execute('CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, heartbeat REAL)')
                if 'run_token' not in {r['name'] for r in conn.execute('PRAGMA table_info(jobs)')}:
                    conn.execute("ALTER TABLE jobs ADD COLUMN run_token TEXT DEFAULT ''")
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _row(row) -> dict:
        data = dict(row)
        data['result'] = json.loads(data['result'] or '{}')
        return data

    def count_open(self, workspace: str) -> int:
        with self.database() as conn:
            return conn.execute("SELECT count(*) FROM jobs WHERE workspace=? AND state IN ('pending','running')", (workspace,)).fetchone()[0]

    def insert(self, job_id, workspace, owner, kind, payload: dict) -> None:
        with self.database() as conn:
            conn.execute('INSERT INTO jobs (id,workspace,owner,kind,payload,state,attempts,lease,updated,result,error) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                         (job_id, workspace, owner, kind, json.dumps(payload), 'pending', 0, 0, time.time(), '{}', ''))

    def list(self, workspace: str, limit: int = 30) -> list[dict]:
        with self.database() as conn:
            return [self._row(r) for r in conn.execute('SELECT * FROM jobs WHERE workspace=? ORDER BY updated DESC LIMIT ?', (workspace, limit))]

    def get(self, workspace: str, job_id: str) -> dict | None:
        with self.database() as conn:
            row = conn.execute('SELECT * FROM jobs WHERE id=? AND workspace=?', (job_id, workspace)).fetchone()
            return self._row(row) if row else None

    def retry(self, workspace: str, job_id: str) -> bool:
        with self.database() as conn:
            return bool(conn.execute("UPDATE jobs SET state='pending', attempts=0, error='', updated=? WHERE id=? AND workspace=? AND state='failed'",
                                     (time.time(), job_id, workspace)).rowcount)

    def claim(self, lease_seconds: float) -> dict | None:
        with self.database() as conn:
            conn.execute('BEGIN IMMEDIATE')
            now = time.time()
            conn.execute("UPDATE jobs SET state='failed', error=? WHERE state='running' AND lease<? AND attempts>=?", (INTERRUPTED, now, MAX_ATTEMPTS))
            row = conn.execute("SELECT * FROM jobs WHERE (state='pending' OR (state='running' AND lease<?)) AND attempts<? ORDER BY updated LIMIT 1",
                               (now, MAX_ATTEMPTS)).fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            conn.execute("UPDATE jobs SET state='running', attempts=attempts+1, lease=?, updated=?, run_token=? WHERE id=?",
                         (now + lease_seconds, now, token, row['id']))
            fresh = conn.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone()
            return self._row(fresh)

    def heartbeat(self, worker_id: str, job_id=None, run_token=None, lease_seconds: float = 0) -> dict:
        now = time.time()
        with self.database() as conn:
            conn.execute('INSERT OR REPLACE INTO workers VALUES (?,?)', (worker_id, now))
            if job_id:
                conn.execute("UPDATE jobs SET lease=? WHERE id=? AND state='running' AND run_token=?", (now + lease_seconds, job_id, run_token))
            return dict(conn.execute('SELECT state, count(*) FROM jobs GROUP BY state').fetchall())

    def complete(self, job_id, run_token, result: dict, now: float) -> None:
        with self.database() as conn:
            conn.execute("UPDATE jobs SET state='completed', result=?, updated=?, lease=0 WHERE id=? AND run_token=?",
                         (json.dumps(result), now, job_id, run_token))

    def fail(self, job_id, run_token, message: str, now: float) -> None:
        with self.database() as conn:
            conn.execute("UPDATE jobs SET state='failed', error=?, updated=?, lease=0 WHERE id=? AND run_token=?", (message, now, job_id, run_token))

    def status(self) -> tuple[dict, float]:
        with self.database() as conn:
            counts = dict(conn.execute('SELECT state, count(*) FROM jobs GROUP BY state').fetchall())
            last = conn.execute('SELECT COALESCE(MAX(heartbeat),0) FROM workers').fetchone()[0]
        return counts, last

    def purge(self, workspace: str) -> int:
        with self.database() as conn:
            return conn.execute('DELETE FROM jobs WHERE workspace = ?', (workspace,)).rowcount

    def expire_lease(self, job_id: str) -> None:                    # test hook: pretend the worker died
        with self.database() as conn:
            conn.execute('UPDATE jobs SET lease = 0 WHERE id = ?', (job_id,))


class PgStore:
    @staticmethod
    def _row(row) -> dict:
        data = dict(row)
        data['result'] = data['result'] or {}
        data['payload'] = json.dumps(data['payload'])
        return data

    def count_open(self, workspace: str) -> int:
        with db.transaction() as conn:
            return conn.execute("SELECT count(*) AS n FROM app.ingestion_jobs WHERE workspace=%s AND state IN ('pending','running')", (workspace,)).fetchone()['n']

    def insert(self, job_id, workspace, owner, kind, payload: dict) -> None:
        with db.transaction() as conn:
            conn.execute('INSERT INTO app.ingestion_jobs (workspace,id,owner,kind,payload,state,attempts,lease,updated,result,error) '
                         "VALUES (%s,%s,%s,%s,%s::jsonb,'pending',0,0,%s,'{}'::jsonb,'')", (workspace, job_id, owner, kind, json.dumps(payload), time.time()))

    def list(self, workspace: str, limit: int = 30) -> list[dict]:
        with db.transaction() as conn:
            return [self._row(r) for r in conn.execute('SELECT * FROM app.ingestion_jobs WHERE workspace=%s ORDER BY updated DESC LIMIT %s', (workspace, limit))]

    def get(self, workspace: str, job_id: str) -> dict | None:
        with db.transaction() as conn:
            row = conn.execute('SELECT * FROM app.ingestion_jobs WHERE workspace=%s AND id=%s', (workspace, job_id)).fetchone()
            return self._row(row) if row else None

    def retry(self, workspace: str, job_id: str) -> bool:
        with db.transaction() as conn:
            return bool(conn.execute("UPDATE app.ingestion_jobs SET state='pending', attempts=0, error='', updated=%s WHERE workspace=%s AND id=%s AND state='failed'",
                                     (time.time(), workspace, job_id)).rowcount)

    def claim(self, lease_seconds: float) -> dict | None:
        now = time.time()
        with db.transaction() as conn:
            conn.execute("UPDATE app.ingestion_jobs SET state='failed', error=%s WHERE state='running' AND lease<%s AND attempts>=%s", (INTERRUPTED, now, MAX_ATTEMPTS))
            row = conn.execute(
                'WITH picked AS (SELECT workspace, id FROM app.ingestion_jobs '
                "WHERE (state='pending' OR (state='running' AND lease<%s)) AND attempts<%s ORDER BY updated LIMIT 1 FOR UPDATE SKIP LOCKED) "
                "UPDATE app.ingestion_jobs j SET state='running', attempts=attempts+1, lease=%s, updated=%s, run_token=%s "
                'FROM picked WHERE j.workspace=picked.workspace AND j.id=picked.id RETURNING j.*',
                (now, MAX_ATTEMPTS, now + lease_seconds, now, uuid.uuid4().hex)).fetchone()
            return self._row(row) if row else None

    def heartbeat(self, worker_id: str, job_id=None, run_token=None, lease_seconds: float = 0) -> dict:
        now = time.time()
        with db.transaction() as conn:
            conn.execute('INSERT INTO app.workers (id, heartbeat) VALUES (%s,%s) ON CONFLICT (id) DO UPDATE SET heartbeat = EXCLUDED.heartbeat', (worker_id, now))
            if job_id:
                conn.execute("UPDATE app.ingestion_jobs SET lease=%s WHERE id=%s AND state='running' AND run_token=%s", (now + lease_seconds, job_id, run_token))
            return {r['state']: r['n'] for r in conn.execute('SELECT state, count(*) AS n FROM app.ingestion_jobs GROUP BY state')}

    def complete(self, job_id, run_token, result: dict, now: float) -> None:
        with db.transaction() as conn:
            conn.execute("UPDATE app.ingestion_jobs SET state='completed', result=%s::jsonb, updated=%s, lease=0 WHERE id=%s AND run_token=%s",
                         (json.dumps(result), now, job_id, run_token))

    def fail(self, job_id, run_token, message: str, now: float) -> None:
        with db.transaction() as conn:
            conn.execute("UPDATE app.ingestion_jobs SET state='failed', error=%s, updated=%s, lease=0 WHERE id=%s AND run_token=%s", (message, now, job_id, run_token))

    def status(self) -> tuple[dict, float]:
        with db.transaction() as conn:
            counts = {r['state']: r['n'] for r in conn.execute('SELECT state, count(*) AS n FROM app.ingestion_jobs GROUP BY state')}
            last = conn.execute('SELECT COALESCE(MAX(heartbeat),0) AS h FROM app.workers').fetchone()['h']
        return counts, last

    def purge(self, workspace: str) -> int:
        with db.transaction() as conn:
            return conn.execute('DELETE FROM app.ingestion_jobs WHERE workspace = %s', (workspace,)).rowcount

    def expire_lease(self, job_id: str) -> None:
        with db.transaction() as conn:
            conn.execute('UPDATE app.ingestion_jobs SET lease = 0 WHERE id = %s', (job_id,))


def get_store():
    return PgStore() if db.enabled() else SqliteStore()
