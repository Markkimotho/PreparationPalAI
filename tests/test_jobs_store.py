"""The same queue behaviour on both storage backends (SQLite files and Postgres)."""
import threading
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document

from app import jobs, purge
from app.config import get_base_settings
from app.workspace import identity_id, workspace_id


@pytest.fixture(params=['files', 'postgres'])
def backend(request, tmp_path, monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'jobs_dir', str(tmp_path / 'jobs'))
    monkeypatch.setattr(settings, 'storage_backend', request.param)
    if request.param == 'postgres':
        request.getfixturevalue('pg')
    return request.param


def as_user(workspace):
    return workspace_id.set(workspace), identity_id.set(workspace)


def reset(tokens):
    workspace_id.reset(tokens[0])
    identity_id.reset(tokens[1])


def test_enqueue_claim_and_complete(backend):
    job = jobs.enqueue('scrape', dict(topic='physics', num_results=1))
    assert job['state'] == 'pending' and jobs.get_job(job['id'])['state'] == 'pending'
    claimed = jobs.claim()
    assert claimed['id'] == job['id'] and claimed['attempts'] == 1 and claimed['state'] == 'running'
    assert jobs.claim() is None                                               # a running job is not handed out twice
    with patch('app.scraper.search_and_scrape', return_value=[Document(page_content='fact', metadata=dict(id='a'))]), \
         patch('app.vectorstore.ingest_documents', return_value=1):
        jobs.run_once()
    # run_once claimed nothing new (the job above is still leased), so finish it the way a worker would
    jobs.store().complete(job['id'], claimed['run_token'], dict(chunks_added=1), time.time())
    assert jobs.get_job(job['id'])['state'] == 'completed' and jobs.get_job(job['id'])['result'] == dict(chunks_added=1)


def test_a_worker_run_completes_a_job_and_a_failure_hides_private_text(backend):
    good = jobs.enqueue('scrape', dict(topic='physics', num_results=1))
    with patch('app.scraper.search_and_scrape', return_value=[Document(page_content='fact', metadata=dict(id='a'))]), \
         patch('app.vectorstore.ingest_documents', return_value=1):
        assert jobs.run_once()
    assert jobs.get_job(good['id'])['result'] == dict(chunks_added=1)
    bad = jobs.enqueue('scrape', dict(topic='physics', num_results=1))
    with patch('app.scraper.search_and_scrape', side_effect=RuntimeError('private document text')):
        jobs.run_once()
    result = jobs.get_job(bad['id'])
    assert result['state'] == 'failed' and 'private' not in result['error']
    assert jobs.retry_job(bad['id'])['state'] == 'pending'
    with pytest.raises(HTTPException) as caught:
        jobs.retry_job(good['id'])                                            # only failed jobs can be retried
    assert caught.value.status_code == 409


def test_an_expired_lease_is_reclaimed_and_repeated_interruptions_fail_the_job(backend):
    job = jobs.enqueue('scrape', dict(topic='x', num_results=1))
    for attempt in (1, 2, 3):
        claimed = jobs.claim()
        assert claimed['id'] == job['id'] and claimed['attempts'] == attempt
        jobs.store().expire_lease(job['id'])                                 # the worker died
    assert jobs.claim() is None
    final = jobs.get_job(job['id'])
    assert final['state'] == 'failed' and 'interrupted' in final['error']


def test_completion_from_a_stale_worker_is_ignored(backend):
    job = jobs.enqueue('scrape', dict(topic='x', num_results=1))
    first = jobs.claim()
    jobs.store().expire_lease(job['id'])
    second = jobs.claim()
    assert first['run_token'] != second['run_token']
    jobs.store().complete(job['id'], first['run_token'], dict(chunks_added=99), time.time())     # the old worker wakes up
    assert jobs.get_job(job['id'])['state'] == 'running'
    jobs.store().complete(job['id'], second['run_token'], dict(chunks_added=1), time.time())
    assert jobs.get_job(job['id'])['result'] == dict(chunks_added=1)


def test_learners_only_see_and_retry_their_own_jobs(backend):
    alice = as_user('u-alice')
    try:
        mine = jobs.enqueue('scrape', dict(topic='a', num_results=1))
    finally:
        reset(alice)
    bob = as_user('u-bob')
    try:
        assert jobs.list_jobs()['jobs'] == []
        with pytest.raises(HTTPException) as caught:
            jobs.get_job(mine['id'])
        assert caught.value.status_code == 404
        with pytest.raises(HTTPException):
            jobs.retry_job(mine['id'])
    finally:
        reset(bob)
    alice = as_user('u-alice')
    try:
        assert [j['id'] for j in jobs.list_jobs()['jobs']] == [mine['id']]
    finally:
        reset(alice)


def test_a_workspace_cannot_flood_the_queue(backend):
    for _ in range(20):
        jobs.enqueue('scrape', dict(topic='x', num_results=1))
    with pytest.raises(HTTPException) as caught:
        jobs.enqueue('scrape', dict(topic='x', num_results=1))
    assert caught.value.status_code == 429
    other = as_user('u-other')
    try:
        jobs.enqueue('scrape', dict(topic='x', num_results=1))                # a different learner is unaffected
    finally:
        reset(other)


def test_heartbeat_and_queue_status(backend):
    jobs.heartbeat('worker-1')
    jobs.enqueue('scrape', dict(topic='x', num_results=1))
    status = jobs.queue_status()
    assert status['worker'] is True and status['pending'] == 1 and status['running'] == 0


def test_ten_workers_racing_for_one_job_produce_one_winner(backend):
    jobs.enqueue('scrape', dict(topic='x', num_results=1))
    winners, barrier = [], threading.Barrier(10)

    def worker():
        barrier.wait()
        job = jobs.claim()
        if job:
            winners.append(job['id'])

    threads = [threading.Thread(target=worker) for _ in range(10)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert len(winners) == 1


def test_purging_a_workspace_removes_its_jobs_only(backend):
    for user in ('u-aaa', 'u-bbb'):
        token = as_user(user)
        try:
            jobs.enqueue('scrape', dict(topic='x', num_results=1))
        finally:
            reset(token)
    assert purge.purge_workspace('u-aaa')['jobs'] >= 1
    token = as_user('u-aaa')
    try:
        assert jobs.list_jobs()['jobs'] == []
    finally:
        reset(token)
    token = as_user('u-bbb')
    try:
        assert len(jobs.list_jobs()['jobs']) == 1
    finally:
        reset(token)


def test_the_backend_under_test_is_really_the_one_in_use(backend):
    assert type(jobs.store()).__name__ == {'files': 'SqliteStore', 'postgres': 'PgStore'}[backend]
    job = jobs.enqueue('scrape', dict(topic='x', num_results=1))
    if backend == 'postgres':
        from app import db
        with db.transaction() as conn:
            assert conn.execute('SELECT count(*) AS n FROM app.ingestion_jobs WHERE id = %s', (job['id'],)).fetchone()['n'] == 1
