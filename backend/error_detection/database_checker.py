"""
Database Checker - Validates database schema and data integrity
"""

import sqlite3
import os
from typing import List, Dict, Tuple

class DatabaseChecker:
    """Check database integrity, schema, and status"""

    REQUIRED_TABLES = ['dashboard_data', 'events']
    REQUIRED_COLUMNS_DASHBOARD = [
        'id', 'timestamp_original', 'timestamp_normalized', 'name_of_student',
        'department_original', 'department_cleaned', 'roll_no_original',
        'date_of_lecture', 'alumni_speaker_name', 'session_help_understanding',
        'session_rating', 'aspect_most_valuable', 'improvements_suggestions',
        'future_topics', 'form_source', 'record_status', 'cleaned_at',
        'dl_sentiment_score', 'dl_sentiment_label', 'dl_keywords', 'dl_processed'
    ]

    def __init__(self, db_path: str):
        self.db_path = db_path

    def check_database_exists(self) -> Tuple[bool, str]:
        """Check if database file exists"""
        exists = os.path.exists(self.db_path)
        if not exists:
            return False, f"Database not found at {self.db_path}"
        return True, "Database file exists"

    def check_tables_exist(self) -> Tuple[bool, List[str], List[str]]:
        """Check if all required tables exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            existing_tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            missing_tables = [t for t in self.REQUIRED_TABLES if t not in existing_tables]

            if missing_tables:
                return False, existing_tables, missing_tables

            return True, existing_tables, []
        except sqlite3.DatabaseError as e:
            return False, [], [str(e)]

    def check_schema_columns(self) -> Dict[str, dict]:
        """Check dashboard_data schema for required columns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(dashboard_data)")
            existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
            conn.close()

            schema_report = {}
            for col in self.REQUIRED_COLUMNS_DASHBOARD:
                if col in existing_columns:
                    schema_report[col] = {"status": "present", "type": existing_columns[col]}
                else:
                    schema_report[col] = {"status": "missing"}

            return schema_report
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def check_data_status(self) -> Dict:
        """Check data ingestion and processing status"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Overall counts
            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data")
            total_records = cursor.fetchone()['cnt']

            # Unprocessed records (for NLP)
            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data WHERE dl_processed = 0")
            unprocessed = cursor.fetchone()['cnt']

            # Processed records
            processed = total_records - unprocessed

            # Records with sentiment data
            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data WHERE dl_sentiment_label IS NOT NULL")
            with_sentiment = cursor.fetchone()['cnt']

            # Records with keywords
            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data WHERE dl_keywords IS NOT NULL")
            with_keywords = cursor.fetchone()['cnt']

            conn.close()

            return {
                "total_records": total_records,
                "processed": processed,
                "unprocessed": unprocessed,
                "with_sentiment": with_sentiment,
                "with_keywords": with_keywords,
                "nlp_completion_percentage": (processed / total_records * 100) if total_records > 0 else 0
            }
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def full_check(self) -> Dict:
        """Run comprehensive database check"""
        exists, msg = self.check_database_exists()
        tables_ok, existing_tables, missing_tables = self.check_tables_exist()
        schema = self.check_schema_columns()
        data_status = self.check_data_status()

        return {
            "database_exists": exists,
            "database_message": msg,
            "tables_ok": tables_ok,
            "existing_tables": existing_tables,
            "missing_tables": missing_tables,
            "schema": schema,
            "data_status": data_status
        }
