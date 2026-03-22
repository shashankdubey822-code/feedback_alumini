"""
DB Error Detector — connectivity, schema, required columns.
"""
from __future__ import annotations
import sqlite3
from typing import List
from .base import ErrorDetector, DetectionResult

REQUIRED_COLUMNS = [
    "id", "timestamp_normalized", "department_cleaned",
    "alumni_speaker_name", "session_rating", "dl_processed",
]

REQUIRED_TABLES = ["dashboard_data"]


class DBErrorDetector(ErrorDetector):
    page = "database"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []

        # 1. Connectivity
        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            conn.execute("SELECT 1")
            conn.close()
            results.append(self._ok("connectivity", "Database connection successful"))
        except Exception as e:
            results.append(self._critical("connectivity", "Cannot connect to database", str(e)))
            return results  # No point running further checks

        # 2. Required tables
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {row[0] for row in cursor.fetchall()}
            conn.close()
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = {row[1] for row in cursor.fetchall()}
            conn.close()
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM dashboard_data")
            count = cursor.fetchone()[0]
            conn.close()
            if count == 0:
                results.append(self._warn("row_count", "dashboard_data table is empty"))
            else:
                results.append(self._ok("row_count", f"{count} rows in dashboard_data"))
        except Exception as e:
            results.append(self._warn("row_count", "Could not count rows", str(e)))

        return results
