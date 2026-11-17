from datetime import datetime, timedelta, timezone

from billing.scheduler import due

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def test_everything_is_due_on_first_start_after_the_daily_time():
    assert set(due(NOW, {})) == {'sweep', 'expire', 'reconcile', 'check-prices'}


def test_interval_tasks_wait_for_their_interval():
    last = {'sweep': NOW - timedelta(seconds=200), 'expire': NOW - timedelta(minutes=30),
            'reconcile': NOW - timedelta(hours=1), 'check-prices': NOW - timedelta(hours=1)}
    assert due(NOW, last) == []
    last['sweep'] = NOW - timedelta(seconds=301)
    assert due(NOW, last) == ['sweep']


def test_daily_tasks_run_once_after_their_time_each_day():
    morning = datetime(2026, 11, 17, 1, 0, tzinfo=timezone.utc)
    fresh = {'sweep': morning, 'expire': morning}
    assert 'reconcile' not in due(morning, fresh | {'reconcile': morning - timedelta(hours=20)})   # before 02:00
    just_after = datetime(2026, 11, 17, 2, 1, tzinfo=timezone.utc)
    assert 'reconcile' in due(just_after, {'reconcile': just_after - timedelta(hours=23)})        # ran yesterday
    assert 'reconcile' not in due(just_after, {'reconcile': datetime(2026, 11, 17, 2, 0, 30, tzinfo=timezone.utc)})
