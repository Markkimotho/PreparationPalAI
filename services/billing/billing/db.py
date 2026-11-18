"""Connection pool and transaction helper. Every ledger change runs inside `transaction()`."""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def configure(url: str, max_size: int = 20) -> None:
    global _pool
    close()
    _pool = ConnectionPool(url, min_size=1, max_size=max_size, kwargs={'row_factory': dict_row, 'autocommit': False}, open=True)
    _pool.wait(timeout=15)


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def transaction():
    """A connection inside one transaction: commits on success, rolls back on any exception."""
    if _pool is None:
        raise RuntimeError('billing.db is not configured')
    with _pool.connection() as conn:
        yield conn


def raw_connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row)
