from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.config import get_base_settings
from app.limits import consume
from app.llm import ChatOllama
from app.workspace import identity_id
from fastapi.testclient import TestClient
from app.api import app


def test_budgets_are_durable_and_per_identity(monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'requests_per_minute', 1)
    consume()
    with pytest.raises(HTTPException) as error:
        consume()
    assert error.value.status_code == 429
    token = identity_id.set('other')
    try:
        consume()
    finally:
        identity_id.reset(token)


def test_inference_is_bounded():
    with patch('app.llm._ChatOllama') as llm:
        ChatOllama(model='test', num_ctx=999999, num_predict=999999)
    assert llm.call_args.kwargs['num_ctx'] == get_base_settings().llm_context_tokens
    assert llm.call_args.kwargs['num_predict'] == get_base_settings().llm_output_tokens
    assert llm.call_args.kwargs['client_kwargs']['timeout'].read == get_base_settings().llm_timeout


def test_oversized_body_rejected_before_inference(monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'request_max_bytes', 1024)
    r = TestClient(app).post('/api/chat/stream', json={'question': 'x' * 2000})
    assert r.status_code == 413
