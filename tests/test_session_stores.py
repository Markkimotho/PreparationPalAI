"""Coach sessions and drawing submissions on both storage backends."""
import threading

import pytest
from fastapi import HTTPException

from app import coach, drawings, purge
from app.config import get_base_settings
from app.workspace import identity_id, role, workspace_id


@pytest.fixture(params=['files', 'postgres'])
def backend(request, tmp_path, monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'coach_db', str(tmp_path / 'coach' / 'sessions.sqlite3'))
    monkeypatch.setattr(settings, 'storage_backend', request.param)
    if request.param == 'postgres':
        request.getfixturevalue('pg')
    token = workspace_id.set('u-test')
    yield request.param
    workspace_id.reset(token)


def session(session_id='s1', learner='ann', **extra):
    base = dict(id=session_id, learner=learner, topic='forces', mode='recap', answers=[], questions=[{'question': 'q'}],
                deadline=0, model='m', grounding='model-general knowledge', sources=[])
    return base | extra


def as_user(workspace):
    return workspace_id.set(workspace)


# ---- coach sessions ---------------------------------------------------------------------

def test_a_session_round_trips_and_is_only_visible_to_its_learner(backend):
    with coach.connect() as db:
        coach.save(db, session())
        assert coach.load(db, 's1', 'ann')['topic'] == 'forces'
        with pytest.raises(HTTPException) as caught:
            coach.load(db, 's1', 'someone-else')
        assert caught.value.status_code == 404


def test_saving_again_replaces_the_session(backend):
    with coach.connect() as db:
        coach.save(db, session())
        coach.save(db, session(topic='replaced'))
        assert coach.load(db, 's1', 'ann')['topic'] == 'replaced'


def test_history_is_newest_first_and_capped_at_thirty(backend):
    with coach.connect() as db:
        for n in range(35):
            coach.save(db, session(f's{n}'))
    token = identity_id.set('ann')
    try:
        history = coach.history('ann')
    finally:
        identity_id.reset(token)
    ids = [s['id'] for s in history['sessions']]
    assert len(ids) == 30 and ids[0] == 's34' and ids[-1] == 's5'


def test_weak_topics_come_from_this_learners_low_scores_only(backend):
    low = session('s1')
    low['answers'] = [dict(topic='thermo', result=dict(score=30)), dict(topic='forces', result=dict(score=90))]
    other = session('s2', learner='bob')
    other['answers'] = [dict(topic='optics', result=dict(score=10))]
    with coach.connect() as db:
        coach.save(db, low)
        coach.save(db, other)
        assert coach.weak_topics(db, 'ann') == ['thermo']


def test_the_same_session_id_in_two_workspaces_does_not_collide(backend):
    with coach.connect() as db:
        coach.save(db, session(topic='mine'))
    token = as_user('u-other')
    try:
        with coach.connect() as db:
            coach.save(db, session(topic='theirs'))
            assert coach.load(db, 's1', 'ann')['topic'] == 'theirs'
    finally:
        workspace_id.reset(token)
    with coach.connect() as db:
        assert coach.load(db, 's1', 'ann')['topic'] == 'mine'


def test_two_answers_racing_for_the_same_question_record_exactly_one(backend):
    with coach.connect() as db:
        coach.save(db, session())
    results, barrier = [], threading.Barrier(10)

    def answer():
        token = workspace_id.set('u-test')
        barrier.wait()
        try:
            with coach.connect() as db:
                latest = coach.load(db, 's1', 'ann', for_update=True)
                if len(latest['answers']) != 0:
                    results.append('conflict')
                    return
                latest['answers'].append(dict(topic='forces', result=dict(score=80)))
                coach.save(db, latest)
                results.append('recorded')
        finally:
            workspace_id.reset(token)

    threads = [threading.Thread(target=answer) for _ in range(10)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert results.count('recorded') == 1 and results.count('conflict') == 9


# ---- drawings -----------------------------------------------------------------------------

def body(drawing_id, **extra):
    return dict(id=drawing_id, question='q', scene={'elements': []}, reference='r', status='pending', reviews=[], **extra)


def put(drawing_id, owner='ann'):
    token = identity_id.set(owner)
    try:
        with drawings.connect() as db:
            db.insert(drawing_id, owner, body(drawing_id), b'\x89PNG-image')
    finally:
        identity_id.reset(token)


def test_a_drawing_round_trips_with_its_image(backend):
    put('d1')
    tokens = identity_id.set('ann'), role.set('reader')
    try:
        with drawings.connect() as db:
            row, parsed = drawings.load(db, 'd1')
        assert row['image'] == b'\x89PNG-image' and parsed['id'] == 'd1' and row['owner'] == 'ann'
    finally:
        identity_id.reset(tokens[0]); role.reset(tokens[1])


def test_a_reader_cannot_open_someone_elses_drawing_but_a_reviewer_can(backend):
    put('d1', owner='ann')
    for who, allowed in (('reader', False), ('editor', True)):
        tokens = identity_id.set('bob'), role.set(who)
        try:
            with drawings.connect() as db:
                if allowed:
                    assert drawings.load(db, 'd1')[1]['id'] == 'd1'
                else:
                    with pytest.raises(HTTPException) as caught:
                        drawings.load(db, 'd1')
                    assert caught.value.status_code == 404
        finally:
            identity_id.reset(tokens[0]); role.reset(tokens[1])


def test_listing_pages_newest_first_and_hides_other_owners_from_readers(backend):
    for n in range(5):
        put(f'd{n}', owner='ann' if n % 2 == 0 else 'bob')
    tokens = identity_id.set('ann'), role.set('reader')
    try:
        mine = drawings.list_submissions(limit=50, before=None)
        import json
        payload = json.loads(mine.body)
        assert [d['id'] for d in payload['drawings']] == ['d4', 'd2', 'd0'] and payload['can_review'] is False
        first = json.loads(drawings.list_submissions(limit=2, before=None).body)
        assert len(first['drawings']) == 2 and first['next_cursor']
        older = json.loads(drawings.list_submissions(limit=2, before=first['next_cursor']).body)
        assert [d['id'] for d in older['drawings']] == ['d0']
    finally:
        identity_id.reset(tokens[0]); role.reset(tokens[1])


def test_many_reviews_added_at_once_are_all_kept(backend):
    put('d1')
    barrier = threading.Barrier(12)

    def review(i):
        tokens = workspace_id.set('u-test'), identity_id.set('ann'), role.set('admin')
        barrier.wait()
        try:
            drawings.save_review('d1', dict(kind='human', feedback=f'note {i}', status='reviewed'))
        finally:
            workspace_id.reset(tokens[0]); identity_id.reset(tokens[1]); role.reset(tokens[2])

    threads = [threading.Thread(target=review, args=(i,)) for i in range(12)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    tokens = identity_id.set('ann'), role.set('admin')
    try:
        with drawings.connect() as db:
            reviews = drawings.load(db, 'd1')[1]['reviews']
    finally:
        identity_id.reset(tokens[0]); role.reset(tokens[1])
    assert sorted(r['feedback'] for r in reviews) == sorted(f'note {i}' for i in range(12))


def test_drawings_are_isolated_between_workspaces(backend):
    put('d1')
    token = as_user('u-other')
    tokens = identity_id.set('ann'), role.set('admin')          # even an admin of another workspace sees nothing
    try:
        with drawings.connect() as db:
            with pytest.raises(HTTPException):
                drawings.load(db, 'd1')
    finally:
        identity_id.reset(tokens[0]); role.reset(tokens[1]); workspace_id.reset(token)


def test_the_backend_under_test_is_really_the_one_in_use(backend):
    with coach.connect() as db:
        coach.save(db, session())
    put('d1')
    if backend == 'postgres':
        from app import db as pg
        with pg.transaction() as conn:
            assert conn.execute("SELECT count(*) AS n FROM app.coach_sessions WHERE workspace = 'u-test'").fetchone()['n'] == 1
            assert conn.execute("SELECT count(*) AS n FROM app.drawings WHERE workspace = 'u-test'").fetchone()['n'] == 1


def test_purging_removes_sessions_and_drawings_for_one_workspace(backend):
    with coach.connect() as db:
        coach.save(db, session())
    put('d1')
    token = as_user('u-keep')
    try:
        with coach.connect() as db:
            coach.save(db, session('keep-me'))
    finally:
        workspace_id.reset(token)
    assert purge.purge_workspace('u-test')['coach'] >= 1
    with coach.connect() as db:
        with pytest.raises(HTTPException):
            coach.load(db, 's1', 'ann')
    token = as_user('u-keep')
    try:
        with coach.connect() as db:
            assert coach.load(db, 'keep-me', 'ann')['id'] == 'keep-me'
    finally:
        workspace_id.reset(token)
