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


# ---- accounts, storage and the public edge ------------------------------------------------

def test_third_party_images_carry_an_explicit_version():
    for name, service in COMPOSE['services'].items():
        if 'image' in service:
            assert ':' in service['image'] and not service['image'].endswith(':latest'), f"{name}: {service['image']}"
    assert COMPOSE['services']['logto']['image'] == 'svhd/logto:1.46.0'
    assert COMPOSE['services']['app-db']['image'] == 'pgvector/pgvector:0.8.7-pg16'


def test_only_the_proxy_faces_the_internet():
    for name, service in COMPOSE['services'].items():
        for port in service.get('ports', []):
            published = str(port)
            if name == 'proxy':
                assert published in ('80:80', '443:443'), published
            else:
                assert published.startswith('127.0.0.1:'), f'{name} publishes {published}'
    assert not any(str(p).startswith(('3001', '127.0.0.1:3001')) for p in COMPOSE['services']['logto'].get('ports', []))   # sign-in is only reachable through the proxy


def test_web_and_worker_use_postgres_and_signed_in_learners():
    for service in ('web', 'worker'):
        values = env(service)
        assert values['STORAGE_BACKEND'] == 'postgres' and values['AUTH_MODE'] == 'oidc' and values['PRODUCTION'] == 'true'
        assert values['DATABASE_URL'].startswith('postgresql://app:${APP_DB_PASSWORD:?')
        assert values['OIDC_ISSUER'] == 'https://${AUTH_HOST:?Set the sign-in hostname}/oidc'
        assert values['OIDC_JWKS_URL'] == 'http://logto:3001/oidc/jwks'                 # keys are fetched privately, not over the internet
        assert values['OIDC_AUDIENCE'].startswith('${OIDC_AUDIENCE:?')
        assert 'AUTH_TOKENS' not in values                                              # no shared static keys in hosted mode


def test_the_app_migrates_its_database_before_serving():
    web, worker = COMPOSE['services']['web']['command'], COMPOSE['services']['worker']['command']
    assert 'app.migrate_db' in web[-1] and 'uvicorn' in web[-1]
    assert 'app.migrate_db' in worker[-1] and 'app.jobs' in worker[-1]
    assert COMPOSE['services']['web']['depends_on']['app-db']['condition'] == 'service_healthy'


def test_the_sign_in_service_is_configured_for_the_public_hostname_behind_the_proxy():
    logto = env('logto')
    assert logto['TRUST_PROXY_HEADER'] == '1'
    assert logto['ENDPOINT'] == 'https://${AUTH_HOST:?Set the sign-in hostname}'
    assert logto['DB_URL'].startswith('postgres://logto:${LOGTO_DB_PASSWORD:?')
    assert COMPOSE['services']['logto']['ports'] == ['127.0.0.1:3002:3002']              # admin console: reach it through an SSH tunnel


def test_the_proxy_routes_both_hostnames_with_security_headers():
    caddy = (ROOT / 'deploy' / 'Caddyfile.hosted').read_text()
    assert '{$PUBLIC_HOST}' in caddy and '{$AUTH_HOST}' in caddy
    assert 'reverse_proxy web:8000' in caddy and 'reverse_proxy logto:3001' in caddy
    assert 'X-Content-Type-Options nosniff' in caddy and 'Strict-Transport-Security' in caddy
    proxy = COMPOSE['services']['proxy']
    assert './deploy/Caddyfile.hosted:/etc/caddy/Caddyfile:ro' in proxy['volumes']
    assert any(e.startswith('AUTH_HOST=${AUTH_HOST:?') for e in proxy['environment'])
    assert any(e.startswith('PUBLIC_HOST=${PUBLIC_HOST:?') for e in proxy['environment'])


def test_every_new_service_has_limits_and_a_restart_policy():
    for name in ('logto', 'logto-db', 'app-db', 'proxy'):
        service = COMPOSE['services'][name]
        assert 'mem_limit' in service and service.get('restart') == 'unless-stopped', name
    for name in ('logto-db', 'app-db'):
        assert 'healthcheck' in COMPOSE['services'][name] and COMPOSE['services'][name]['volumes']
