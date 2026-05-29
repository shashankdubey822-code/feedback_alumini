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
CREATE TABLE IF NOT EXISTS events (
    id                  BIGSERIAL PRIMARY KEY,
    name                TEXT,
    speaker_name        TEXT NOT NULL,
    venue_date          TEXT NOT NULL,
    department          TEXT,
    form_id             TEXT UNIQUE,
    form_url            TEXT,
    form_edit_url       TEXT,
    template_id         TEXT,
    send_certificates   BOOLEAN DEFAULT FALSE,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'creating_form', 'active', 'closed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_form_id ON events(form_id);
CREATE INDEX IF NOT EXISTS idx_events_status  ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);

CREATE TABLE IF NOT EXISTS feedback_responses (
    id                          BIGSERIAL PRIMARY KEY,
    event_id                    BIGINT REFERENCES events(id) ON DELETE SET NULL,
    submitted_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp_display           TEXT,
    name_of_student             TEXT,
    roll_no                     TEXT,
    department                  TEXT,
    student_email               TEXT,
    date_of_lecture             TEXT,
    alumni_speaker_name         TEXT,
    session_help_understanding  TEXT,
    session_rating              SMALLINT CHECK (session_rating BETWEEN 1 AND 5),
    session_technical_clarity   SMALLINT CHECK (session_technical_clarity BETWEEN 1 AND 5),
    aspect_most_valuable        TEXT,
    improvements_suggestions    TEXT,
    future_topics               TEXT,
    form_source                 TEXT DEFAULT 'webhook',
    data_quality_score          NUMERIC(5,2),
    is_duplicate                BOOLEAN DEFAULT FALSE,
    record_status               TEXT DEFAULT 'active',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_event_id     ON feedback_responses(event_id);
CREATE INDEX IF NOT EXISTS idx_feedback_submitted_at ON feedback_responses(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_speaker      ON feedback_responses(alumni_speaker_name);
CREATE INDEX IF NOT EXISTS idx_feedback_department   ON feedback_responses(department);
CREATE INDEX IF NOT EXISTS idx_feedback_roll_no      ON feedback_responses(roll_no);

CREATE TABLE IF NOT EXISTS feedback_analysis (
    id              BIGSERIAL PRIMARY KEY,
    response_id     BIGINT NOT NULL UNIQUE REFERENCES feedback_responses(id) ON DELETE CASCADE,
    sentiment_score NUMERIC(6,4),
    sentiment_label TEXT CHECK (sentiment_label IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE')),
    keywords_json   JSONB,
    topic_id        INTEGER,
    topic_label     TEXT,
    processed_at    TIMESTAMPTZ DEFAULT NOW(),
    model_version   TEXT DEFAULT 'v1'
);

CREATE INDEX IF NOT EXISTS idx_analysis_response_id ON feedback_analysis(response_id);
CREATE INDEX IF NOT EXISTS idx_analysis_sentiment   ON feedback_analysis(sentiment_label);

CREATE TABLE IF NOT EXISTS certificate_jobs (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    response_id     BIGINT REFERENCES feedback_responses(id) ON DELETE SET NULL,
    student_name    TEXT NOT NULL,
    student_email   TEXT NOT NULL,
    roll_no         TEXT,
    department      TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts        SMALLINT DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cert_jobs_status   ON certificate_jobs(status);
CREATE INDEX IF NOT EXISTS idx_cert_jobs_event_id ON certificate_jobs(event_id);
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
