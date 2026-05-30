"""
Speakers Page Error Detector.
"""
from __future__ import annotations
from typing import List
from ..base import ErrorDetector, DetectionResult
from backend.utils.insforge_db import get_db, execute_one


class SpeakersErrorDetector(ErrorDetector):
    page = "speakers"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    # 1. alumni_speaker_name column exists
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'events'")
                    cols = {row["column_name"] for row in cursor.fetchall()}

                    if "speaker_name" not in cols:
                        results.append(self._critical("speaker_column",
                            "speaker_name column missing in events table — Speakers page will be empty"))
                        return results
                    results.append(self._ok("speaker_column", "speaker_name column present"))

                    # 2. At least one speaker exists
                    cursor.execute("SELECT COUNT(DISTINCT speaker_name) as cnt FROM events WHERE speaker_name IS NOT NULL")
                    speaker_res = cursor.fetchone()
                    speaker_count = int(speaker_res["cnt"]) if speaker_res and speaker_res["cnt"] is not None else 0
                    if speaker_count == 0:
                        results.append(self._warn("speaker_data", "No speaker names found in data"))
                    else:
                        results.append(self._ok("speaker_data", f"{speaker_count} unique speakers found"))

                    # 3. Rating column present
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'feedback_responses'")
                    cols = {row["column_name"] for row in cursor.fetchall()}
                    
                    if "session_rating" not in cols:
                        results.append(self._warn("rating_column", "session_rating column missing — speaker ratings unavailable"))
                    else:
                        results.append(self._ok("rating_column", "session_rating column present"))

                    # 4. Sentiment score range check (dl_sentiment_score should be -1 to 1)
                    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'feedback_analysis'")
                    analysis_cols = {row["column_name"] for row in cursor.fetchall()}

                    if "dl_sentiment_score" in analysis_cols:
                        cursor.execute("""
                            SELECT COUNT(*) as cnt FROM feedback_analysis
                            WHERE dl_sentiment_score IS NOT NULL
                            AND (CAST(dl_sentiment_score AS REAL) < -1.0 OR CAST(dl_sentiment_score AS REAL) > 1.0)
                        """)
                        range_res = cursor.fetchone()
                        out_of_range = int(range_res["cnt"]) if range_res and range_res["cnt"] is not None else 0
                        if out_of_range > 0:
                            results.append(self._warn("sentiment_range",
                                f"{out_of_range} rows have dl_sentiment_score outside [-1, 1]",
                                "Speaker sentiment averages may be skewed"))
                        else:
                            results.append(self._ok("sentiment_range", "dl_sentiment_score values are in valid range"))
                    else:
                        results.append(self._warn("sentiment_range", "dl_sentiment_score column missing from feedback_analysis"))

        except Exception as e:
            results.append(self._critical("speakers_check", "Speakers error detection failed", str(e)))

        return results
