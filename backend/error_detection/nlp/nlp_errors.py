"""
NLP / Deep Learning Page Error Detector.
"""
from __future__ import annotations
from backend.utils.insforge_db import get_db, execute_one
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
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'feedback_analysis'")
                    cols = {row["column_name"] for row in cursor.fetchall()}
                    
            if "processed_at" in cols:
                # rows in feedback_responses not in feedback_analysis
                backlog_res = execute_one("""
                    SELECT COUNT(*) as count 
                    FROM feedback_responses r 
                    LEFT JOIN feedback_analysis a ON r.id = a.response_id 
                    WHERE a.response_id IS NULL
                """)
                backlog = backlog_res["count"] if backlog_res else 0
                if backlog > 50:
                    results.append(self._warn("dl_backlog",
                        f"{backlog} rows pending DL processing",
                        "NLP analysis may be incomplete"))
                else:
                    results.append(self._ok("dl_backlog", f"DL backlog is manageable ({backlog} pending)"))
            else:
                results.append(self._warn("dl_backlog", "feedback_analysis table structure missing"))
        except Exception as e:
            results.append(self._warn("dl_backlog", "Could not check DL backlog", str(e)))

        # 3. Sentiment data present
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'feedback_analysis'")
                    cols = {row["column_name"] for row in cursor.fetchall()}
                    
            if "sentiment_label" in cols:
                sent_res = execute_one("SELECT COUNT(*) as count FROM feedback_analysis WHERE sentiment_label IS NOT NULL")
                sent_count = sent_res["count"] if sent_res else 0
                if sent_count == 0:
                    results.append(self._warn("sentiment_data", "No sentiment labels found — NLP section will be empty"))
                else:
                    results.append(self._ok("sentiment_data", f"{sent_count} rows have sentiment labels"))
            else:
                results.append(self._warn("sentiment_data", "sentiment_label column missing"))
        except Exception as e:
            results.append(self._warn("sentiment_data", "Could not verify sentiment data", str(e)))

        # 4. Keyword JSON validity (sample 10 rows)
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'feedback_analysis'")
                    cols = {row["column_name"] for row in cursor.fetchall()}
                    
            if "keywords_json" in cols:
                with get_db() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT keywords_json FROM feedback_analysis WHERE keywords_json IS NOT NULL LIMIT 10")
                        rows = cursor.fetchall()
                bad = 0
                for r in rows:
                    kw_val = r["keywords_json"]
                    if not isinstance(kw_val, (dict, list)):
                        try:
                            if isinstance(kw_val, str):
                                json.loads(kw_val)
                            else:
                                bad += 1
                        except Exception:
                            bad += 1
                if bad > 0:
                    results.append(self._warn("keyword_json", f"{bad}/10 sampled keywords_json rows have invalid JSON"))
                else:
                    results.append(self._ok("keyword_json", "keywords_json is valid in sampled rows"))
            else:
                results.append(self._warn("keyword_json", "keywords_json column missing"))
        except Exception as e:
            results.append(self._warn("keyword_json", "Could not validate keyword JSON", str(e)))

        return results
