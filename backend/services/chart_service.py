"""
Chart Service — Generate chart data using native Supabase PostgreSQL.
"""

from typing import Dict, List
from datetime import datetime, timedelta
from backend.utils.supabase_db import execute_all, execute_one


class ChartService:
    """Generate chart data from Supabase PostgreSQL."""

    def get_timeline_data(self, days: int = 30) -> List[Dict]:
        """Submissions per day for the last N days."""
        try:
            start_date = (datetime.utcnow() - timedelta(days=days)).date()
            rows = execute_all("""
                SELECT
                    DATE(submitted_at) AS date,
                    COUNT(*) AS count,
                    AVG(session_rating) AS avg_rating
                FROM feedback_responses
                WHERE DATE(submitted_at) >= %s
                GROUP BY DATE(submitted_at)
                ORDER BY date
            """, (start_date,))
            return [
                {
                    'date': str(r['date']),
                    'submissions': r['count'],
                    'average_rating': round(float(r['avg_rating']), 2) if r['avg_rating'] else None,
                }
                for r in rows
            ]
        except Exception as e:
            raise Exception(f"Error getting timeline data: {e}")

    def get_department_ratings(self) -> List[Dict]:
        """Average session rating grouped by department."""
        try:
            rows = execute_all("""
                SELECT
                    e.department,
                    COUNT(*) AS count,
                    AVG(r.session_rating) AS avg_rating
                FROM feedback_responses r
                LEFT JOIN events e ON r.event_id = e.id
                WHERE e.department IS NOT NULL AND e.department <> ''
                  AND r.session_rating IS NOT NULL
                GROUP BY e.department
                ORDER BY avg_rating DESC
            """)
            return [
                {
                    'department': r['department'],
                    'count': r['count'],
                    'average_rating': round(float(r['avg_rating']), 2),
                }
                for r in rows
            ]
        except Exception as e:
            raise Exception(f"Error getting department ratings: {e}")

    def get_speaker_statistics(self, limit: int = 10) -> List[Dict]:
        """Top speakers by number of feedback responses."""
        try:
            rows = execute_all("""
                SELECT
                    e.speaker_name AS alumni_speaker_name,
                    COUNT(*) AS session_count,
                    AVG(r.session_rating) AS avg_rating
                FROM feedback_responses r
                LEFT JOIN events e ON r.event_id = e.id
                WHERE e.speaker_name IS NOT NULL AND e.speaker_name <> ''
                GROUP BY e.speaker_name
                ORDER BY session_count DESC
                LIMIT %s
            """, (limit,))
            return [
                {
                    'speaker': r['alumni_speaker_name'],
                    'sessions': r['session_count'],
                    'average_rating': round(float(r['avg_rating']), 2) if r['avg_rating'] else None,
                }
                for r in rows
            ]
        except Exception as e:
            raise Exception(f"Error getting speaker statistics: {e}")

    def get_rating_pie_chart(self) -> List[Dict]:
        """Rating distribution (1–5) for doughnut chart."""
        try:
            rows = execute_all("""
                SELECT session_rating, COUNT(*) AS count
                FROM feedback_responses
                WHERE session_rating IS NOT NULL
                GROUP BY session_rating
                ORDER BY session_rating
            """)
            rating_labels = {
                1: '1 - Poor', 2: '2 - Fair', 3: '3 - Average',
                4: '4 - Good', 5: '5 - Excellent',
            }
            return [
                {
                    'label': rating_labels.get(r['session_rating'], f"Rating {r['session_rating']}"),
                    'value': r['count'],
                    'rating': r['session_rating'],
                }
                for r in rows
            ]
        except Exception as e:
            raise Exception(f"Error getting rating pie chart: {e}")

    def get_monthly_comparison(self) -> List[Dict]:
        """Monthly submission counts and avg rating — last 12 months."""
        try:
            rows = execute_all("""
                SELECT
                    TO_CHAR(submitted_at, 'YYYY-MM') AS month,
                    COUNT(*) AS count,
                    AVG(session_rating) AS avg_rating
                FROM feedback_responses
                WHERE submitted_at IS NOT NULL
                GROUP BY TO_CHAR(submitted_at, 'YYYY-MM')
                ORDER BY month DESC
                LIMIT 12
            """)
            results = [
                {
                    'month': r['month'],
                    'submissions': r['count'],
                    'average_rating': round(float(r['avg_rating']), 2) if r['avg_rating'] else None,
                }
                for r in rows
            ]
            return list(reversed(results))
        except Exception as e:
            raise Exception(f"Error getting monthly comparison: {e}")

    def get_all_chart_data(self) -> Dict:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                'timeline':            executor.submit(self.get_timeline_data),
                'department_ratings':  executor.submit(self.get_department_ratings),
                'speakers':            executor.submit(self.get_speaker_statistics),
                'rating_distribution': executor.submit(self.get_rating_pie_chart),
                'monthly_comparison':  executor.submit(self.get_monthly_comparison),
            }
            return {k: v.result() for k, v in futures.items()}
