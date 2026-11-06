import base64
import io
import hashlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import app
from app.config import get_base_settings
from app.drawings import normalized_png


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'coach_db', str(tmp_path / 'sessions.sqlite3'))
    monkeypatch.setattr(get_base_settings(), 'auth_enabled', True)
    monkeypatch.setattr(get_base_settings(), 'auth_tokens', {
        hashlib.sha256(key.encode()).hexdigest(): {'workspace': workspace, 'role': role}
        for key, workspace, role in [('admin', 'classroom', 'admin'), ('student-a', 'classroom', 'reader'),
                                     ('student-b', 'classroom', 'reader'), ('other-admin', 'other-classroom', 'admin')]})
    with patch('app.drawings.check_text'), TestClient(app, headers={'Authorization': 'Bearer admin'}) as client:
        yield client


def submission():
    image = Image.new('RGB', (64, 64), 'white')
    buffer = io.BytesIO(); image.save(buffer, 'PNG')
    return dict(question='Draw a free-body diagram for a stationary block.', explanation='Upward normal and downward weight balance.',
                image='data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(),
                scene={'elements': [{'id': 'arrow-1', 'type': 'arrow'}]})


def test_submit_persists_private_image_scene_and_pending_review(client):
    result = client.post('/api/drawings', json=submission())
    assert result.status_code == 200
    body = result.json()
    assert body['status'] == 'pending' and body['reviews'] == []
    assert 'reference' not in body and 'scene' not in body
    assert client.get(f"/api/drawings/{body['id']}/image").content.startswith(b'\x89PNG')
    assert client.get(f"/api/drawings/{body['id']}/scene").json()['elements'][0]['type'] == 'arrow'
    assert client.get('/api/drawings').json()['drawings'][0]['id'] == body['id']


def test_reader_can_submit_but_not_review_another_students_work(client):
    client.headers['Authorization'] = 'Bearer student-a'
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    assert client.post(f'/api/drawings/{drawing}/review', json={'feedback': 'Good.'}).status_code == 403
    client.headers['Authorization'] = 'Bearer student-b'
    assert client.get('/api/drawings').json()['drawings'] == []
    assert client.get(f'/api/drawings/{drawing}/image').status_code == 404
    assert client.get(f'/api/drawings/{drawing}/scene').status_code == 404


def test_workspaces_are_isolated(client):
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    client.headers['Authorization'] = 'Bearer other-admin'
    assert client.get('/api/drawings').json()['drawings'] == []
    assert client.get(f'/api/drawings/{drawing}/image').status_code == 404


def test_human_feedback_is_saved_without_changing_coach_scores(client):
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    result = client.post(f'/api/drawings/{drawing}/review', json={'feedback': 'Label the normal force.', 'score': 70})
    assert result.status_code == 200
    assert result.json()['status'] == 'reviewed'
    assert result.json()['reviews'][0]['score'] == 70
    assert result.json()['reviews'][0]['kind'] == 'human'


@pytest.mark.parametrize('change', [
    {'image': 'data:image/png;base64,broken'},
    {'scene': {'elements': []}},
    {'scene': {'elements': [{'type': 'image', 'fileId': 'private'}]}},
    {'scene': {'elements': [{'type': 'rectangle', 'link': 'https://untrusted.invalid'}]}},
])
def test_rejects_invalid_images_empty_scenes_and_external_content(client, change):
    assert client.post('/api/drawings', json={**submission(), **change}).status_code == 422
    assert client.get('/api/drawings').json()['drawings'] == []


def test_non_vision_model_cannot_guess_a_diagram(client):
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    with patch('app.drawings.require_model', return_value='qwen2.5:7b'), patch('app.drawings.httpx.post') as show, patch('app.drawings.vision_call') as vision:
        show.return_value.json.return_value = {'capabilities': ['completion']}
        response = client.post(f'/api/drawings/{drawing}/ai-review', json={'model': 'qwen2.5:7b'})
        assert response.status_code == 409
        vision.assert_not_called()
    assert client.get('/api/drawings').json()['drawings'][0]['status'] == 'pending'


def test_ai_inspects_image_before_review_and_never_assigns_score(client):
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    with patch('app.drawings.require_model', return_value='vision-model'), patch('app.drawings.httpx.post') as show, patch('app.drawings.vision_call') as vision:
        show.return_value.json.return_value = {'capabilities': ['vision', 'completion']}
        vision.side_effect = [{'safe': True}, {'status': 'unclear', 'observations': ['The image is blank.'], 'feedback': 'Draw the force arrows.', 'improvements': ['Label each force.']}]
        result = client.post(f'/api/drawings/{drawing}/ai-review', json={'model': 'vision-model'})
        assert result.status_code == 200
        body = result.json()
        assert body['status'] == 'needs_clarification' and body['reviews'][0]['score'] is None
        assert vision.call_args_list[0].args[3].startswith(b'\x89PNG')
        assert 'drawing_review' in vision.call_args_list[1].args[1]


@pytest.mark.parametrize('decision', [{'safe': False}, {'safe': 1}, {'safe': 'true'}, {}, []])
def test_visual_safety_fails_closed_and_preserves_submission(client, decision):
    drawing = client.post('/api/drawings', json=submission()).json()['id']
    with patch('app.drawings.require_model', return_value='vision'), patch('app.drawings.httpx.post') as show, patch('app.drawings.vision_call', return_value=decision) as vision:
        show.return_value.json.return_value = {'capabilities': ['vision']}
        result = client.post(f'/api/drawings/{drawing}/ai-review', json={'model': 'vision'})
        assert result.status_code == 422
        assert vision.call_count == 1
    assert client.get('/api/drawings').json()['drawings'][0]['reviews'] == []


def test_png_transparency_is_composited_on_white():
    buffer = io.BytesIO(); Image.new('RGBA', (32, 32), (0, 0, 0, 0)).save(buffer, 'PNG')
    result = normalized_png('data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode())
    assert Image.open(io.BytesIO(result)).getpixel((0, 0)) == (255, 255, 255)


def test_explicit_drawing_instruction_cannot_be_mislabelled_by_a_model():
    from app.quiz import QuizItem
    from app.coach import Question
    from app.drawing_requirements import requires_drawing
    assert not requires_drawing('Which command lets you draw a graph?')
    assert not requires_drawing('Draw conclusions from this graph.')
    question = 'Draw a labelled free-body diagram for a stationary block.'
    quiz = QuizItem(type='short_answer', question=question, drawing_required=False, drawing_prompt='The solution is normal up, weight down.', source='mechanics.txt', sample_answer='Normal up, weight down.')
    coach = Question(type='free_response', question=question, drawing_required=False, topic='Physics', answer='Normal up, weight down.')
    assert quiz.drawing_required and coach.drawing_required
    assert quiz.drawing_prompt and coach.drawing_prompt
    assert 'solution' not in quiz.drawing_prompt and 'weight' not in quiz.drawing_prompt


def test_review_pagination_does_not_hide_older_submissions(client):
    created = [client.post('/api/drawings', json=submission()).json()['id'] for _ in range(3)]
    first = client.get('/api/drawings?limit=2')
    assert first.headers['cache-control'] == 'no-store'
    body = first.json()
    assert [d['id'] for d in body['drawings']] == created[::-1][:2]
    second = client.get(f"/api/drawings?limit=2&before={body['next_cursor']}").json()
    assert second['drawings'][0]['id'] == created[0]
    assert second['next_cursor'] is None
