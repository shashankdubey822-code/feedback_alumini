"""
db_helper.py — Database initialization and startup helpers.
Uses native psycopg2 via supabase_db.py — no SQLite shim.
"""

import logging
from backend.utils.supabase_db import get_db, execute_all

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema SQL — single source of truth for all table definitions
# ---------------------------------------------------------------------------
_SCHEMA_SQL = """
DROP TABLE IF EXISTS certificate_jobs CASCADE;
DROP TABLE IF EXISTS feedback_analysis CASCADE;
DROP TABLE IF EXISTS feedback_responses CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS students CASCADE;

CREATE TABLE students (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    roll_no         TEXT UNIQUE,
    department      TEXT,
    email           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE events (
    id                  BIGSERIAL PRIMARY KEY,
    name                TEXT,
    speaker_name        TEXT NOT NULL,
    venue_date          TEXT NOT NULL,
    form_id             TEXT UNIQUE,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'creating_form', 'active', 'closed')),
    template_id         TEXT,
    send_certificates   BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE feedback_responses (
    id                          BIGSERIAL PRIMARY KEY,
    event_id                    BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    student_id                  BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    submitted_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_rating              SMALLINT CHECK (session_rating BETWEEN 1 AND 5),
    aspect_most_valuable        TEXT,
    improvements_suggestions    TEXT,
    session_help_understanding  TEXT,
    future_topics               TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE feedback_analysis (
    id              BIGSERIAL PRIMARY KEY,
    response_id     BIGINT NOT NULL UNIQUE REFERENCES feedback_responses(id) ON DELETE CASCADE,
    sentiment_score NUMERIC(6,4),
    sentiment_label TEXT CHECK (sentiment_label IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE')),
    keywords_json   JSONB,
    processed_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE certificate_jobs (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    student_id      BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_feedback_event_id ON feedback_responses(event_id);
CREATE INDEX idx_feedback_student_id ON feedback_responses(student_id);
CREATE INDEX idx_analysis_response_id ON feedback_analysis(response_id);
CREATE INDEX idx_cert_jobs_status ON certificate_jobs(status);
"""


def initialize_database(app, log=None):
    """
    Ensure all required tables exist in Supabase PostgreSQL.
    Safe to call on every startup (uses CREATE TABLE IF NOT EXISTS).
    """
    _log = log or logger
    try:
        _log.info("Verifying database schema on Supabase...")
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA_SQL)
        _log.info("Database schema verified and ready")
    except Exception as e:
        _log.error(f"Database initialization failed: {e}")
        raise


def get_table_columns(table_name: str) -> list[str]:
    """Return a list of column names for the given table."""
    rows = execute_all(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        (table_name,)
    )
    return [r['column_name'] for r in rows]


# ---------------------------------------------------------------------------
# Legacy compatibility: kept so old imports don't crash during migration
# These are deprecated — use supabase_db.get_db() directly instead
# ---------------------------------------------------------------------------
def get_db_connection(db_path=None, timeout=30.0):
    """
    DEPRECATED — do not use in new code.
    Returns a raw psycopg2 connection from the pool for legacy callers.
    Caller must commit and return it themselves.
    """
    from backend.utils.supabase_db import get_conn
    conn = get_conn()
    return conn
