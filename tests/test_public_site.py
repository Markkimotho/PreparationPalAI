import json
import re
from xml.etree import ElementTree

from fastapi.testclient import TestClient
from app.api import app
from app.config import get_settings

client = TestClient(app)


def test_public_html_without_ollama(monkeypatch):
    monkeypatch.setattr(get_settings(), 'public_base_url', 'https://prep.example')
    r = client.get('/')
    assert r.status_code == 200
    assert '<h1>Study deeply.' in r.text
    assert 'href="/prepare"' in r.text and '500 free credits' in r.text
    assert '<script src' not in r.text                      # the landing page stays JavaScript-free
    assert 'rel="canonical" href="https://prep.example/"' in r.text
    assert 'property="og:image" content="https://prep.example/social-preview.png"' in r.text
    schema = json.loads(re.search(r'application/ld\+json">(.*?)</script>', r.text)[1])
    assert schema['@type'] == 'SoftwareApplication'
    assert '/api/' in client.get('/robots.txt').text
    sitemap = ElementTree.fromstring(client.get('/sitemap.xml').text)
    assert len(sitemap) == 1
    assert 'prepare' not in client.get('/sitemap.xml').text


def test_local_instance_not_indexed(monkeypatch):
    monkeypatch.setattr(get_settings(), 'public_base_url', '')
    assert 'noindex' in client.get('/').text
    assert 'Disallow: /' in client.get('/robots.txt').text
    assert len(ElementTree.fromstring(client.get('/sitemap.xml').text)) == 0


def test_api_and_asset_typos_do_not_return_a_successful_spa_shell():
    assert client.get('/api/nonexistent').status_code == 404
    assert client.get('/assets/missing.js').status_code == 404
    assert client.get('/missing-public-page').status_code == 404


def test_public_origin_rejects_embedded_credentials():
    import pytest
    from app.config import Settings
    with pytest.raises(ValueError, match='PUBLIC_BASE_URL'):
        Settings(public_base_url='https://user:password@example.com')


def test_landing_stylesheet_url_changes_when_the_stylesheet_does():
    """Regression: an unversioned /landing.css was served stale by the service worker after a deploy,
    leaving the new page unstyled until a second reload."""
    import re as _re
    from app import public_site
    version = _re.search(r'/landing\.css\?v=([0-9a-f]{12}|dev)"', client.get('/').text)
    assert version, 'the stylesheet link must carry a content version'
    assert version[1] == public_site.stylesheet_version()
