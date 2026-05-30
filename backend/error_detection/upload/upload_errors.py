"""
Upload Page Error Detector — file handling, DB insert, Google Sheets.
"""
from __future__ import annotations
import os
from typing import List
from ..base import ErrorDetector, DetectionResult


class UploadErrorDetector(ErrorDetector):
    page = "upload"

    def __init__(self, upload_dir: str, db_path: str):
        self.upload_dir = upload_dir
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []

        # 1. Upload directory exists and is writable
        if not os.path.exists(self.upload_dir):
            results.append(self._critical("upload_dir", f"Upload directory missing: {self.upload_dir}"))
        elif not os.access(self.upload_dir, os.W_OK):
            results.append(self._critical("upload_dir", f"Upload directory not writable: {self.upload_dir}"))
        else:
            results.append(self._ok("upload_dir", f"Upload directory accessible: {self.upload_dir}"))

        # 2. DB writable (needed for CSV insert)
        if os.path.exists(self.db_path):
            if not os.access(self.db_path, os.W_OK):
                results.append(self._critical("db_writable", "Database file is not writable — CSV upload will fail"))
            else:
                results.append(self._ok("db_writable", "Database file is writable"))
        else:
            results.append(self._warn("db_writable", f"Database file not found at: {self.db_path}"))

        # 3. pandas importable (required for CSV parsing)
        try:
            import pandas  # noqa
            results.append(self._ok("pandas_import", f"pandas {pandas.__version__} available"))
        except ImportError:
            results.append(self._critical("pandas_import", "pandas not installed — CSV upload will fail"))

        # 4. Apps Script URL configured
        apps_script_url = os.getenv("APPS_SCRIPT_URL", "")
        if not apps_script_url or apps_script_url.startswith("YOUR_"):
            results.append(self._warn("apps_script_url",
                "APPS_SCRIPT_URL not configured",
                "Google Sheets fetch will not work"))
        else:
            results.append(self._ok("apps_script_url", "APPS_SCRIPT_URL is configured"))

        return results
