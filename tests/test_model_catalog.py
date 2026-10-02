from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.config import get_settings
from app.model_catalog import catalogue, require_model

client = TestClient(app)


def test_catalogue_merges_installed_and_configured():
    items = catalogue({'custom:local', 'mistral:latest'})
    by_id = {m['id']: m for m in items}
    assert by_id['custom:local']['installed']
    assert by_id['custom:local']['tools'] is None
    assert by_id['mistral']['installed']
    assert get_settings().glm_model in by_id
    assert get_settings().deepseek_model in by_id


@pytest.mark.parametrize('model', ['glm4:9b', 'deepseek-r1:7b'])
@pytest.mark.parametrize('route,body,target', [
    ('/api/chat/stream', {'question': 'hi'}, 'app.api.lcel_chain.stream'),
    ('/api/code-chat/stream', {'message': 'hi'}, 'app.api.code_assistant.stream_code_assistant'),
    ('/api/agent/stream', {'message': 'hi'}, 'app.api.quiz_agent.stream_agent'),
    ('/api/quiz/generate', {'topic': 'physics'}, 'app.api.generate_questions'),
    ('/api/flashcards/generate', {'topic': 'physics'}, 'app.api.fc.generate_deck'),
])
def test_exact_model_reaches_each_engine(model, route, body, target):
    value = dict(id='d', name='Physics', cards=[]) if 'flashcards' in route else []
    with patch('app.model_catalog.get_installed_models', return_value={model}), \
         patch(target, return_value=value) as engine:
        r = client.post(route, json={**body, 'model': model})
    assert r.status_code == 200, r.text
    assert engine.call_args.kwargs.get('model') == model


def test_missing_model_preflight():
    with patch('app.model_catalog.get_installed_models', return_value=set()), \
         patch('app.api.lcel_chain.stream') as engine:
        r = client.post('/api/chat/stream', json=dict(question='hi', model='missing:7b'))
    assert r.status_code == 409
    assert 'Pull' in r.json()['detail']
    engine.assert_not_called()


def test_latest_alias():
    with patch('app.model_catalog.get_installed_models', return_value={'mistral:latest'}):
        assert require_model('mistral') == 'mistral'
