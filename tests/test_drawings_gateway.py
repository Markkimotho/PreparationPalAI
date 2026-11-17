import base64
import hashlib
import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.api import app
from app.config import get_base_settings
from tests.support.fake_openai import FakeOpenAI

REVIEW = '{"status": "reviewed", "observations": ["Two arrows"], "feedback": "Label them.", "improvements": []}'


@pytest.fixture
def gateway_client(tmp_path, monkeypatch):
    settings = get_base_settings()
    with FakeOpenAI() as fake:
        monkeypatch.setattr(settings, 'inference_backend', 'gateway')
        monkeypatch.setattr(settings, 'gateway_base_url', fake.url)
        monkeypatch.setattr(settings, 'gateway_api_key', SecretStr('sk-test'))
        monkeypatch.setattr(settings, 'coach_db', str(tmp_path / 'sessions.sqlite3'))
        monkeypatch.setattr(settings, 'auth_enabled', True)
        monkeypatch.setattr(settings, 'auth_tokens', {hashlib.sha256(b'admin').hexdigest(): {'workspace': 'classroom', 'role': 'admin'}})
        with TestClient(app, headers={'Authorization': 'Bearer admin'}) as client:
            yield client, fake


def submission():
    buffer = io.BytesIO()
    Image.new('RGB', (64, 64), 'white').save(buffer, 'PNG')
    return dict(question='Draw a free-body diagram for a stationary block.', explanation='Normal and weight balance.',
                image='data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(),
                scene={'elements': [{'id': 'a', 'type': 'arrow'}]})


def test_vision_models_lists_the_configured_vision_alias(gateway_client):
    client, _ = gateway_client
    assert client.get('/api/drawings/vision-models').json() == {'models': ['vision-open']}


def test_ai_review_sends_the_image_to_the_vision_alias_and_moderates_on_guard(gateway_client):
    client, fake = gateway_client
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    fake.replies = [REVIEW]
    result = client.post(f'/api/drawings/{drawing}/ai-review', json={'model': 'whatever-the-ui-saved'})
    assert result.status_code == 200, result.text
    assert result.json()['reviews'][0]['score'] is None
    vision = fake.chat_requests('vision-open')
    assert len(vision) == 2  # visual safety decision, then the review
    parts = vision[1]['messages'][-1]['content']
    assert any(p['type'] == 'image_url' and p['image_url']['url'].startswith('data:image/png;base64,') for p in parts)
    assert {r['model'] for r in fake.chat_requests()} <= {'vision-open', 'guard'}


def test_vision_unreachable_keeps_submission_and_returns_502(gateway_client):
    client, fake = gateway_client
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    fake.status = 500
    result = client.post(f'/api/drawings/{drawing}/ai-review', json={'model': 'x'})
    assert result.status_code in (502, 503)
    assert client.get('/api/drawings').json()['drawings'][0]['status'] == 'pending'


def test_text_moderation_ignores_the_requested_model_in_gateway_mode(gateway_client):
    client, fake = gateway_client
    assert client.post('/api/drawings', json=submission()).status_code == 200
    assert fake.chat_requests() and {r['model'] for r in fake.chat_requests()} == {'guard'}


def test_judge_uses_guard_alias_even_when_caller_passes_another_model(gateway_client):
    from app.safety import moderate
    _, fake = gateway_client
    moderate('hello', model='open-reasoning', base_url='http://ignored', timeout=5)
    assert {r['model'] for r in fake.chat_requests()} == {'guard'}
