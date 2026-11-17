"""Postgres connection pool for hosted storage (STORAGE_BACKEND=postgres)."""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_base_settings

_pool: ConnectionPool | None = None


def enabled() -> bool:
    return get_base_settings().storage_backend == 'postgres'


def configure(url: str, max_size: int = 20) -> None:
    global _pool
    close()
    _pool = ConnectionPool(url, min_size=1, max_size=max_size, open=True, check=ConnectionPool.check_connection,
                           kwargs={'row_factory': dict_row, 'autocommit': False, 'application_name': 'preparationpal-app'})
    _pool.wait(timeout=15)


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _ensure() -> ConnectionPool:
    if _pool is None:
        configure(get_base_settings().database_url.get_secret_value())
    return _pool


@contextmanager
def transaction():
    """One connection inside one transaction: commits on success, rolls back on any exception."""
    with _ensure().connection() as conn:
        yield conn


def raw_connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row)
