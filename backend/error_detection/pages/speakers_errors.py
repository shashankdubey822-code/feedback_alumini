"""
Speakers Page Error Detector.
"""
from __future__ import annotations
from backend.utils import pg_helper as sqlite3
from typing import List
from ..base import ErrorDetector, DetectionResult


class SpeakersErrorDetector(ErrorDetector):
    page = "speakers"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. alumni_speaker_name column exists
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = {row["name"] for row in cursor.fetchall()}

            if "alumni_speaker_name" not in cols:
                results.append(self._critical("speaker_column",
                    "alumni_speaker_name column missing — Speakers page will be empty"))
                conn.close()
                return results
            results.append(self._ok("speaker_column", "alumni_speaker_name column present"))

            # 2. At least one speaker exists
            cursor.execute("SELECT COUNT(DISTINCT alumni_speaker_name) as cnt FROM dashboard_data WHERE alumni_speaker_name IS NOT NULL AND alumni_speaker_name != ''")
            speaker_count = cursor.fetchone()["cnt"]
            if speaker_count == 0:
                results.append(self._warn("speaker_data", "No speaker names found in data"))
            else:
                results.append(self._ok("speaker_data", f"{speaker_count} unique speakers found"))

            # 3. Rating column present
            if "session_rating" not in cols:
                results.append(self._warn("rating_column", "session_rating column missing — speaker ratings unavailable"))
            else:
                results.append(self._ok("rating_column", "session_rating column present"))

            # 4. Sentiment score range check (dl_sentiment_score should be -1 to 1)
            if "dl_sentiment_score" in cols:
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM dashboard_data
                    WHERE dl_sentiment_score IS NOT NULL
                    AND (CAST(dl_sentiment_score AS REAL) < -1.0 OR CAST(dl_sentiment_score AS REAL) > 1.0)
                """)
                out_of_range = cursor.fetchone()["cnt"]
                if out_of_range > 0:
                    results.append(self._warn("sentiment_range",
                        f"{out_of_range} rows have dl_sentiment_score outside [-1, 1]",
                        "Speaker sentiment averages may be skewed"))
                else:
                    results.append(self._ok("sentiment_range", "dl_sentiment_score values are in valid range"))
            else:
                results.append(self._warn("sentiment_range", "dl_sentiment_score column missing"))

            conn.close()
        except Exception as e:
            results.append(self._critical("speakers_check", "Speakers error detection failed", str(e)))

        return results
