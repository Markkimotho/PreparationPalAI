import json
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.api import app
from app.jobs import enqueue, claim, database, get_job, run_once
from app.workspace import workspace_id

client = TestClient(app)


def test_durable_queue_and_workspace_access():
    job = enqueue('scrape', dict(topic='physics', num_results=1))
    assert get_job(job['id'])['state'] == 'pending'
    token = workspace_id.set('other')
    try:
        from fastapi import HTTPException
        import pytest
        with pytest.raises(HTTPException):
            get_job(job['id'])
    finally:
        workspace_id.reset(token)


def test_interrupted_lease_is_reclaimed():
    job = enqueue('scrape', dict(topic='physics', num_results=1))
    assert claim()['id'] == job['id']
    assert claim() is None
    with database() as db:
        db.execute('UPDATE jobs SET lease=? WHERE id=?', (time.time() - 1, job['id']))
    assert claim()['id'] == job['id']
    assert get_job(job['id'])['attempts'] == 2


def test_worker_completion_and_safe_failure():
    docs = [Document(page_content='A fact', metadata=dict(id='a'))]
    good = enqueue('scrape', dict(topic='physics', num_results=1))
    with patch('app.scraper.search_and_scrape', return_value=docs), patch('app.vectorstore.ingest_documents', return_value=1):
        assert run_once()
    assert get_job(good['id'])['result']['chunks_added'] == 1
    bad = enqueue('scrape', dict(topic='physics', num_results=1))
    with patch('app.scraper.search_and_scrape', side_effect=RuntimeError('private document')):
        run_once()
    result = get_job(bad['id'])
    assert result['state'] == 'failed' and 'private' not in result['error']
    assert client.post(f"/api/kb/jobs/{bad['id']}/retry").status_code == 200


def test_upload_returns_job_without_extraction():
    with patch('app.extraction.extract') as extract:
        result = client.post('/api/kb/jobs/upload', files={'files': ('notes.pdf', b'%PDF-1.4', 'application/pdf')})
    assert result.status_code == 202
    assert result.json()['jobs'][0]['state'] == 'pending'
    extract.assert_not_called()
