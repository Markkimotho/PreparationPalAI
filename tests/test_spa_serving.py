"""How the built web app is served: client routes, the PWA files and their caching headers."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import SPAStaticFiles


@pytest.fixture
def client(tmp_path):
    (tmp_path / 'index.html').write_text('<!doctype html><title>app</title>')
    (tmp_path / 'sw.js').write_text('self.addEventListener("fetch", () => {})')
    (tmp_path / 'sw-strategy.js').write_text('self.swStrategy = () => "network"')
    (tmp_path / 'manifest.webmanifest').write_text('{"name": "PreparationPalAI"}')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets' / 'index-abc123.js').write_text('console.log(1)')
    app = FastAPI()
    app.mount('/', SPAStaticFiles(directory=str(tmp_path), html=True), name='spa')
    return TestClient(app)


@pytest.mark.parametrize('path', ['/account', '/auth/callback?code=abc&state=xyz', '/prepare', '/flashcards/123', '/setup', '/setup?edit=1'])
def test_client_routes_load_the_app_on_reload_and_after_sign_in(client, path):
    r = client.get(path)
    assert r.status_code == 200 and '<title>app</title>' in r.text


def test_unknown_paths_are_still_404(client):
    assert client.get('/definitely-not-a-route').status_code == 404


def test_the_service_worker_is_always_revalidated_and_may_control_the_whole_site(client):
    r = client.get('/sw.js')
    assert r.headers['cache-control'] == 'no-cache' and r.headers['service-worker-allowed'] == '/'
    assert client.get('/sw-strategy.js').headers['cache-control'] == 'no-cache'


def test_the_manifest_has_the_manifest_content_type(client):
    r = client.get('/manifest.webmanifest')
    assert r.headers['content-type'].startswith('application/manifest+json')


def test_the_app_shell_is_revalidated_but_hashed_assets_are_cached_for_a_year(client):
    assert client.get('/account').headers['cache-control'] == 'no-cache'
    assert client.get('/assets/index-abc123.js').headers['cache-control'] == 'public, max-age=31536000, immutable'


def test_every_route_the_web_app_defines_is_served_on_reload():
    """Gate: a page added to frontend/src/App.tsx must also be in CLIENT_ROUTES, or reloading it 404s.
    This shipped twice (/account and /auth/callback, then /setup)."""
    import re
    from pathlib import Path
    from app.api import CLIENT_ROUTES
    app_tsx = (Path(__file__).resolve().parent.parent / 'frontend' / 'src' / 'App.tsx').read_text()
    routes = {p.strip('/').split('/')[0] for p in re.findall(r'path="(/[^"*]*)"', app_tsx)} - {''}
    assert routes and routes <= CLIENT_ROUTES, f'missing from CLIENT_ROUTES: {sorted(routes - CLIENT_ROUTES)}'
