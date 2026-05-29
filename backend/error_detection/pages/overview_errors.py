"""
Overview Page Error Detector — KPI, filter, and data quality checks.
"""
from __future__ import annotations
from typing import List
from ..base import ErrorDetector, DetectionResult
from backend.utils.supabase_db import get_db, execute_one


class OverviewErrorDetector(ErrorDetector):
    page = "overview"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    # 1. Empty data check
                    cursor.execute("SELECT COUNT(*) as cnt FROM feedback_responses")
                    total_res = cursor.fetchone()
                    total = total_res["cnt"] if total_res else 0
                    if total == 0:
                        results.append(self._critical("empty_data", "No records in feedback_responses — overview will be blank"))
                        return results
                    results.append(self._ok("empty_data", f"{total} records available for overview"))

                    # 2. KPI column type check — session_rating should be numeric
                    cursor.execute("SELECT session_rating FROM feedback_responses WHERE session_rating IS NOT NULL LIMIT 20")
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
                    for tbl, col in [("feedback_responses", "department_cleaned"), ("events", "speaker_name")]:
                        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tbl}'")
                        cols = {row["column_name"] for row in cursor.fetchall()}
                        if col not in cols:
                            results.append(self._warn("filter_column", f"Filter column '{col}' missing in {tbl} — filter panel will be empty"))
                        else:
                            results.append(self._ok("filter_column", f"Filter column '{col}' present in {tbl}"))

                    # 4. Null timestamp check
                    cursor.execute("SELECT COUNT(*) as cnt FROM feedback_responses WHERE timestamp_normalized IS NULL")
                    null_ts_res = cursor.fetchone()
                    null_ts = null_ts_res["cnt"] if null_ts_res else 0
                    if null_ts > total * 0.3:
                        results.append(self._warn("timestamp_nulls",
                            f"{null_ts}/{total} rows have null timestamps",
                            "Time-trend chart may be incomplete"))
                    else:
                        results.append(self._ok("timestamp_nulls", f"Timestamp coverage acceptable ({total - null_ts}/{total})"))

        except Exception as e:
            results.append(self._critical("overview_check", "Overview error detection failed", str(e)))

        return results
