import threading

from billing import db, ledger
from billing.ledger import InsufficientCredits


def seed(micros):
    with db.transaction() as conn:
        ledger.credit(conn, 'a1', micros, 'topup', f'seed-{micros}')


def run_parallel(count, target):
    results, barrier = [None] * count, threading.Barrier(count)

    def worker(i):
        barrier.wait()
        try:
            results[i] = target(i)
        except Exception as exc:  # noqa: BLE001
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    return results


def test_concurrent_reserves_never_overdraw():
    seed(5_000)

    def reserve(i):
        with db.transaction() as conn:
            ledger.reserve(conn, 'a1', f'r{i}', 1_000, 'chat', 'open-default')
            return 'ok'

    results = run_parallel(20, reserve)
    assert results.count('ok') == 5
    assert sum(isinstance(r, InsufficientCredits) for r in results) == 15
    with db.transaction() as conn:
        assert (ledger.balance(conn, 'a1').available_micros, ledger.balance(conn, 'a1').reserved_micros) == (0, 5_000)
        assert ledger.invariant_holds(conn, 'a1')


def test_same_request_reserved_concurrently_is_one_hold():
    seed(10_000)

    def reserve(_):
        with db.transaction() as conn:
            ledger.reserve(conn, 'a1', 'same', 1_000, 'chat', 'open-default')

    run_parallel(10, reserve)
    with db.transaction() as conn:
        assert ledger.balance(conn, 'a1').reserved_micros == 1_000 and ledger.invariant_holds(conn, 'a1')


def test_settle_racing_release_never_double_counts():
    seed(10_000)
    with db.transaction() as conn:
        ledger.reserve(conn, 'a1', 'r1', 3_000, 'chat', 'open-default')

    def act(i):
        with db.transaction() as conn:
            return ledger.settle(conn, 'r1', 1_000, 1) if i % 2 else ledger.release(conn, 'r1')

    run_parallel(8, act)
    with db.transaction() as conn:
        b = ledger.balance(conn, 'a1')
        assert b.reserved_micros == 0 and ledger.invariant_holds(conn, 'a1')
        assert b.available_micros == 9_000  # every ordering charges exactly once
