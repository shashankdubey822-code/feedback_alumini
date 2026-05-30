"""
insforge_db.py — HTTP REST connection for InsForge PostgreSQL.

Replaces insforge_db.py.
All backend services should import from this module.
"""

import os
import logging
import contextlib
import requests

logger = logging.getLogger(__name__)

def _get_headers():
    api_key = os.environ.get('INSFORGE_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError("INSFORGE_API_KEY environment variable is not set")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

def _get_url():
    base_url = os.environ.get('INSFORGE_API_BASE_URL', '').strip()
    if not base_url:
        raise RuntimeError("INSFORGE_API_BASE_URL environment variable is not set")
    return f"{base_url.rstrip('/')}/api/database/advance/rawsql"

def _get_records_url(table: str):
    base_url = os.environ.get('INSFORGE_API_BASE_URL', '').strip()
    if not base_url:
        raise RuntimeError("INSFORGE_API_BASE_URL environment variable is not set")
    return f"{base_url.rstrip('/')}/api/database/records/{table}"

def api_insert(table: str, data: list | dict) -> list:
    """Inserts records using InsForge PostgREST API (returns list of inserted dicts)."""
    if isinstance(data, dict):
        data = [data]
    url = _get_records_url(table)
    headers = _get_headers()
    headers['Prefer'] = 'return=representation'
    
    resp = requests.post(url, json=data, headers=headers)
    if not resp.ok:
        logger.error(f"api_insert failed: {resp.text}")
    resp.raise_for_status()
    return resp.json()

def api_upsert(table: str, data: list | dict, conflict_columns: str = 'id') -> list:
    """Upserts records using InsForge PostgREST API."""
    if isinstance(data, dict):
        data = [data]
    url = f"{_get_records_url(table)}?on_conflict={conflict_columns}"
    headers = _get_headers()
    headers['Prefer'] = 'return=representation,resolution=merge-duplicates'
    
    resp = requests.post(url, json=data, headers=headers)
    if not resp.ok:
        logger.error(f"api_upsert failed: {resp.text}")
    resp.raise_for_status()
    return resp.json()

def api_update(table: str, match_col: str, match_val: str, data: dict) -> list:
    """Updates a record matching the column=val using PostgREST API."""
    url = f"{_get_records_url(table)}?{match_col}=eq.{match_val}"
    headers = _get_headers()
    headers['Prefer'] = 'return=representation'
    
    resp = requests.patch(url, json=data, headers=headers)
    if not resp.ok:
        logger.error(f"api_update failed: {resp.text}")
    resp.raise_for_status()
    return resp.json()

def api_select(table: str, match_col: str, match_val: str) -> list:
    """Select records matching the criteria using PostgREST API."""
    url = f"{_get_records_url(table)}?{match_col}=eq.{match_val}"
    headers = _get_headers()
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def _convert_placeholders(query: str) -> str:
    """Convert psycopg2 '%s' placeholders to PostgreSQL '$1', '$2', etc."""
    parts = query.split('%s')
    new_query = parts[0]
    for i, p in enumerate(parts[1:], 1):
        new_query += f"${i}" + p
    return new_query

def _run_sql(query: str, params=None):
    url = _get_url()
    headers = _get_headers()
    
    # Convert placeholders
    pg_query = _convert_placeholders(query)
    
    payload = {"query": pg_query}
    if params:
        payload["params"] = list(params)
        
    try:
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"SQL execution failed: {e}")
        if e.response is not None:
            logger.error(f"Response body: {e.response.text}")
        raise

@contextlib.contextmanager
def get_db():
    """
    Dummy context manager to replace the InsForge connection pool context.
    Since InsForge uses a stateless HTTP REST API, we yield a dummy object.
    We don't need real transaction management here because queries are sent directly.
    """
    class DummyConn:
        class DummyCursor:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb): pass
            
            def __init__(self):
                self._rows = []
                self.rowcount = 0
                
            def execute(self, query, params=None):
                result = _run_sql(query, params)
                self._rows = result.get('rows', [])
                self.rowcount = result.get('rowCount', 0)
                
            def fetchone(self):
                return self._rows[0] if self._rows else None
                
            def fetchall(self):
                return self._rows
                
        def cursor(self):
            return self.DummyCursor()
            
        def commit(self): pass
        def rollback(self): pass
        
    yield DummyConn()

def execute_one(query: str, params=None) -> dict | None:
    """Execute a query and return the first row as a dict, or None."""
    res = _run_sql(query, params)
    rows = res.get('rows', [])
    return rows[0] if rows else None

def execute_all(query: str, params=None) -> list[dict]:
    """Execute a query and return all rows as a list of dicts."""
    res = _run_sql(query, params)
    return res.get('rows', [])

def execute_write(query: str, params=None) -> int:
    """
    Execute an INSERT/UPDATE/DELETE and return the number of affected rows.
    """
    res = _run_sql(query, params)
    return res.get('rowCount', 0)

def execute_returning(query: str, params=None):
    """
    Execute an INSERT ... RETURNING ... and return the first returned value.
    Example:
        new_id = execute_returning(
            "INSERT INTO events (speaker_name) VALUES (%s) RETURNING id",
            ("John",)
        )
    """
    res = _run_sql(query, params)
    rows = res.get('rows', [])
    if rows:
        # Get the first value of the first row dictionary
        first_row = rows[0]
        if first_row:
            return list(first_row.values())[0]
    return None

def close_pool() -> None:
    """No-op for InsForge REST API."""
    pass

def initialize_database(app=None, log=None) -> None:
    """Verify that InsForge can be reached and tables exist."""
    _log = log or logger
    try:
        _log.info("Initialising InsForge REST connection...")
        tables_data = execute_all("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                  'events','feedback_responses',
                  'feedback_analysis','certificate_jobs'
              )
        """)
        found = [r['table_name'] for r in tables_data]
        expected = {'events', 'feedback_responses', 'feedback_analysis', 'certificate_jobs'}
        missing  = expected - set(found)
        if missing:
            _log.warning(
                f"DATABASE SCHEMA WARNING: missing tables: {', '.join(sorted(missing))}. "
                "Run the schema creation SQL before using the application."
            )
        else:
            _log.info(f"Database OK — tables verified: {', '.join(sorted(found))}")
    except Exception as exc:
        _log.error(f"Database initialisation failed: {exc}", exc_info=True)
        raise
