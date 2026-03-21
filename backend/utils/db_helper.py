"""
Database connection helper to prevent locking issues
"""
import os
import sqlite3


def get_db_connection(db_path, timeout=30.0):
    """
    Create a database connection with proper timeout and WAL mode
    
    Args:
        db_path: Path to the SQLite database file
        timeout: Timeout in seconds for database locks (default: 30.0)
        
    Returns:
        sqlite3.Connection: Database connection with optimized settings
    """
    conn = sqlite3.connect(db_path, timeout=timeout, check_same_thread=False)
    # Enable Write-Ahead Logging for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    # Set busy timeout
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn


def initialize_database(app, logger):
    """Initialize database on application startup"""
    try:
        db_path = app.config.get('DATABASE_PATH', 'database/dashboard.db')

        # Create database directory if it doesn't exist (and if there is a directory specified)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Connect to database using our helper
        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        # Check if table exists and has correct columns
        cursor.execute("PRAGMA table_info(dashboard_data)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # If table doesn't exist or is missing critical modern columns, recreate it
        if not columns or 'form_source' not in columns:
            logger.info("Initializing/Repairing dashboard_data table...")
            cursor.execute("DROP TABLE IF EXISTS dashboard_data")
            cursor.execute('''
                CREATE TABLE dashboard_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_original TEXT,
                    timestamp_normalized TEXT,
                    name_of_student TEXT,
                    name_normalized TEXT,
                    department_original TEXT,
                    department_cleaned TEXT,
                    roll_no_original TEXT,
                    roll_no_cleaned TEXT,
                    date_of_lecture TEXT,
                    alumni_speaker_name TEXT,
                    session_help_understanding TEXT,
                    session_rating INTEGER,
                    session_technical_clarity INTEGER,
                    aspect_most_valuable TEXT,
                    improvements_suggestions TEXT,
                    future_topics TEXT,
                    form_source TEXT,
                    data_quality_score REAL,
                    is_duplicate_flag INTEGER DEFAULT 0,
                    record_status TEXT,
                    cleaned_at TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    dl_sentiment_score REAL,
                    dl_sentiment_label TEXT,
                    dl_keywords TEXT,
                    dl_topic_id INTEGER,
                    dl_processed INTEGER DEFAULT 0
                )
            ''')
        
        # Add new DL columns if they don't exist but the table does
        if columns and 'form_source' in columns:
            dl_columns = {
                'dl_sentiment_score': 'REAL',
                'dl_sentiment_label': 'TEXT',
                'dl_keywords': 'TEXT',
                'dl_topic_id': 'INTEGER',
                'dl_processed': 'INTEGER DEFAULT 0'
            }
            for col_name, col_type in dl_columns.items():
                if col_name not in columns:
                    logger.info(f"Adding column {col_name} to dashboard_data")
                    cursor.execute(f"ALTER TABLE dashboard_data ADD COLUMN {col_name} {col_type}")
        
        # Ensure events table exists
        cursor.execute("PRAGMA table_info(events)")
        event_cols = [row[1] for row in cursor.fetchall()]
        if not event_cols:
            logger.info("Creating events table...")
            cursor.execute('''
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_name TEXT NOT NULL,
                    venue_date TEXT NOT NULL,
                    form_id TEXT,
                    form_url TEXT,
                    form_edit_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        conn.commit()
        conn.close()
        logger.info("Database schema verified and ready")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
