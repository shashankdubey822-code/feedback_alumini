"""
Overview Page Error Detector — KPI, filter, and data quality checks.
"""
from __future__ import annotations
import sqlite3
from typing import List
from .base import ErrorDetector, DetectionResult


class OverviewErrorDetector(ErrorDetector):
    page = "overview"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Empty data check
            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data")
            total = cursor.fetchone()["cnt"]
            if total == 0:
                results.append(self._critical("empty_data", "No records in dashboard_data — overview will be blank"))
                conn.close()
                return results
            results.append(self._ok("empty_data", f"{total} records available for overview"))

            # 2. KPI column type check — session_rating should be numeric
            cursor.execute("SELECT session_rating FROM dashboard_data WHERE session_rating IS NOT NULL LIMIT 20")
            rows = cursor.fetchall()
            bad = 0
            for r in rows:
                try:
                    float(r["session_rating"])
                except (TypeError, ValueError):
                    bad += 1
            if bad > 0:
                results.append(self._warn("kpi_column_type",
                    f"{bad}/20 sampled session_rating values are non-numeric",
                    "Average Rating KPI may be incorrect"))
            else:
                results.append(self._ok("kpi_column_type", "session_rating column is numeric"))

            # 3. Filter columns exist
            for col in ["department_cleaned", "alumni_speaker_name"]:
                cursor.execute(f"PRAGMA table_info(dashboard_data)")
                cols = {row["name"] for row in cursor.fetchall()}
                if col not in cols:
                    results.append(self._warn("filter_column", f"Filter column '{col}' missing — filter panel will be empty"))
                else:
                    results.append(self._ok("filter_column", f"Filter column '{col}' present"))

            # 4. Null timestamp check
            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data WHERE timestamp_normalized IS NULL OR timestamp_normalized = ''")
            null_ts = cursor.fetchone()["cnt"]
            if null_ts > total * 0.3:
                results.append(self._warn("timestamp_nulls",
                    f"{null_ts}/{total} rows have null timestamps",
                    "Time-trend chart may be incomplete"))
            else:
                results.append(self._ok("timestamp_nulls", f"Timestamp coverage acceptable ({total - null_ts}/{total})"))

            conn.close()
        except Exception as e:
            results.append(self._critical("overview_check", "Overview error detection failed", str(e)))

        return results
