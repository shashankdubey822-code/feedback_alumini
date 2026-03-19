"""
Database initialisation for the Feedback System.
Creates 3 tables: events, feedback_forms, feedback_submissions.
Called automatically when app.py starts.
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "dashboard.db")


def get_db():
    """Return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create feedback tables if they don't already exist."""
    conn = get_db()
    cursor = conn.cursor()

    # ── Table 1: Events ──────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker_name TEXT    NOT NULL,
            venue_date   TEXT    NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Table 2: Feedback Forms (Google Form links) ───────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_forms (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id       INTEGER NOT NULL,
            google_form_id TEXT    NOT NULL UNIQUE,
            google_form_url TEXT   NOT NULL,
            google_edit_url TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    # ── Table 3: Student Submissions ─────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_submissions (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id           INTEGER NOT NULL,
            form_id            INTEGER NOT NULL,
            student_name       TEXT,
            department         TEXT,
            roll_no            TEXT,
            year               TEXT,
            helpfulness_rating INTEGER,
            valuable_aspect    TEXT,
            improvements       TEXT,
            future_topics      TEXT,
            raw_answers        TEXT,
            submitted_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (form_id)  REFERENCES feedback_forms(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Feedback tables initialised successfully.")


if __name__ == "__main__":
    init_db()
    print("[DB] Done.")
