from io import BytesIO
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api import app
from app.exports import ExportQuestion, ExportRequest, render_pdf


def sample():
    return ExportQuestion(type='mcq', question='A 2 kg mass accelerates at 3 m/s². What is the net force?',
                          options={'A': '6 N', 'B': '1 N', 'C': '2 N', 'D': '3 N'}, correct='A',
                          explanation='SECRET worked answer: F = ma = 6 N.')


@pytest.mark.parametrize('kind', ['exam', 'worksheet', 'checklist'])
def test_fillable_packs_have_blank_fields_and_no_hidden_key(kind):
    content = render_pdf(ExportRequest(kind=kind, questions=[sample(), ExportQuestion(question='Explain α, ΔT and CO₂.')]))
    reader = PdfReader(BytesIO(content))
    fields = reader.get_fields()
    assert fields['learner_name'].get('/V', '') == ''
    assert ('understood_0' if kind == 'checklist' else 'answer_0') in fields
    assert all('SECRET' not in p.extract_text() for p in reader.pages)
    assert len(reader.pages) == 2
    assert 'CO₂' in reader.pages[1].extract_text()
    # A learner can fill, save, reopen, and retain the entered value.
    with pymupdf.open(stream=content, filetype='pdf') as doc:
        page = doc[0]
        widget = next(w for w in page.widgets() if w.field_name == 'learner_name')
        widget.field_value = 'Ada'; widget.update()
        saved = doc.tobytes()
    with pymupdf.open(stream=saved, filetype='pdf') as reopened:
        page = reopened[0]
        assert next(w for w in page.widgets() if w.field_name == 'learner_name').field_value == 'Ada'


def test_answer_key_separate_and_has_no_response_fields():
    reader = PdfReader(BytesIO(render_pdf(ExportRequest(kind='answers', questions=[sample()]))))
    assert 'SECRET' in reader.pages[0].extract_text()
    assert not reader.get_fields()


def test_export_endpoint_checks_content_and_returns_attachment():
    with patch('app.exports.moderate') as moderation, patch('app.exports.require_model', return_value='test'):
        response = TestClient(app).post('/api/exports/study', json={'questions': [sample().model_dump()]})
    assert response.status_code == 200
    assert response.content.startswith(b'%PDF')
    assert response.headers['cache-control'] == 'no-store'
    moderation.assert_called_once()


def test_export_rejects_missing_or_ambiguous_source():
    client = TestClient(app)
    assert client.post('/api/exports/study', json={}).status_code == 422
    assert client.post('/api/exports/study', json={'questions': [sample().model_dump()], 'deck_id': 'other'}).status_code == 422


def test_export_rejects_excessive_questions():
    response = TestClient(app).post('/api/exports/study', json={'questions': [sample().model_dump()] * 51})
    assert response.status_code == 422


def test_pdf_html_is_escaped_and_does_not_fetch_assets():
    q = ExportQuestion(question='<img src="http://example.invalid/private"> Literal HTML')
    reader = PdfReader(BytesIO(render_pdf(ExportRequest(questions=[q]))))
    assert '<img' in reader.pages[0].extract_text()
