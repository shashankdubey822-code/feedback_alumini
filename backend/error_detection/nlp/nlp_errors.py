"""
NLP / Deep Learning Page Error Detector.
"""
from __future__ import annotations
import sqlite3
import json
from typing import List
from ..base import ErrorDetector, DetectionResult


class NLPErrorDetector(ErrorDetector):
    page = "nlp"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []

        # 1. DL worker thread alive
        try:
            from backend.services.dl_worker import _dl_thread
            if _dl_thread is not None and _dl_thread.is_alive():
                results.append(self._ok("dl_worker_alive", "DL worker thread is running"))
            else:
                results.append(self._warn("dl_worker_alive", "DL worker thread is not running",
                    "New submissions will not be processed until restart"))
        except ImportError:
            results.append(self._warn("dl_worker_alive", "Could not import dl_worker to check thread status"))
        except Exception as e:
            results.append(self._warn("dl_worker_alive", "DL worker status check failed", str(e)))

        # 2. Unprocessed backlog
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = {row[1] for row in cursor.fetchall()}
            if "dl_processed" in cols:
                cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE dl_processed = 0")
                backlog = cursor.fetchone()[0]
                conn.close()
                if backlog > 50:
                    results.append(self._warn("dl_backlog",
                        f"{backlog} rows pending DL processing",
                        "NLP analysis may be incomplete"))
                else:
                    results.append(self._ok("dl_backlog", f"DL backlog is manageable ({backlog} pending)"))
            else:
                conn.close()
                results.append(self._warn("dl_backlog", "dl_processed column missing"))
        except Exception as e:
            results.append(self._warn("dl_backlog", "Could not check DL backlog", str(e)))

        # 3. Sentiment data present
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = {row[1] for row in cursor.fetchall()}
            if "dl_sentiment_label" in cols:
                cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE dl_sentiment_label IS NOT NULL AND dl_sentiment_label != ''")
                sent_count = cursor.fetchone()[0]
                conn.close()
                if sent_count == 0:
                    results.append(self._warn("sentiment_data", "No sentiment labels found — NLP section will be empty"))
                else:
                    results.append(self._ok("sentiment_data", f"{sent_count} rows have sentiment labels"))
            else:
                conn.close()
                results.append(self._warn("sentiment_data", "dl_sentiment_label column missing"))
        except Exception as e:
            results.append(self._warn("sentiment_data", "Could not verify sentiment data", str(e)))

        # 4. Keyword JSON validity (sample 10 rows)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = {row[1] for row in cursor.fetchall()}
            if "dl_keywords" in cols:
                cursor.execute("SELECT dl_keywords FROM dashboard_data WHERE dl_keywords IS NOT NULL LIMIT 10")
                rows = cursor.fetchall()
                conn.close()
                bad = 0
                for (kw_str,) in rows:
                    try:
                        json.loads(kw_str)
                    except Exception:
                        bad += 1
                if bad > 0:
                    results.append(self._warn("keyword_json", f"{bad}/10 sampled dl_keywords rows have invalid JSON"))
                else:
                    results.append(self._ok("keyword_json", "dl_keywords JSON is valid in sampled rows"))
            else:
                conn.close()
                results.append(self._warn("keyword_json", "dl_keywords column missing"))
        except Exception as e:
            results.append(self._warn("keyword_json", "Could not validate keyword JSON", str(e)))

        return results
