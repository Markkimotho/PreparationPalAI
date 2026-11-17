import threading

import pytest

from app import flashcards as fc, purge
from app.config import get_base_settings
from app.workspace import workspace_id


@pytest.fixture(params=['files', 'postgres'])
def backend(request, tmp_path, monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'flashcards_dir', str(tmp_path / 'cards'))
    monkeypatch.setattr(settings, 'storage_backend', request.param)
    if request.param == 'postgres':
        request.getfixturevalue('pg')
    # Use a private workspace so the files backend writes under a temp folder, like production
    token = workspace_id.set('u-test')
    yield request.param
    workspace_id.reset(token)


def as_user(workspace):
    return workspace_id.set(workspace)


def test_deck_and_card_lifecycle(backend):
    deck = fc.create_deck('  Physics  ', [dict(front='F', back='ma')])
    assert deck['name'] == 'Physics' and len(deck['cards']) == 1
    assert [d['name'] for d in fc.list_decks()] == ['Physics'] and fc.list_decks()[0]['card_count'] == 1
    card = fc.add_card(deck['id'], 'V', 'IR')
    assert fc.get_deck(deck['id'])['cards'][1]['front'] == 'V'
    assert fc.update_card(deck['id'], card['id'], 'V?', 'I times R')['back'] == 'I times R'
    assert fc.delete_card(deck['id'], card['id']) is True and fc.delete_card(deck['id'], card['id']) is False
    assert fc.delete_deck(deck['id']) is True and fc.delete_deck(deck['id']) is False
    assert fc.get_deck(deck['id']) is None and fc.list_decks() == []


def test_missing_decks_and_cards_return_nothing_not_errors(backend):
    assert fc.get_deck('nope') is None and fc.add_card('nope', 'a', 'b') is None
    deck = fc.create_deck('D')
    assert fc.update_card(deck['id'], 'missing', 'a', 'b') is None and fc.delete_card('nope', 'x') is False


def test_blank_names_become_untitled_and_newest_decks_list_first(backend):
    first = fc.create_deck('First')
    second = fc.create_deck('   ')
    assert second['name'] == 'Untitled deck'
    assert [d['id'] for d in fc.list_decks()] == [second['id'], first['id']]


def test_learners_cannot_see_or_touch_each_others_decks(backend):
    mine = fc.create_deck('Mine', [dict(front='a', back='b')])
    token = as_user('u-other')
    try:
        assert fc.list_decks() == [] and fc.get_deck(mine['id']) is None
        assert fc.add_card(mine['id'], 'x', 'y') is None and fc.delete_deck(mine['id']) is False
        assert fc.update_card(mine['id'], mine['cards'][0]['id'], 'hack', 'hack') is None
    finally:
        workspace_id.reset(token)
    assert fc.get_deck(mine['id'])['cards'][0]['front'] == 'a'


def test_parallel_card_additions_are_not_lost(backend):
    deck = fc.create_deck('Busy')
    barrier = threading.Barrier(15)

    def add(i):
        token = as_user('u-test')
        barrier.wait()
        try:
            fc.add_card(deck['id'], f'q{i}', f'a{i}')
        finally:
            workspace_id.reset(token)

    threads = [threading.Thread(target=add, args=(i,)) for i in range(15)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert sorted(c['front'] for c in fc.get_deck(deck['id'])['cards']) == sorted(f'q{i}' for i in range(15))


def test_the_backend_under_test_is_really_the_one_in_use(backend):
    deck = fc.create_deck('X')
    if backend == 'postgres':
        from app import db
        with db.transaction() as conn:
            assert conn.execute('SELECT count(*) AS n FROM app.flashcard_decks WHERE workspace = %s AND id = %s', ('u-test', deck['id'])).fetchone()['n'] == 1


def test_purging_removes_only_that_learners_decks(backend):
    fc.create_deck('Mine')
    token = as_user('u-keep')
    try:
        fc.create_deck('Neighbour')
    finally:
        workspace_id.reset(token)
    assert purge.purge_workspace('u-test')['flashcards'] >= 1
    assert fc.list_decks() == []
    token = as_user('u-keep')
    try:
        assert [d['name'] for d in fc.list_decks()] == ['Neighbour']
    finally:
        workspace_id.reset(token)
