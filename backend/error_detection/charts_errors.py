"""
Charts Page Error Detector — chart data shape and payload validation.
"""
from __future__ import annotations
import sqlite3
from typing import List
from .base import ErrorDetector, DetectionResult


class ChartsErrorDetector(ErrorDetector):
    page = "charts"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []
        try:
            from backend.services.chart_service import ChartService
            svc = ChartService(self.db_path)
            charts = svc.get_all_chart_data()

            if not charts:
                results.append(self._warn("chart_payload", "ChartService returned empty payload"))
                return results

            results.append(self._ok("chart_payload", f"ChartService returned {len(charts)} chart groups"))

            # Validate each chart group
            for key, data in charts.items():
                if not isinstance(data, list):
                    results.append(self._warn("chart_shape", f"Chart '{key}' is not a list", f"type={type(data).__name__}"))
                    continue
                if len(data) == 0:
                    results.append(self._warn("chart_empty", f"Chart '{key}' has no data points"))
                    continue
                # Check first item has expected keys
                sample = data[0]
                if not isinstance(sample, dict):
                    results.append(self._warn("chart_item_shape", f"Chart '{key}' items are not dicts"))
                else:
                    results.append(self._ok("chart_shape", f"Chart '{key}' has {len(data)} items with valid shape"))

        except Exception as e:
            results.append(self._critical("chart_service", "ChartService failed to run", str(e)))

        # Check session_rating column exists and has data
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE session_rating IS NOT NULL AND session_rating != ''")
            rated = cursor.fetchone()[0]
            conn.close()
            if rated == 0:
                results.append(self._warn("rating_data", "No session_rating data — rating distribution chart will be empty"))
            else:
                results.append(self._ok("rating_data", f"{rated} rows have session_rating values"))
        except Exception as e:
            results.append(self._warn("rating_data", "Could not verify rating data", str(e)))

        return results
