import hashlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.config import get_base_settings, get_settings, Settings
from app.memory import add_messages, get_chat_history, clear_history
from app.workspace import workspace_id, scoped_thread

client = TestClient(app)


@pytest.fixture
def auth(monkeypatch, tmp_path):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'auth_enabled', True)
    monkeypatch.setattr(settings, 'auth_tokens', {
        hashlib.sha256(key.encode()).hexdigest(): dict(workspace=ws, role=role)
        for key, ws, role in [('alice-key', 'alice', 'editor'), ('bob-key', 'bob', 'editor'),
                              ('reader-key', 'alice', 'reader')]})
    monkeypatch.setattr(settings, 'flashcards_dir', str(tmp_path / 'cards'))
    monkeypatch.setattr(settings, 'coach_db', str(tmp_path / 'coach.sqlite3'))
    return lambda key: {'Authorization': f'Bearer {key}-key'}


def test_protected_routes_and_public_surface(auth):
    assert client.get('/api/kb/sources').status_code == 401
    assert client.get('/api/auth/status').json() == {'enabled': True}
    assert client.get('/').status_code == 200
    assert client.get('/api/auth/me', headers=auth('alice')).json()['workspace'] == 'alice'


def test_decks_cannot_cross_workspaces(auth):
    alice = client.post('/api/flashcards', headers=auth('alice'), json={'name': 'Alice only'}).json()
    assert client.get('/api/flashcards', headers=auth('bob')).json()['decks'] == []
    assert client.delete(f"/api/flashcards/{alice['id']}", headers=auth('bob')).status_code == 404
    assert client.get(f"/api/flashcards/{alice['id']}", headers=auth('alice')).status_code == 200


def test_upload_delete_permissions(auth):
    with patch('app.api.load_and_chunk_pdf', return_value=[]):
        assert client.post('/api/kb/upload', headers=auth('reader'),
            files={'files': ('notes.pdf', b'%PDF-1.4', 'application/pdf')}).status_code == 403
        assert client.post('/api/kb/upload', headers=auth('alice'),
            files={'files': ('notes.pdf', b'%PDF-1.4', 'application/pdf')}).status_code == 200
    assert client.delete('/api/kb', headers=auth('reader')).status_code == 403
    assert client.post('/api/models/pull', headers=auth('alice'), json={'model': 'x'}).status_code == 403


def test_storage_and_memory_scope():
    a = workspace_id.set('alice')
    try:
        alice_path = get_settings().chroma_persist_dir
        add_messages('same', 'alice secret', 'reply')
        assert scoped_thread('same') == 'alice:same'
        b = workspace_id.set('bob')
        try:
            assert get_settings().chroma_persist_dir != alice_path
            assert get_chat_history('same') == []
            clear_history('same')
        finally:
            workspace_id.reset(b)
        assert get_chat_history('same')[0].content == 'alice secret'
        clear_history('same')
    finally:
        workspace_id.reset(a)


def test_production_requires_auth():
    with pytest.raises(ValueError, match='PRODUCTION requires'):
        Settings(production=True, auth_enabled=False)
