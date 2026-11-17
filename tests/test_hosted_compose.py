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


def test_billing_stack_is_private_and_requires_its_secrets():
    for name in ('billing', 'billing-db', 'billing-jobs'):
        service = COMPOSE['services'][name]
        assert 'ports' not in service and 'mem_limit' in service
    for name in ('billing', 'billing-jobs'):
        assert any('BILLING_DATABASE_URL' in e and '${BILLING_DB_PASSWORD:?' in e for e in COMPOSE['services'][name]['environment'])
    assert any(e.startswith('BILLING_SERVICE_TOKEN=${BILLING_SERVICE_TOKEN:?') for e in COMPOSE['services']['billing']['environment'])
    assert COMPOSE['services']['billing-jobs']['command'] == ['python', '-m', 'billing.scheduler']
    assert any(e.startswith('GATEWAY_ADMIN_KEY=${GATEWAY_ADMIN_KEY:?') for e in COMPOSE['services']['billing-jobs']['environment'])


def test_app_and_worker_bill_through_the_internal_service():
    for service in ('web', 'worker'):
        values = env(service)
        assert values['BILLING_ENABLED'] == 'true' and values['BILLING_BASE_URL'] == 'http://billing:8100'
        assert values['BILLING_SERVICE_TOKEN'].startswith('${BILLING_SERVICE_TOKEN:?')
    assert 'usage_data:/app/data/usage' in COMPOSE['services']['worker']['volumes']      # the settle outbox must survive restarts
    assert 'billing_pg' in COMPOSE['volumes']
