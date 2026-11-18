"""Learner profiles: storage, validation, isolation, and tailoring every AI request to the learner."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import profile
from app.api import app
from app.config import get_base_settings
from app.prompt_library import TASKS, PromptProfile, render_prompt
from app.workspace import workspace_id

client = TestClient(app)
MINE = dict(display_name='Amani', avatar_seed='k3x9', accent='coral', goal='exam', subjects=['Organic chemistry', 'Statistics'],
            level='advanced', exam_context='KCSE, November 2027', language='Kiswahili', daily_goal=20, onboarded=True)


@pytest.fixture(autouse=True)
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'profiles_dir', str(tmp_path / 'profiles'))


def as_workspace(name):
    return workspace_id.set(name)


def test_a_new_learner_gets_defaults_and_is_not_onboarded():
    body = client.get('/api/profile').json()
    assert body['onboarded'] is False and body['accent'] == 'blue' and body['daily_goal'] == 10 and body['subjects'] == []


def test_saving_and_reading_back_through_the_api():
    saved = client.put('/api/profile', json=MINE)
    assert saved.status_code == 200
    body = client.get('/api/profile').json()
    assert {k: body[k] for k in MINE} == MINE and body['updated_at']


@pytest.mark.parametrize('change', [
    dict(accent='purple'), dict(goal='fun'), dict(level='expert'), dict(daily_goal=0), dict(daily_goal=500),
    dict(subjects=[f's{i}' for i in range(7)]), dict(subjects=['']), dict(display_name='x' * 41),
    dict(avatar_seed='../etc'), dict(language=''), dict(unexpected='field'),
])
def test_invalid_profiles_are_refused_and_nothing_is_saved(change):
    assert client.put('/api/profile', json={**MINE, **change}).status_code == 422
    assert client.get('/api/profile').json()['onboarded'] is False


def test_subjects_are_trimmed_and_deduplicated_ignoring_case():
    body = client.put('/api/profile', json={**MINE, 'subjects': [' Physics ', 'physics', 'Maths']}).json()
    assert body['subjects'] == ['Physics', 'Maths']


def test_each_account_has_its_own_profile():
    token = as_workspace('u-aaaaaaaaaaaaaaaaaaaa')
    try:
        profile.save(profile.LearnerProfile(**MINE))
    finally:
        workspace_id.reset(token)
    token = as_workspace('u-bbbbbbbbbbbbbbbbbbbb')
    try:
        assert profile.load().display_name == ''
    finally:
        workspace_id.reset(token)
    assert profile.load('u-aaaaaaaaaaaaaaaaaaaa').display_name == 'Amani'


def test_a_damaged_profile_file_reads_as_defaults_instead_of_failing():
    profile.save(profile.LearnerProfile(**MINE))
    path = profile._file(workspace_id.get())
    path.write_text('{not json')
    assert profile.load().onboarded is False


def test_the_tutor_sees_subject_level_goal_exam_and_language():
    tutor = profile.prompt_profile(profile.LearnerProfile(**MINE))
    assert tutor.discipline == 'Organic chemistry' and tutor.level == 'advanced' and tutor.language == 'Kiswahili'
    assert tutor.exam_context == 'KCSE, November 2027'
    assert tutor.objectives[0].startswith('Prepare for an exam') and 'Cover Statistics.' in tutor.objectives


def test_tailor_uses_the_stored_profile_only_when_the_request_brings_none():
    assert profile.tailor(PromptProfile()) == PromptProfile()                      # not set up yet: unchanged
    profile.save(profile.LearnerProfile(**MINE))
    assert profile.tailor(PromptProfile()).discipline == 'Organic chemistry'       # defaults: tailored
    assert profile.tailor(None).level == 'advanced'
    explicit = PromptProfile(discipline='physics')
    assert profile.tailor(explicit) is explicit                                   # the request's own profile wins


def test_ai_requests_are_pitched_to_the_learner_without_the_app_sending_anything():
    profile.save(profile.LearnerProfile(**MINE))
    with patch('app.api.require_model', return_value='open-default'), \
         patch('app.api.fc.generate_deck', return_value=dict(id='d', name='n', cards=[], created_at=0.0, updated_at=0.0)) as gen:
        assert client.post('/api/flashcards/generate', json={'topic': 'alkenes', 'n': 2}).status_code == 200
    assert gen.call_args.kwargs['profile'].discipline == 'Organic chemistry'


def test_the_rendered_prompt_carries_the_learner_profile():
    tutor = profile.prompt_profile(profile.LearnerProfile(**MINE))
    values = {name: 'x' for name in TASKS['flashcards'].required}
    prompt = render_prompt('flashcards', profile=tutor, **values)
    for expected in ('Organic chemistry', 'advanced', 'KCSE, November 2027', 'Kiswahili', 'Prepare for an exam'):
        assert expected in prompt
