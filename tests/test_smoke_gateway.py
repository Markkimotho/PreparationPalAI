import json

import httpx
import pytest

from scripts.smoke_gateway import main, run

RealClient = httpx.Client  # main() is patched to build clients through the mock transport


def transport(health=True, models=None, quiz_status=200, stream_error=False):
    models = ['open-default'] if models is None else models

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == '/api/health':
            return httpx.Response(200, json={'online': health, 'model_count': len(models)})
        if path == '/api/models':
            return httpx.Response(200, json={'supported': models, 'installed': models, 'catalogue': [{'id': m} for m in models]})
        if path == '/api/quiz/generate':
            return httpx.Response(quiz_status, json=[{'question': 'q'}, {'question': 'q2'}] if quiz_status == 200 else {'detail': 'nope'})
        if path == '/api/chat/stream':
            frames = [{'type': 'token', 'text': 'Force'}, {'type': 'error', 'message': 'boom'} if stream_error else {'type': 'token', 'text': ' = ma'}, {'type': 'done'}]
            return httpx.Response(200, text=''.join(f'data: {json.dumps(f)}\n\n' for f in frames))
        return httpx.Response(404)

    return RealClient(transport=httpx.MockTransport(handler), base_url='http://app')


def test_all_checks_pass():
    results = run(transport())
    assert [r.name for r in results] == ['health', 'models', 'quiz', 'chat']
    assert all(r.ok for r in results)


@pytest.mark.parametrize('kwargs,failing', [
    (dict(health=False), 'health'),
    (dict(models=[]), 'models'),
    (dict(quiz_status=503), 'quiz'),
    (dict(stream_error=True), 'chat'),
])
def test_each_failure_is_named(kwargs, failing):
    failed = [r.name for r in run(transport(**kwargs)) if not r.ok]
    assert failing in failed


def test_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr('scripts.smoke_gateway.httpx.Client', lambda **kw: transport())
    assert main(['http://app']) == 0
    monkeypatch.setattr('scripts.smoke_gateway.httpx.Client', lambda **kw: transport(health=False))
    assert main(['http://app']) == 1
    assert 'FAIL health' in capsys.readouterr().out
