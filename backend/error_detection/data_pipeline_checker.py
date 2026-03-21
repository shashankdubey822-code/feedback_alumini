"""
Data Pipeline Checker - Validates full data flow from ingestion to NLP processing
"""

import sqlite3
from typing import Dict, List, Tuple

class DataPipelineChecker:
    """Check the complete data processing pipeline"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def check_data_ingestion(self) -> Dict:
        """Check if data is being ingested properly"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as cnt FROM dashboard_data")
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT form_source, COUNT(*) as cnt
                FROM dashboard_data
                GROUP BY form_source
            """)
            sources = {row[0]: row[1] for row in cursor.fetchall()}

            conn.close()

            return {
                "step": "Data Ingestion",
                "total_records": total,
                "by_source": sources,
                "status": "OK" if total > 0 else "NO_DATA"
            }
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def check_nlp_processing_queue(self) -> Dict:
        """Check for records waiting to be NLP processed"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM dashboard_data
                WHERE dl_processed = 0
            """)
            unprocessed = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM dashboard_data
                WHERE dl_processed = 1
            """)
            processed = cursor.fetchone()[0]

            conn.close()

            return {
                "step": "NLP Processing Queue",
                "waiting": unprocessed,
                "completed": processed,
                "status": "OK" if unprocessed + processed > 0 else "NO_DATA",
                "issue": "QUEUE_STUCK" if unprocessed > 100 and processed == 0 else None
            }
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def check_sentiment_extraction(self) -> Dict:
        """Check if sentiment data is being extracted"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM dashboard_data
                WHERE dl_sentiment_label IS NOT NULL
            """)
            with_sentiment = cursor.fetchone()[0]

            cursor.execute("""
                SELECT dl_sentiment_label, COUNT(*) as cnt
                FROM dashboard_data
                WHERE dl_sentiment_label IS NOT NULL
                GROUP BY dl_sentiment_label
            """)
            sentiment_dist = {row[0]: row[1] for row in cursor.fetchall()}

            conn.close()

            return {
                "step": "Sentiment Extraction",
                "records_with_sentiment": with_sentiment,
                "distribution": sentiment_dist,
                "status": "OK" if with_sentiment > 0 else "NO_SENTIMENT_DATA"
            }
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def check_keyword_extraction(self) -> Dict:
        """Check if keywords are being extracted"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM dashboard_data
                WHERE dl_keywords IS NOT NULL
            """)
            with_keywords = cursor.fetchone()[0]

            cursor.execute("""
                SELECT AVG(LENGTH(dl_keywords)) as avg_length
                FROM dashboard_data
                WHERE dl_keywords IS NOT NULL
            """)
            result = cursor.fetchone()
            avg_length = result[0] if result[0] else 0

            conn.close()

            return {
                "step": "Keyword Extraction",
                "records_with_keywords": with_keywords,
                "avg_keywords_length": avg_length,
                "status": "OK" if with_keywords > 0 else "NO_KEYWORDS"
            }
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def check_api_response(self) -> Dict:
        """Check if API would return NLP data"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check what the API would return
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN dl_sentiment_label = 'POSITIVE' THEN 1 ELSE 0 END) as positive_count,
                    SUM(CASE WHEN dl_sentiment_label = 'NEGATIVE' THEN 1 ELSE 0 END) as negative_count,
                    SUM(CASE WHEN dl_sentiment_label = 'NEUTRAL' THEN 1 ELSE 0 END) as neutral_count
                FROM dashboard_data
                WHERE dl_sentiment_label IS NOT NULL
            """)
            sentiment_summary = dict(cursor.fetchone())

            conn.close()

            return {
                "step": "API Response (NLP Data)",
                "sentiment_summary": sentiment_summary,
                "would_return_data": sentiment_summary['total'] > 0 if sentiment_summary['total'] else False
            }
        except sqlite3.DatabaseError as e:
            return {"error": str(e)}

    def full_pipeline_check(self) -> Dict:
        """Run full data pipeline check"""
        pipeline_steps = [
            self.check_data_ingestion(),
            self.check_nlp_processing_queue(),
            self.check_sentiment_extraction(),
            self.check_keyword_extraction(),
            self.check_api_response()
        ]

        # Determine overall health
        issues = []
        for step in pipeline_steps:
            status = step.get("status", "UNKNOWN")
            if status == "NO_DATA":
                issues.append(f"{step['step']}: No data found")
            elif status == "NO_SENTIMENT_DATA":
                issues.append(f"{step['step']}: No sentiment data extracted")
            elif step.get("issue") == "QUEUE_STUCK":
                issues.append(f"{step['step']}: Processing queue appears stuck")

        return {
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "pipeline_stages": pipeline_steps,
            "overall_status": "HEALTHY" if not issues else "ISSUES_DETECTED",
            "issues": issues,
            "recommendations": [
                "If no data is ingesting: Check /api/admin/upload_csv endpoint",
                "If queue is stuck: Background worker may have crashed",
                "If no sentiment/keywords: Wait for background worker to process (can take minutes)",
                "Check logs/app.log for worker errors"
            ]
        }
