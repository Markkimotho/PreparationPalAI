import json
import logging
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from app.api import app
from app.diagnostics import SafeFormatter

client = TestClient(app)


def test_logs_drop_content_and_exception_details():
    record = logging.LogRecord('app.scraper', logging.ERROR, '', 1,
        'secret document %s', ('private source',), None)
    assert 'secret' not in SafeFormatter().format(record)
    assert 'private source' not in SafeFormatter().format(record)


def test_request_correlation_and_liveness():
    response = client.get('/health/live')
    assert response.json() == {'alive': True}
    assert len(response.headers['x-request-id']) == 32


def test_readiness_is_explicit_when_models_unavailable():
    with patch('app.diagnostics.httpx.get', side_effect=RuntimeError), patch('app.vectorstore.get_vectorstore'):
        response = client.get('/health/ready')
    assert response.status_code == 503
    assert response.json()['dependencies']['chat_model'] is False


def test_frontend_reports_only_allowlisted_categories():
    assert client.post('/api/diagnostics/frontend', json={'kind': 'script', 'message': 'ignored secret'}).status_code == 200
    assert client.post('/api/diagnostics/frontend', json={'kind': 'secret'}).status_code == 422
