import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.config import get_settings

client = TestClient(app)
QUESTIONS = [dict(type='mcq', question='Which unit measures energy?', topic='Units',
                  answer='A', options=dict(A='Joule', B='Watt', C='Kelvin', D='Newton'),
                  explanation='Energy is measured in joules.'),
             dict(type='free_response', question='Derive the ideal gas law.',
                  topic='Thermodynamics', answer='PV=nRT', explanation='State assumptions.')]


@pytest.fixture(autouse=True)
def local_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), 'coach_db', str(tmp_path / 'coach.sqlite3'))
    with patch('app.model_catalog.get_installed_models', return_value={'test:7b'}), \
         patch('app.coach.get_retriever') as retrieval, patch('app.coach._get_llm') as llm:
        retrieval.return_value.invoke.return_value = []
        llm.return_value.invoke.return_value.content = json.dumps(QUESTIONS)
        yield llm, retrieval


def start(**kwargs):
    if kwargs.get('mode') == 'interview':
        with patch('app.coach._get_llm') as llm:
            llm.return_value.invoke.return_value.content = json.dumps([QUESTIONS[1], dict(QUESTIONS[1], question='Explain the assumptions of the ideal gas law.')])
            r = client.post('/api/coach/sessions', json=dict(learner='alice', topic='Physics',
                model='test:7b', n=2, **kwargs))
            assert r.status_code == 200, r.text
            return r.json()
    r = client.post('/api/coach/sessions', json=dict(learner='alice', topic='Physics',
        model='test:7b', n=2, **kwargs))
    assert r.status_code == 200, r.text
    return r.json()


def submit(s, answer='A', index=0):
    return client.post(f"/api/coach/sessions/{s['id']}/answers", json=dict(
        learner='alice', index=index, answer=answer, confidence=2))


@pytest.mark.parametrize('mode', ['recap', 'exam', 'interview', 'review'])
def test_modes_and_no_answer_leak(mode):
    s = start(mode=mode)
    assert s['mode'] == mode
    assert s['grounding'] == 'model-general knowledge'
    assert 'answer' not in s['question']
    assert 'explanation' not in s['question']


def test_resume_duplicate_and_learner_scope():
    s = start()
    r = submit(s)
    assert r.status_code == 200
    assert r.json()['index'] == 1
    assert submit(s).status_code == 409
    assert client.get(f"/api/coach/sessions/{s['id']}?learner=bob").status_code == 404
    assert client.get(f"/api/coach/sessions/{s['id']}?learner=alice").json()['index'] == 1


def test_result_breakdown_and_weak_review(local_runtime):
    s = start()
    submit(s, answer='B')
    evaluation = dict(score=80, is_correct=True, feedback='Good reasoning', key_missed=[], hint='Check units')
    with patch('app.coach.validate_answer', return_value=evaluation):
        result = submit(s, answer='PV=nRT', index=1).json()
    assert result['done']
    assert result['summary']['score'] == 40
    assert result['summary']['weak'][0]['topic'] == 'Units'
    assert result['summary']['next_actions']
    assert client.get('/api/coach/history?learner=alice').json()['weak_topics'] == ['Units']
    review = start(mode='review')
    assert review['topic'] == 'Units'


def test_server_enforces_expiry():
    s = start(mode='exam', minutes=1)
    with patch('app.coach.time.time', return_value=s['deadline'] + 1):
        assert submit(s).status_code == 409
        result = client.get(f"/api/coach/sessions/{s['id']}?learner=alice").json()
    assert result['done'] and result['summary']['score'] == 0


def test_interview_followup(local_runtime):
    s = start(mode='interview')
    llm, _ = local_runtime
    llm.return_value.invoke.return_value.content = json.dumps(QUESTIONS[1])
    with patch('app.coach.validate_answer', return_value=dict(score=60, is_correct=False,
            feedback='Explain assumptions.', key_missed=['Assumptions'], hint='Review the gas model.')):
        result = submit(s).json()
    assert result['total'] == 3
    assert result['question']['type'] == 'free_response'


def test_failed_grading_preserves_question():
    s = start()
    with patch('app.coach.validate_answer', return_value=dict(
            feedback='Could not grade answer: offline', score=0)):
        assert submit(s).status_code == 502
    assert client.get(f"/api/coach/sessions/{s['id']}?learner=alice").json()['index'] == 0


def test_generation_rejects_invalid_options(local_runtime):
    llm, _ = local_runtime
    llm.return_value.invoke.return_value.content = json.dumps([
        dict(QUESTIONS[0], options={'A': 'only one'}), QUESTIONS[1]])
    assert client.post('/api/coach/sessions', json=dict(
        learner='alice', topic='x', model='test:7b')).status_code == 502


def test_grounding_has_actual_sources(local_runtime):
    _, retrieval = local_runtime
    retrieval.return_value.invoke.return_value = [SimpleNamespace(
        metadata=dict(source='physics.pdf', page=2), page_content='Energy is measured in joules.')]
    s = start()
    assert s['grounding'] == 'documents'
    assert s['sources'] == [dict(source='physics.pdf', page=2)]


def test_recap_adapts_next_question_after_misconception(local_runtime):
    s = start()
    llm, _ = local_runtime
    llm.return_value.invoke.return_value.content = json.dumps(dict(
        QUESTIONS[1], topic='Units', question='Recall the unit of force.'))
    result = submit(s, answer='B').json()
    assert result['question']['adaptive']
    assert result['question']['topic'] == 'Units'
    assert result['total'] == 2


def test_generation_retries_truncated_json_without_leaking_it(local_runtime):
    llm, _ = local_runtime
    llm.return_value.invoke.side_effect = [
        SimpleNamespace(content='[{"question":"PRIVATE STUDY TEXT', response_metadata={'done_reason': 'length'}),
        SimpleNamespace(content=json.dumps({'questions': QUESTIONS}), response_metadata={}),
    ]
    assert start()['total'] == 2
    assert llm.return_value.invoke.call_count == 2


def test_generation_uses_small_batches_and_preserves_exact_count(local_runtime):
    llm, _ = local_runtime
    llm.return_value.invoke.side_effect = [SimpleNamespace(content=json.dumps({'questions': batch}), response_metadata={})
        for batch in [QUESTIONS, [dict(q, question=q['question'] + ' Again?') for q in QUESTIONS],
                      [dict(QUESTIONS[0], question='Which unit measures work?')]]]
    response = client.post('/api/coach/sessions', json=dict(learner='alice', topic='Physics', model='test:7b', n=5))
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 5
    assert llm.return_value.invoke.call_count == 3
    assert 'response_format' in llm.call_args.kwargs


def test_failed_generation_is_actionable_and_does_not_save_partial_session(local_runtime):
    llm, _ = local_runtime
    llm.return_value.invoke.return_value.content = '[{"question":"PRIVATE STUDY TEXT'
    response = client.post('/api/coach/sessions', json=dict(learner='alice', topic='Physics', model='test:7b', n=5))
    assert response.status_code == 502
    assert 'PRIVATE' not in response.text
    assert 'fewer questions' in response.json()['detail']
    assert client.get('/api/coach/history?learner=alice').json()['sessions'] == []
    assert llm.return_value.invoke.call_count == 2


def test_requested_format_is_enforced_by_schema_and_prompt(local_runtime):
    llm, _ = local_runtime
    llm.return_value.invoke.return_value.content = json.dumps([
        QUESTIONS[0], dict(QUESTIONS[0], question='Which unit measures work?')])
    response = client.post('/api/coach/sessions', json=dict(learner='alice', topic='Physics',
        model='test:7b', n=2, question_type='mcq'))
    assert response.status_code == 200
    schema = llm.call_args.kwargs['response_format']['$defs']['Question']['properties']
    assert schema['type']['enum'] == ['mcq']
    assert schema['answer']['enum'] == list('ABCD')
    assert schema['options']['required'] == list('ABCD')
    prompt = llm.return_value.invoke.call_args.args[0][0].content
    assert 'Use only mcq questions.' in prompt
    assert 'For mixed use' not in prompt
