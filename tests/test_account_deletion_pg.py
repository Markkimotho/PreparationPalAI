"""Account deletion on Postgres: every table is emptied for one learner and a neighbour keeps everything."""
import hashlib
import re

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app import coach, drawings, flashcards, jobs, limits, oidc, purge, vectorstore
from app.api import app
from app.config import get_base_settings
from app.pgvector_store import DIMENSIONS
from app.workspace import identity_id, workspace_id
from tests.support.fake_issuer import FakeIssuer

pytestmark = pytest.mark.usefixtures('pg')
TABLES = ['flashcard_decks', 'coach_sessions', 'drawings', 'ingestion_jobs', 'usage_events', 'chunks']
client = TestClient(app)


class Words(Embeddings):
    def vector(self, text):
        v = [0.0] * DIMENSIONS
        for w in re.findall(r'[a-z]+', text.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        return v

    def embed_documents(self, texts):
        return [self.vector(t) for t in texts]

    def embed_query(self, text):
        return self.vector(text)


@pytest.fixture(autouse=True)
def postgres_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(get_base_settings(), 'storage_backend', 'postgres')
    monkeypatch.setattr(get_base_settings(), 'jobs_dir', str(tmp_path / 'jobs'))
    monkeypatch.setattr('app.vectorstore.get_embeddings', lambda: Words())
    monkeypatch.setattr('app.pgvector_store.get_embeddings', lambda: Words())


def fill(workspace):
    tokens = workspace_id.set(workspace), identity_id.set(workspace)
    try:
        flashcards.create_deck('Private deck', [dict(front='a', back='b')])
        vectorstore.get_vectorstore().add_documents([Document(page_content='private note', metadata=dict(source='n.pdf', page=1, id='c1'))])
        with coach.connect() as db:
            coach.save(db, dict(id='s1', learner='ann', topic='t', mode='recap', answers=[], questions=[]))
        with drawings.connect() as db:
            db.insert('d1', workspace, dict(id='d1', question='q'), b'png')
        jobs.enqueue('scrape', dict(topic='x', num_results=1))
        limits.consume()
    finally:
        workspace_id.reset(tokens[0]); identity_id.reset(tokens[1])


def rows(pg, workspace):
    with pg.transaction() as conn:
        return {t: conn.execute(f'SELECT count(*) AS n FROM app.{t} WHERE workspace = %s', (workspace,)).fetchone()['n'] for t in TABLES}


def test_purge_empties_every_postgres_table_for_one_learner_only(pg):
    fill('u-alice')
    fill('u-bob')
    assert all(n >= 1 for n in rows(pg, 'u-alice').values())
    purge.purge_workspace('u-alice')
    assert rows(pg, 'u-alice') == dict.fromkeys(TABLES, 0)
    assert all(n >= 1 for n in rows(pg, 'u-bob').values())


def test_deleting_through_the_api_on_postgres(pg, monkeypatch):
    issuer = FakeIssuer()
    s = get_base_settings()
    for name, value in dict(auth_mode='oidc', auth_enabled=True, oidc_issuer=issuer.issuer, oidc_audience=issuer.audience,
                            oidc_jwks_url=issuer.jwks_url, auth_tokens={}).items():
        monkeypatch.setattr(s, name, value)
    oidc.reset_cache()
    try:
        alice, bob = oidc.workspace_for(issuer.issuer, 'alice'), oidc.workspace_for(issuer.issuer, 'bob')
        fill(alice)
        fill(bob)
        response = client.delete('/api/account', headers={'Authorization': f"Bearer {issuer.sign(sub='alice')}"})
        assert response.status_code == 204
        assert rows(pg, alice) == dict.fromkeys(TABLES, 0) and all(n >= 1 for n in rows(pg, bob).values())
    finally:
        issuer.close()
        oidc.reset_cache()


def test_every_postgres_table_has_a_purge_path(pg):
    """A new user table must come with a deleter, or this fails."""
    fill('u-check')
    purge.purge_workspace('u-check')
    assert rows(pg, 'u-check') == dict.fromkeys(TABLES, 0)
