"""
DB Error Detector — connectivity, schema, required columns.
"""
from __future__ import annotations
from typing import List
from ..base import ErrorDetector, DetectionResult
from backend.utils.supabase_db import get_conn, execute_one


REQUIRED_COLUMNS = [
    "id", "timestamp_normalized", "department_cleaned",
    "session_rating", "dl_processed"
]

REQUIRED_TABLES = ["feedback_responses", "events"]


class DBErrorDetector(ErrorDetector):
    page = "database"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []

        # 1. Connectivity
        try:
            execute_one("SELECT 1")
            results.append(self._ok("connectivity", "Database connection successful"))
        except Exception as e:
            results.append(self._critical("connectivity", "Cannot connect to database", str(e)))
            return results  # No point running further checks

        # 2. Required tables
        try:
            with get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
                    existing = {row["table_name"] for row in cursor.fetchall()}
            for tbl in REQUIRED_TABLES:
                if tbl in existing:
                    results.append(self._ok("table_exists", f"Table '{tbl}' exists"))
                else:
                    results.append(self._critical("table_exists", f"Required table '{tbl}' missing"))
        except Exception as e:
            results.append(self._critical("table_schema", "Failed to read table list", str(e)))
            return results

        # 3. Required columns
        try:
            with get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'feedback_responses'")
                    cols = {row["column_name"] for row in cursor.fetchall()}
            missing = [c for c in REQUIRED_COLUMNS if c not in cols]
            if missing:
                results.append(self._warn("required_columns",
                    f"Missing columns: {', '.join(missing)}",
                    "Some features may not work correctly"))
            else:
                results.append(self._ok("required_columns", "All required columns present"))
        except Exception as e:
            results.append(self._warn("required_columns", "Could not verify columns", str(e)))

        # 4. Row count sanity
        try:
            res = execute_one("SELECT COUNT(*) as count FROM feedback_responses")
            count = res["count"] if res else 0
            if count == 0:
                results.append(self._warn("row_count", "feedback_responses table is empty"))
            else:
                results.append(self._ok("row_count", f"{count} rows in feedback_responses"))
        except Exception as e:
            results.append(self._warn("row_count", "Could not count rows", str(e)))

        return results
