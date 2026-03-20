"""
Time Trend Service - Temporal analysis and trend detection
"""

import sqlite3
from typing import Dict, List
from datetime import datetime, timedelta


class TimeTrendService:
    """Analyze trends over time"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_daily_trend(self, days: int = 30) -> List[Dict]:
        """Get daily submission trend"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            cursor.execute(
                'SELECT DATE(timestamp_normalized) as date, COUNT(*) as submissions '
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
                    'submissions': row['submissions'],
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting daily trend: {str(e)}")

    def get_weekly_trend(self, weeks: int = 12) -> List[Dict]:
        """Get weekly submission trend"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(weeks=weeks)

            cursor.execute(
                'SELECT strftime("%Y-W%W", timestamp_normalized) as week, COUNT(*) as submissions '
                'FROM dashboard_data '
                'WHERE timestamp_normalized >= ? '
                'GROUP BY week '
                'ORDER BY week',
                (str(start_date),)
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'week': row['week'],
                    'submissions': row['submissions'],
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting weekly trend: {str(e)}")

    def get_monthly_trend(self, months: int = 12) -> List[Dict]:
        """Get monthly submission trend"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT strftime("%Y-%m", timestamp_normalized) as month, '
                'COUNT(*) as submissions, AVG(session_rating) as avg_rating '
                'FROM dashboard_data '
                'WHERE timestamp_normalized IS NOT NULL '
                'GROUP BY month '
                'ORDER BY month DESC '
                'LIMIT ?',
                (months,)
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'month': row['month'],
                    'submissions': row['submissions'],
                    'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else None,
                })

            conn.close()
            return list(reversed(results))  # Chronological order
        except Exception as e:
            raise Exception(f"Error getting monthly trend: {str(e)}")

    def get_rating_trend(self, days: int = 30) -> List[Dict]:
        """Get rating trend over time"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            cursor.execute(
                'SELECT DATE(timestamp_normalized) as date, AVG(session_rating) as avg_rating '
                'FROM dashboard_data '
                'WHERE DATE(timestamp_normalized) BETWEEN ? AND ? AND session_rating IS NOT NULL '
                'GROUP BY DATE(timestamp_normalized) '
                'ORDER BY date',
                (str(start_date), str(end_date))
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'date': row['date'],
                    'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else None,
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting rating trend: {str(e)}")

    def get_submission_peak_hours(self) -> List[Dict]:
        """Get peak submission hours"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT strftime("%H", timestamp_normalized) as hour, COUNT(*) as submissions '
                'FROM dashboard_data '
                'WHERE timestamp_normalized IS NOT NULL '
                'GROUP BY hour '
                'ORDER BY submissions DESC'
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'hour': f"{row['hour']}:00",
                    'submissions': row['submissions'],
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting submission peak hours: {str(e)}")

    def get_submission_peak_days(self) -> List[Dict]:
        """Get peak submission days of week"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT strftime("%w", timestamp_normalized) as day_num, COUNT(*) as submissions '
                'FROM dashboard_data '
                'WHERE timestamp_normalized IS NOT NULL '
                'GROUP BY day_num '
                'ORDER BY submissions DESC'
            )

            day_names = {
                '0': 'Sunday',
                '1': 'Monday',
                '2': 'Tuesday',
                '3': 'Wednesday',
                '4': 'Thursday',
                '5': 'Friday',
                '6': 'Saturday',
            }

            results = []
            for row in cursor.fetchall():
                results.append({
                    'day': day_names.get(row['day_num']),
                    'submissions': row['submissions'],
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting submission peak days: {str(e)}")

    def get_all_trends(self) -> Dict:
        """Get all trend data"""
        return {
            'daily': self.get_daily_trend(),
            'weekly': self.get_weekly_trend(),
            'monthly': self.get_monthly_trend(),
            'rating_trend': self.get_rating_trend(),
            'peak_hours': self.get_submission_peak_hours(),
            'peak_days': self.get_submission_peak_days(),
        }
