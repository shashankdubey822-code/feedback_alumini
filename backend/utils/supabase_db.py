"""
supabase_db.py — Native psycopg2 connection pool for Supabase PostgreSQL.

Replaces the fragile pg_helper.py SQLite compatibility shim.
All backend services should import from this module.
"""

import os
import logging
import contextlib
import psycopg2
import psycopg2.extras
from psycopg2 import pool

logger = logging.getLogger(__name__)

_connection_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    """Return (and lazily create) the global connection pool."""
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is not set")

        min_conn = int(os.environ.get('DB_POOL_MIN', 1))
        max_conn = int(os.environ.get('DB_POOL_MAX', 10))

        logger.info(f"Creating connection pool (min={min_conn}, max={max_conn})")
        _connection_pool = pool.ThreadedConnectionPool(
            min_conn, max_conn,
            dsn=db_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _connection_pool


def get_conn() -> psycopg2.extensions.connection:
    """Get a connection from the pool. Caller must call put_conn() when done."""
    return _get_pool().getconn()


def put_conn(conn: psycopg2.extensions.connection, close: bool = False) -> None:
    """Return a connection to the pool."""
    try:
        _get_pool().putconn(conn, close=close)
    except Exception:
        pass


@contextlib.contextmanager
def get_db():
    """
    Context manager for database connections.

    Usage:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
        # auto-committed and returned to pool

    On exception: rolls back automatically.
    """
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def execute_one(query: str, params=None) -> dict | None:
    """Execute a query and return the first row as a dict, or None."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def execute_all(query: str, params=None) -> list[dict]:
    """Execute a query and return all rows as a list of dicts."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall() or []


def execute_write(query: str, params=None) -> int:
    """
    Execute an INSERT/UPDATE/DELETE and return the number of affected rows.
    For INSERT ... RETURNING id, use execute_returning() instead.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount


def execute_returning(query: str, params=None):
    """
    Execute an INSERT ... RETURNING ... and return the first returned value.
    Example:
        new_id = execute_returning(
            "INSERT INTO events (speaker_name) VALUES (%s) RETURNING id",
            ("John",)
        )
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return row[0] if row else None


def close_pool() -> None:
    """Close all connections in the pool. Call on app shutdown."""
    global _connection_pool
    if _connection_pool and not _connection_pool.closed:
        _connection_pool.closeall()
        logger.info("Connection pool closed")
    _connection_pool = None


def initialize_database(app=None, log=None) -> None:
    """
    Verify that the pool can connect and that required tables exist.
    Called from app.py on startup. Logs results via the provided logger
    or falls back to the module-level logger.
    """
    _log = log or logger
    try:
        _log.info("Initialising Supabase PostgreSQL connection pool...")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                          'events','feedback_responses',
                          'feedback_analysis','certificate_jobs'
                      )
                    ORDER BY table_name
                """)
                found = [r['table_name'] for r in cur.fetchall()]
        expected = {'events', 'feedback_responses', 'feedback_analysis', 'certificate_jobs'}
        missing  = expected - set(found)
        if missing:
            _log.warning(
                f"DATABASE SCHEMA WARNING: missing tables: {', '.join(sorted(missing))}. "
                "Run the migration SQL on Supabase before using the application."
            )
        else:
            _log.info(f"Database OK — tables verified: {', '.join(sorted(found))}")
    except Exception as exc:
        _log.error(f"Database initialisation failed: {exc}", exc_info=True)
        raise
