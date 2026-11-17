"""Gate checks for docker-compose.hosted.yml: gateway inference, no Ollama, no secrets inline."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = yaml.safe_load((ROOT / 'docker-compose.hosted.yml').read_text())


def env(service):
    raw = COMPOSE['services'][service]['environment']
    return dict(item.split('=', 1) for item in raw) if isinstance(raw, list) else raw


def test_hosted_stack_has_no_ollama():
    assert not [name for name in COMPOSE['services'] if 'ollama' in name]
    assert 'ollama_models' not in COMPOSE.get('volumes', {})


def test_web_and_worker_use_the_gateway_backend():
    for service in ('web', 'worker'):
        values = env(service)
        assert values['INFERENCE_BACKEND'] == 'gateway'
        assert values['GATEWAY_BASE_URL'] == 'http://litellm:4000'
        assert values['GATEWAY_API_KEY'].startswith('${GATEWAY_API_KEY:?')  # required, never defaulted
        assert 'ai-gateway' in COMPOSE['services'][service]['networks']


def test_gateway_network_is_external_and_web_is_only_published_on_loopback():
    assert COMPOSE['networks']['ai-gateway']['external'] is True
    for port in COMPOSE['services']['web'].get('ports', []):
        assert str(port).startswith('127.0.0.1:')
    assert 'ports' not in COMPOSE['services']['worker']


def test_no_inline_secrets():
    for service in COMPOSE['services'].values():
        for value in (service.get('environment') or []):
            key, _, setting = str(value).partition('=')
            if any(word in key for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET')):
                assert setting.startswith('${'), key


def test_services_stay_bounded_and_unprivileged():
    for name in ('web', 'worker'):
        service = COMPOSE['services'][name]
        assert service['read_only'] is True and service['cap_drop'] == ['ALL']
        assert 'mem_limit' in service and 'pids_limit' in service


def test_data_volumes_match_the_self_hosted_layout():
    assert {'chroma_data', 'jobs_data', 'coach_data', 'flashcards_data', 'usage_data'} <= set(COMPOSE['volumes'])
