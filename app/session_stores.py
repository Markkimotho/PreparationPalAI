"""Stores for coach sessions and drawing submissions: SQLite files (self-hosted) or Postgres (hosted).

Callers get one object per `connect()` and never see SQL. `for_update=True` takes a write lock so a
read-check-write sequence (recording an answer, appending a review) cannot interleave with another.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app import db as pg
from app.workspace import workspace_id


# ---- SQLite (one file per workspace) ---------------------------------------------------------

class SqliteSessions:
    def __init__(self, conn):
        self.conn = conn

    def _lock(self):
        if not self.conn.in_transaction:
            self.conn.execute('BEGIN IMMEDIATE')

    def get(self, session_id: str, learner: str, for_update: bool = False) -> dict | None:
        if for_update:
            self._lock()
        row = self.conn.execute('SELECT body FROM sessions WHERE id=? AND learner=?', (session_id, learner)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, session: dict) -> None:
        self.conn.execute('INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)', (session['id'], session['learner'], json.dumps(session)))

    def recent(self, learner: str, limit: int = 30) -> list[dict]:
        return [json.loads(r[0]) for r in self.conn.execute('SELECT body FROM sessions WHERE learner=? ORDER BY rowid DESC LIMIT ?', (learner, limit))]

    def all_for(self, learner: str) -> list[dict]:
        return [json.loads(r[0]) for r in self.conn.execute('SELECT body FROM sessions WHERE learner=?', (learner,))]


class SqliteDrawings:
    def __init__(self, conn):
        self.conn = conn

    def _lock(self):
        if not self.conn.in_transaction:
            self.conn.execute('BEGIN IMMEDIATE')

    def get(self, drawing_id: str, for_update: bool = False) -> dict | None:
        if for_update:
            self._lock()
        row = self.conn.execute('SELECT * FROM drawings WHERE id=?', (drawing_id,)).fetchone()
        return None if row is None else dict(owner=row['owner'], image=bytes(row['image']), body=json.loads(row['body']))

    def insert(self, drawing_id: str, owner: str, body: dict, image: bytes) -> None:
        self.conn.execute('INSERT INTO drawings VALUES (?, ?, ?, ?)', (drawing_id, owner, json.dumps(body), image))

    def update_body(self, drawing_id: str, body: dict) -> None:
        self.conn.execute('UPDATE drawings SET body=? WHERE id=?', (json.dumps(body), drawing_id))

    def page(self, owner: str | None, before: int | None, limit: int) -> list[tuple[int, dict]]:
        clauses, params = [], []
        if owner is not None:
            clauses.append('owner=?'); params.append(owner)
        if before is not None:
            clauses.append('rowid<?'); params.append(before)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = self.conn.execute('SELECT rowid AS cursor, body FROM drawings' + where + ' ORDER BY rowid DESC LIMIT ?', [*params, limit]).fetchall()
        return [(r['cursor'], json.loads(r['body'])) for r in rows]


def sqlite_sessions(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, learner TEXT, body TEXT)')
    return conn


def sqlite_drawings(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE IF NOT EXISTS drawings (id TEXT PRIMARY KEY, owner TEXT NOT NULL, body TEXT NOT NULL, image BLOB NOT NULL)')
    return conn


@contextmanager
def open_sqlite(opener, path: Path, wrapper):
    conn = opener(path)
    try:
        with conn:
            yield wrapper(conn)
    finally:
        conn.close()


# ---- Postgres (shared tables, every query filtered by workspace) --------------------------------

class PgSessions:
    def __init__(self, conn):
        self.conn = conn

    def get(self, session_id: str, learner: str, for_update: bool = False) -> dict | None:
        row = self.conn.execute('SELECT body FROM app.coach_sessions WHERE workspace=%s AND id=%s AND learner=%s' + (' FOR UPDATE' if for_update else ''),
                                (workspace_id.get(), session_id, learner)).fetchone()
        return row['body'] if row else None

    def put(self, session: dict) -> None:
        self.conn.execute(
            'INSERT INTO app.coach_sessions (workspace, id, learner, body) VALUES (%s, %s, %s, %s::jsonb) '
            "ON CONFLICT (workspace, id) DO UPDATE SET learner = EXCLUDED.learner, body = EXCLUDED.body, "
            "seq = nextval(pg_get_serial_sequence('app.coach_sessions', 'seq'))",
            (workspace_id.get(), session['id'], session['learner'], json.dumps(session)))

    def recent(self, learner: str, limit: int = 30) -> list[dict]:
        return [r['body'] for r in self.conn.execute('SELECT body FROM app.coach_sessions WHERE workspace=%s AND learner=%s ORDER BY seq DESC LIMIT %s',
                                                     (workspace_id.get(), learner, limit))]

    def all_for(self, learner: str) -> list[dict]:
        return [r['body'] for r in self.conn.execute('SELECT body FROM app.coach_sessions WHERE workspace=%s AND learner=%s', (workspace_id.get(), learner))]


class PgDrawings:
    def __init__(self, conn):
        self.conn = conn

    def get(self, drawing_id: str, for_update: bool = False) -> dict | None:
        row = self.conn.execute('SELECT owner, body, image FROM app.drawings WHERE workspace=%s AND id=%s' + (' FOR UPDATE' if for_update else ''),
                                (workspace_id.get(), drawing_id)).fetchone()
        return None if row is None else dict(owner=row['owner'], image=bytes(row['image']), body=row['body'])

    def insert(self, drawing_id: str, owner: str, body: dict, image: bytes) -> None:
        self.conn.execute('INSERT INTO app.drawings (workspace, id, owner, body, image) VALUES (%s, %s, %s, %s::jsonb, %s)',
                          (workspace_id.get(), drawing_id, owner, json.dumps(body), image))

    def update_body(self, drawing_id: str, body: dict) -> None:
        self.conn.execute('UPDATE app.drawings SET body=%s::jsonb WHERE workspace=%s AND id=%s', (json.dumps(body), workspace_id.get(), drawing_id))

    def page(self, owner: str | None, before: int | None, limit: int) -> list[tuple[int, dict]]:
        clauses, params = ['workspace=%s'], [workspace_id.get()]
        if owner is not None:
            clauses.append('owner=%s'); params.append(owner)
        if before is not None:
            clauses.append('seq<%s'); params.append(before)
        rows = self.conn.execute('SELECT seq, body FROM app.drawings WHERE ' + ' AND '.join(clauses) + ' ORDER BY seq DESC LIMIT %s', [*params, limit]).fetchall()
        return [(r['seq'], r['body']) for r in rows]


@contextmanager
def open_postgres(wrapper):
    with pg.transaction() as conn:
        yield wrapper(conn)
