"""
Chart Service - Generate chart data for visualizations
"""

from backend.utils import pg_helper as sqlite3
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from backend.utils.db_helper import get_db_connection


class ChartService:
    """Generate data for various charts and visualizations"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        """Get database connection"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_timeline_data(self, days: int = 30) -> List[Dict]:
        """Get timeline data for last N days"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Calculate date range
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            cursor.execute(
                'SELECT DATE(timestamp_normalized) as date, COUNT(*) as count, '
                'AVG(session_rating) as avg_rating '
                'FROM dashboard_data '
                'WHERE DATE(timestamp_normalized) BETWEEN ? AND ? '
                'GROUP BY DATE(timestamp_normalized) '
                'ORDER BY date',
                (str(start_date), str(end_date))
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'date': row['date'],
                    'submissions': row['count'],
                    'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else None,
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting timeline data: {str(e)}")

    def get_department_ratings(self) -> List[Dict]:
        """Get average rating by department"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT department_cleaned, COUNT(*) as count, AVG(session_rating) as avg_rating '
                'FROM dashboard_data '
                'WHERE department_cleaned IS NOT NULL AND department_cleaned != "" '
                'AND session_rating IS NOT NULL '
                'GROUP BY department_cleaned '
                'ORDER BY avg_rating DESC'
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'department': row['department_cleaned'],
                    'count': row['count'],
                    'average_rating': round(row['avg_rating'], 2),
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting department ratings: {str(e)}")

    def get_speaker_statistics(self, limit: int = 10) -> List[Dict]:
        """Get top speakers by number of sessions"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT alumni_speaker_name, COUNT(*) as session_count, AVG(session_rating) as avg_rating '
                'FROM dashboard_data '
                'WHERE alumni_speaker_name IS NOT NULL AND alumni_speaker_name != "" '
                'GROUP BY alumni_speaker_name '
                'ORDER BY session_count DESC '
                'LIMIT ?',
                (limit,)
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'speaker': row['alumni_speaker_name'],
                    'sessions': row['session_count'],
                    'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else None,
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting speaker statistics: {str(e)}")

    def get_rating_pie_chart(self) -> List[Dict]:
        """Get rating distribution for pie chart"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT session_rating, COUNT(*) as count FROM dashboard_data '
                'WHERE session_rating IS NOT NULL '
                'GROUP BY session_rating '
                'ORDER BY session_rating'
            )

            rating_labels = {
                1: '1 - Poor',
                2: '2 - Fair',
                3: '3 - Average',
                4: '4 - Good',
                5: '5 - Excellent',
            }

            results = []
            for row in cursor.fetchall():
                results.append({
                    'label': rating_labels.get(row['session_rating'], f'Rating {row["session_rating"]}'),
                    'value': row['count'],
                    'rating': row['session_rating'],
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting rating pie chart: {str(e)}")

    def get_monthly_comparison(self) -> List[Dict]:
        """Get monthly comparison data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT strftime("%Y-%m", timestamp_normalized) as month, '
                'COUNT(*) as count, AVG(session_rating) as avg_rating '
                'FROM dashboard_data '
                'WHERE timestamp_normalized IS NOT NULL '
                'GROUP BY month '
                'ORDER BY month DESC '
                'LIMIT 12'
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'month': row['month'],
                    'submissions': row['count'],
                    'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else None,
                })

            conn.close()
            return list(reversed(results))  # Return in chronological order
        except Exception as e:
            raise Exception(f"Error getting monthly comparison: {str(e)}")

    def get_all_chart_data(self) -> Dict:
        """Get all chart data at once"""
        return {
            'timeline': self.get_timeline_data(),
            'department_ratings': self.get_department_ratings(),
            'speakers': self.get_speaker_statistics(),
            'rating_distribution': self.get_rating_pie_chart(),
            'monthly_comparison': self.get_monthly_comparison(),
        }
