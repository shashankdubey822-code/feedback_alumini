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
            from backend.utils.supabase_db import execute_one
            row_total = execute_one("SELECT COUNT(*) as count FROM feedback_responses")
            row_processed = execute_one("SELECT COUNT(*) as count FROM feedback_analysis")
            
            total = row_total['count'] if row_total else 0
            processed = row_processed['count'] if row_processed else 0
            
            if processed == 0 and total > 0:
                results.append(self._warn("dl_processed_count",
                    "No DL-processed rows — AI insights will be generic",
                    "DL worker may not have run yet"))
            else:
                results.append(self._ok("dl_processed_count", f"{processed}/{total} rows DL-processed"))
        except Exception as e:
            results.append(self._warn("dl_processed_count", "Could not check DL processing status", str(e)))

        return results
