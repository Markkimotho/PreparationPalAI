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
