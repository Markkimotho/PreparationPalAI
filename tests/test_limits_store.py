import threading
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import limits, purge
from app.config import get_base_settings
from app.workspace import identity_id, workspace_id


@pytest.fixture(params=['files', 'postgres'])
def backend(request, tmp_path, monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'usage_db', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(settings, 'storage_backend', request.param)
    monkeypatch.setattr(settings, 'requests_per_minute', 5)
    monkeypatch.setattr(settings, 'requests_per_day', 8)
    if request.param == 'postgres':
        request.getfixturevalue('pg')
    return request.param


def as_user(workspace, identity=None):
    return workspace_id.set(workspace), identity_id.set(identity or workspace)


def reset(tokens):
    workspace_id.reset(tokens[0])
    identity_id.reset(tokens[1])


def test_the_minute_limit_blocks_the_sixth_request_with_retry_after(backend):
    tokens = as_user('u-a')
    try:
        for _ in range(5):
            limits.consume()
        with pytest.raises(HTTPException) as caught:
            limits.consume()
    finally:
        reset(tokens)
    assert caught.value.status_code == 429 and caught.value.headers['Retry-After'] == '60'


def test_the_window_slides_so_requests_return_after_a_minute(backend):
    tokens = as_user('u-a')
    try:
        for _ in range(5):
            limits.consume()
        later = time.time() + 61
        with patch('time.time', return_value=later), patch('app.limits.time.time', return_value=later):
            limits.consume()
    finally:
        reset(tokens)


def test_the_daily_limit_applies_even_when_the_minute_window_is_clear(backend):
    tokens = as_user('u-a')
    try:
        now = time.time()
        for n in range(8):
            with patch('app.limits.time.time', return_value=now + n * 120):
                limits.consume()
        with patch('app.limits.time.time', return_value=now + 8 * 120), pytest.raises(HTTPException):
            limits.consume()
    finally:
        reset(tokens)


def test_learners_have_separate_budgets_even_in_one_workspace(backend):
    for identity in ('person-1', 'person-2'):
        tokens = as_user('shared-class', identity)
        try:
            for _ in range(5):
                limits.consume()
        finally:
            reset(tokens)
    tokens = as_user('u-other')
    try:
        limits.consume()
    finally:
        reset(tokens)


def test_parallel_requests_cannot_slip_past_the_limit(backend):
    allowed, refused, barrier = [], [], threading.Barrier(30)

    def worker():
        tokens = as_user('u-a')
        barrier.wait()
        try:
            limits.consume()
            allowed.append(1)
        except HTTPException:
            refused.append(1)
        finally:
            reset(tokens)

    threads = [threading.Thread(target=worker) for _ in range(30)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert (len(allowed), len(refused)) == (5, 25)


def test_the_backend_under_test_is_really_the_one_in_use(backend):
    tokens = as_user('u-a')
    try:
        limits.consume()
    finally:
        reset(tokens)
    if backend == 'postgres':
        from app import db
        with db.transaction() as conn:
            assert conn.execute("SELECT count(*) AS n FROM app.usage_events WHERE workspace = 'u-a'").fetchone()['n'] == 1


def test_purging_removes_a_learners_usage_rows_only(backend):
    for user in ('u-aaa', 'u-bbb'):
        tokens = as_user(user)
        try:
            limits.consume()
        finally:
            reset(tokens)
    assert purge.purge_workspace('u-aaa')['usage'] == 1
    tokens = as_user('u-bbb')
    try:
        for _ in range(4):
            limits.consume()                                     # still has 4 of its 5 left, so its row survived
        with pytest.raises(HTTPException):
            limits.consume(); limits.consume()
    finally:
        reset(tokens)
