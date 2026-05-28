"""
AI Insights Page Error Detector — NLP service, insight payload checks.
"""
from __future__ import annotations
from typing import List
from ..base import ErrorDetector, DetectionResult


class InsightsErrorDetector(ErrorDetector):
    page = "insights"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []

        # 1. NLP service importable
        try:
            from backend.services.nlp_service import NLPService  # noqa
            results.append(self._ok("nlp_import", "NLPService importable"))
        except ImportError as e:
            results.append(self._critical("nlp_import", "NLPService cannot be imported", str(e)))

        # 2. KPI service importable (insights depend on it)
        try:
            from backend.services.kpi_service import KPIService  # noqa
            results.append(self._ok("kpi_import", "KPIService importable"))
        except ImportError as e:
            results.append(self._critical("kpi_import", "KPIService cannot be imported", str(e)))

        # 3. Check that at least some DL-processed rows exist (insights need them)
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = {row[1] for row in cursor.fetchall()}
            if "dl_processed" in cols:
                cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE dl_processed = 1")
                processed = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM dashboard_data")
                total = cursor.fetchone()[0]
                conn.close()
                if processed == 0 and total > 0:
                    results.append(self._warn("dl_processed_count",
                        "No DL-processed rows — AI insights will be generic",
                        "DL worker may not have run yet"))
                else:
                    results.append(self._ok("dl_processed_count", f"{processed}/{total} rows DL-processed"))
            else:
                conn.close()
                results.append(self._warn("dl_processed_count", "dl_processed column missing — cannot verify NLP coverage"))
        except Exception as e:
            results.append(self._warn("dl_processed_count", "Could not check DL processing status", str(e)))

        return results
