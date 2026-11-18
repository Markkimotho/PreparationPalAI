import hashlib
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app import billing_client, logto, memory, metered, oidc, purge, vectorstore
from app.api import app
from app.config import get_base_settings
from app.workspace import workspace_id
from tests.support.fake_billing import FakeBilling
from tests.support.fake_issuer import FakeIssuer

A, B = 'u-aaaaaaaaaaaaaaaaaaaa', 'u-bbbbbbbbbbbbbbbbbbbb'
client = TestClient(app)


class ThreeDim(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


@pytest.fixture
def stores(tmp_path, monkeypatch):
    s = get_base_settings()
    for name, value in dict(flashcards_dir=str(tmp_path / 'cards'), chroma_persist_dir=str(tmp_path / 'vectors'),
                            coach_db=str(tmp_path / 'coach' / 'sessions.sqlite3'), jobs_dir=str(tmp_path / 'jobs'),
                            usage_db=str(tmp_path / 'usage' / 'usage.sqlite3'), profiles_dir=str(tmp_path / 'profiles')).items():
        monkeypatch.setattr(s, name, value)
    monkeypatch.setattr(vectorstore, '_vectorstore', None)
    vectorstore._workspace_stores.clear()
    with patch('app.vectorstore.get_embeddings', return_value=ThreeDim()):
        yield tmp_path
    vectorstore._workspace_stores.clear()


def fill(workspace: str) -> None:
    """Put a little data for `workspace` into every file-based store."""
    from app import code_assistant, coach, flashcards, jobs, limits, quiz_agent
    from app import profile
    token = workspace_id.set(workspace)
    try:
        profile.save(profile.LearnerProfile(display_name='Private name', onboarded=True))
        flashcards.create_deck('Private deck')
        vectorstore.get_vectorstore().add_documents([Document(page_content='private note', metadata=dict(source='n.pdf', page=1, id='x'))])
        with coach.connect():
            pass
        jobs.enqueue('scrape', dict(topic='physics', num_results=1))
        folder = Path(get_base_settings().jobs_dir) / 'files' / workspace
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'upload.pdf').write_bytes(b'%PDF-private')
        from app.workspace import identity_id
        itoken = identity_id.set(workspace)
        try:
            limits.consume()
        finally:
            identity_id.reset(itoken)
        memory.add_messages('s1', 'my question', 'my answer')
        for cp in (code_assistant._checkpointer, quiz_agent._checkpointer):
            cp.storage[f'{workspace}:thread-1'] = {}
    finally:
        workspace_id.reset(token)


def snapshot(workspace: str) -> dict:
    from app import code_assistant, flashcards, jobs, quiz_agent
    token = workspace_id.set(workspace)
    try:
        s = get_base_settings()
        with jobs.database() as db:
            job_rows = db.execute('SELECT count(*) FROM jobs WHERE workspace=?', (workspace,)).fetchone()[0]
        import sqlite3
        usage = 0
        if Path(s.usage_db).exists():
            usage = sqlite3.connect(s.usage_db).execute('SELECT count(*) FROM usage WHERE workspace=?', (workspace,)).fetchone()[0]
        return dict(
            decks=len(flashcards.list_decks()),
            vectors=vectorstore.get_vectorstore()._collection.count() if (Path(s.chroma_persist_dir) / 'workspaces' / workspace).exists() else 0,
            coach_dir=(Path(s.coach_db).parent / 'workspaces' / workspace).exists(),
            jobs=job_rows, job_files=(Path(s.jobs_dir) / 'files' / workspace).exists(), usage=usage,
            history=len(memory.get_chat_history('s1')),
            profile=(Path(s.profiles_dir) / f'{workspace}.json').exists(),
            checkpoints=sum(f'{workspace}:thread-1' in cp.storage for cp in (code_assistant._checkpointer, quiz_agent._checkpointer)))
    finally:
        workspace_id.reset(token)


FULL = dict(decks=1, vectors=1, coach_dir=True, jobs=1, job_files=True, usage=1, history=2, checkpoints=2, profile=True)
EMPTY = dict(decks=0, vectors=0, coach_dir=False, jobs=0, job_files=False, usage=0, history=0, checkpoints=0, profile=False)


def test_the_fixture_really_fills_every_store(stores):
    fill(A)
    assert snapshot(A) == FULL


def test_purge_removes_every_store_for_one_workspace_and_leaves_the_neighbour(stores):
    fill(A)
    fill(B)
    report = purge.purge_workspace(A)
    assert snapshot(A) == EMPTY
    assert snapshot(B) == FULL
    assert set(report) >= {'flashcards', 'vectors', 'coach', 'jobs', 'usage', 'chat_memory', 'profile'} and all(v >= 0 for v in report.values())


def test_purging_twice_is_harmless(stores):
    fill(A)
    purge.purge_workspace(A)
    again = purge.purge_workspace(A)
    assert snapshot(A) == EMPTY and sum(again.values()) == 0


@pytest.mark.parametrize('bad', ['local', '', '../etc', 'a/b', 'x' * 65, 'has space'])
def test_purge_refuses_unsafe_or_shared_workspaces(stores, bad):
    with pytest.raises(ValueError):
        purge.purge_workspace(bad)


def test_one_failing_store_does_not_stop_the_rest_and_is_reported(stores, monkeypatch):
    fill(A)
    monkeypatch.setitem(purge._stores, 'flashcards', lambda ws: (_ for _ in ()).throw(OSError('disk')))
    with pytest.raises(purge.PurgeIncomplete) as caught:
        purge.purge_workspace(A)
    assert caught.value.failed == ['flashcards']
    assert snapshot(A)['jobs'] == 0 and snapshot(A)['vectors'] == 0          # the others still ran


# ---- the HTTP endpoint -------------------------------------------------------------------

@pytest.fixture
def signed_in(stores, monkeypatch):
    issuer = FakeIssuer()
    s = get_base_settings()
    for name, value in dict(auth_mode='oidc', auth_enabled=True, oidc_issuer=issuer.issuer, oidc_audience=issuer.audience,
                            oidc_jwks_url=issuer.jwks_url, auth_tokens={}).items():
        monkeypatch.setattr(s, name, value)
    oidc.reset_cache()
    yield issuer
    issuer.close()
    oidc.reset_cache()


def bearer(issuer, sub):
    return {'Authorization': f'Bearer {issuer.sign(sub=sub)}'}


def test_a_learner_can_delete_their_account_and_only_theirs(signed_in):
    alice, bob = oidc.workspace_for(signed_in.issuer, 'alice'), oidc.workspace_for(signed_in.issuer, 'bob')
    fill(alice)
    fill(bob)
    assert client.delete('/api/account', headers=bearer(signed_in, 'alice')).status_code == 204
    assert snapshot(alice) == EMPTY and snapshot(bob) == FULL
    assert client.delete('/api/account', headers=bearer(signed_in, 'alice')).status_code == 204     # repeat is fine


def test_deletion_needs_a_sign_in_and_is_not_offered_for_shared_static_keys(signed_in, monkeypatch):
    assert client.delete('/api/account').status_code == 401
    monkeypatch.setattr(get_base_settings(), 'auth_mode', 'tokens')
    monkeypatch.setattr(get_base_settings(), 'auth_enabled', False)
    assert client.delete('/api/account').status_code == 403


@pytest.fixture
def billing(monkeypatch):
    fake = FakeBilling()
    monkeypatch.setattr(get_base_settings(), 'billing_enabled', True)
    monkeypatch.setattr(metered, 'get_client', lambda: billing_client.BillingClient(client=fake.client()))
    return fake


def test_billing_is_closed_before_the_data_goes(signed_in, billing):
    workspace = oidc.workspace_for(signed_in.issuer, 'alice')
    fill(workspace)
    assert client.delete('/api/account', headers=bearer(signed_in, 'alice')).status_code == 204
    assert billing.paths('/close') == [f'/v1/accounts/{workspace}/close'] and snapshot(workspace) == EMPTY


def test_if_billing_is_down_nothing_is_deleted_and_the_learner_can_retry(signed_in, billing):
    workspace = oidc.workspace_for(signed_in.issuer, 'alice')
    fill(workspace)
    billing.fail_paths = {'/close'}
    assert client.delete('/api/account', headers=bearer(signed_in, 'alice')).status_code == 503
    assert snapshot(workspace) == FULL
    billing.fail_paths = set()
    assert client.delete('/api/account', headers=bearer(signed_in, 'alice')).status_code == 204 and snapshot(workspace) == EMPTY


def test_a_closed_account_cannot_start_new_billable_work(signed_in, billing):
    billing.closed.add(oidc.workspace_for(signed_in.issuer, 'alice'))
    response = client.post('/api/chat/stream', json={'question': 'hi'}, headers=bearer(signed_in, 'alice'))
    assert response.status_code == 403 and response.json() == {'detail': 'This account has been closed.'}


# ---- removing the sign-in itself ----------------------------------------------------------

def test_the_sign_in_is_removed_last_and_a_failure_can_be_retried(signed_in, monkeypatch):
    removed, fail = [], [True]

    def delete_user(subject):
        if fail[0]:
            raise logto.LogtoError('down')
        removed.append(subject)

    monkeypatch.setattr(logto, 'configured', lambda: True)
    monkeypatch.setattr(logto, 'delete_user', delete_user)
    workspace = oidc.workspace_for(signed_in.issuer, 'alice')
    fill(workspace)
    first = client.delete('/api/account', headers=bearer(signed_in, 'alice'))
    assert first.status_code == 502 and snapshot(workspace) == EMPTY                # data is gone even though sign-in removal failed
    fail[0] = False
    assert client.delete('/api/account', headers=bearer(signed_in, 'alice')).status_code == 204
    assert removed == ['alice']


def mock_logto(calls, token_status=200, delete_status=204):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.headers.get('authorization')))
        if request.url.path == '/oidc/token':
            return httpx.Response(token_status, json={'access_token': 'mgmt-token'})
        return httpx.Response(delete_status)
    return httpx.Client(transport=httpx.MockTransport(handler), base_url='https://id.example')


@pytest.fixture
def logto_settings(monkeypatch):
    from pydantic import SecretStr
    s = get_base_settings()
    monkeypatch.setattr(s, 'logto_endpoint', 'https://id.example')
    monkeypatch.setattr(s, 'logto_management_app_id', 'mgmt-id')
    monkeypatch.setattr(s, 'logto_management_app_secret', SecretStr('mgmt-secret'))


def test_logto_deletion_gets_a_management_token_then_deletes_the_user(logto_settings):
    calls = []
    logto.delete_user('user-123', client=mock_logto(calls))
    assert calls[0][:2] == ('POST', '/oidc/token') and calls[0][2].startswith('Basic ')
    assert calls[1] == ('DELETE', '/api/users/user-123', 'Bearer mgmt-token')


def test_logto_already_deleted_is_success_and_errors_are_reported(logto_settings):
    logto.delete_user('gone', client=mock_logto([], delete_status=404))
    with pytest.raises(logto.LogtoError):
        logto.delete_user('x', client=mock_logto([], delete_status=500))
    with pytest.raises(logto.LogtoError):
        logto.delete_user('x', client=mock_logto([], token_status=401))


def test_logto_is_optional_and_subjects_are_url_safe(logto_settings, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'logto_endpoint', '')
    assert logto.configured() is False
    monkeypatch.setattr(get_base_settings(), 'logto_endpoint', 'https://id.example')
    assert logto.configured() is True
    with pytest.raises(logto.LogtoError):
        logto.delete_user('../../admin', client=mock_logto([]))
