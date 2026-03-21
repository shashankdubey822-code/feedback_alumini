"""
Analytics service - Core analytics calculations and aggregations
"""

import sqlite3
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import Counter
from backend.utils.db_helper import get_db_connection


class AnalyticsService:
    """Handle analytics queries and calculations"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        """Get database connection"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_total_records(self) -> int:
        """Get total number of feedback records"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM dashboard_data')
            result = cursor.fetchone()
            conn.close()
            return result['count'] if result else 0
        except Exception as e:
            raise Exception(f"Error getting total records: {str(e)}")

    def get_average_rating(self) -> Optional[float]:
        """Calculate average session rating"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT AVG(session_rating) as avg_rating FROM dashboard_data WHERE session_rating IS NOT NULL'
            )
            result = cursor.fetchone()
            conn.close()
            return round(result['avg_rating'], 2) if result and result['avg_rating'] else None
        except Exception as e:
            raise Exception(f"Error calculating average rating: {str(e)}")

    def get_department_distribution(self) -> Dict[str, int]:
        """Get feedback count by department"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT department_cleaned, COUNT(*) as count FROM dashboard_data '
                'WHERE department_cleaned IS NOT NULL AND department_cleaned != "" '
                'GROUP BY department_cleaned ORDER BY count DESC'
            )
            results = cursor.fetchall()
            conn.close()
            return {row['department_cleaned']: row['count'] for row in results}
        except Exception as e:
            raise Exception(f"Error getting department distribution: {str(e)}")

    def get_rating_distribution(self) -> Dict[int, int]:
        """Get distribution of session ratings"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT session_rating, COUNT(*) as count FROM dashboard_data '
                'WHERE session_rating IS NOT NULL '
                'GROUP BY session_rating ORDER BY session_rating'
            )
            results = cursor.fetchall()
            conn.close()
            return {row['session_rating']: row['count'] for row in results}
        except Exception as e:
            raise Exception(f"Error getting rating distribution: {str(e)}")

    def get_records_by_department(self, department: str, limit: int = 50) -> List[Dict]:
        """Get records for a specific department"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM dashboard_data WHERE department_cleaned = ? '
                'ORDER BY timestamp_normalized DESC LIMIT ?',
                (department, limit)
            )
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting records by department: {str(e)}")

    def get_records_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get records within a date range"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM dashboard_data WHERE timestamp_normalized BETWEEN ? AND ? '
                'ORDER BY timestamp_normalized DESC',
                (start_date, end_date)
            )
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting records by date range: {str(e)}")

    def get_data_quality_metrics(self) -> Dict:
        """Get data quality statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Quality scores
            cursor.execute('SELECT AVG(data_quality_score) as avg_quality FROM dashboard_data')
            avg_quality = cursor.fetchone()['avg_quality'] or 0

            # Missing fields
            cursor.execute(
                'SELECT '
                'COUNT(CASE WHEN roll_no_cleaned IS NULL OR roll_no_cleaned = "" THEN 1 END) as missing_roll, '
                'COUNT(CASE WHEN name_of_student IS NULL OR name_of_student = "" THEN 1 END) as missing_name, '
                'COUNT(CASE WHEN session_rating IS NULL THEN 1 END) as missing_rating, '
                'COUNT(CASE WHEN department_cleaned IS NULL OR department_cleaned = "" THEN 1 END) as missing_dept '
                'FROM dashboard_data'
            )
            missing = cursor.fetchone()

            # Duplicates
            cursor.execute('SELECT COUNT(*) as duplicate_count FROM dashboard_data WHERE is_duplicate_flag = 1')
            duplicates = cursor.fetchone()['duplicate_count']

            conn.close()

            return {
                'average_quality_score': round(avg_quality, 2),
                'missing_roll_numbers': missing['missing_roll'],
                'missing_names': missing['missing_name'],
                'missing_ratings': missing['missing_rating'],
                'missing_departments': missing['missing_dept'],
                'flagged_duplicates': duplicates,
            }
        except Exception as e:
            raise Exception(f"Error getting data quality metrics: {str(e)}")

    def get_statistics_summary(self) -> Dict:
        """Get comprehensive statistics summary"""
        return {
            'total_records': self.get_total_records(),
            'average_rating': self.get_average_rating(),
            'department_distribution': self.get_department_distribution(),
            'rating_distribution': self.get_rating_distribution(),
            'data_quality_metrics': self.get_data_quality_metrics(),
        }
