"""
KPI Service - Key Performance Indicators calculation and tracking
"""

from backend.utils import pg_helper as sqlite3
from typing import Dict, Optional
from datetime import datetime, timedelta
from backend.utils.db_helper import get_db_connection


class KPIService:
    """Calculate and track key performance indicators"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        """Get database connection"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_engagement_rate(self) -> float:
        """Calculate feedback engagement rate (feedback provided vs total records)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT '
                'COUNT(*) as total, '
                'COUNT(CASE WHEN (aspect_most_valuable IS NOT NULL AND aspect_most_valuable != "") '
                'OR (improvements_suggestions IS NOT NULL AND improvements_suggestions != "") THEN 1 END) as with_feedback '
                'FROM dashboard_data'
            )

            result = cursor.fetchone()
            conn.close()

            total = result['total']
            with_feedback = result['with_feedback']

            if total == 0:
                return 0.0

            return round((with_feedback / total) * 100, 2)
        except Exception as e:
            raise Exception(f"Error calculating engagement rate: {str(e)}")

    def calculate_satisfaction_score(self) -> float:
        """Calculate overall satisfaction (based on ratings > 3)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT '
                'COUNT(*) as total_rated, '
                'COUNT(CASE WHEN session_rating >= 4 THEN 1 END) as satisfied '
                'FROM dashboard_data '
                'WHERE session_rating IS NOT NULL'
            )

            result = cursor.fetchone()
            conn.close()

            total = result['total_rated']
            satisfied = result['satisfied']

            if total == 0:
                return 0.0

            return round((satisfied / total) * 100, 2)
        except Exception as e:
            raise Exception(f"Error calculating satisfaction score: {str(e)}")

    def calculate_completion_rate(self) -> float:
        """Calculate form completion rate (all required fields filled)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT '
                'COUNT(*) as total, '
                'COUNT(CASE WHEN '
                '(name_of_student IS NOT NULL AND name_of_student != "") AND '
                '(department_cleaned IS NOT NULL AND department_cleaned != "") AND '
                '(session_rating IS NOT NULL) THEN 1 END) as complete '
                'FROM dashboard_data'
            )

            result = cursor.fetchone()
            conn.close()

            total = result['total']
            complete = result['complete']

            if total == 0:
                return 0.0

            return round((complete / total) * 100, 2)
        except Exception as e:
            raise Exception(f"Error calculating completion rate: {str(e)}")

    def calculate_department_coverage(self) -> float:
        """Calculate percentage of departments covered"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT COUNT(DISTINCT department_cleaned) as unique_depts FROM dashboard_data '
                'WHERE department_cleaned IS NOT NULL AND department_cleaned != ""'
            )

            result = cursor.fetchone()
            conn.close()

            # Assuming we have around 40 standardized departments
            unique_depts = result['unique_depts']
            total_depts = 40  # From RESTRUCTURING_PLAN.md

            return round((unique_depts / total_depts) * 100, 2)
        except Exception as e:
            raise Exception(f"Error calculating department coverage: {str(e)}")

    def calculate_submission_velocity(self, days: int = 7) -> float:
        """Calculate average submissions per day (last N days)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            start_date = datetime.utcnow().date() - timedelta(days=days)

            cursor.execute(
                'SELECT COUNT(*) as count FROM dashboard_data '
                'WHERE DATE(timestamp_normalized) >= ?',
                (str(start_date),)
            )

            result = cursor.fetchone()
            conn.close()

            total_submissions = result['count']
            return round(total_submissions / days, 2)
        except Exception as e:
            raise Exception(f"Error calculating submission velocity: {str(e)}")

    def get_all_kpis(self) -> Dict:
        """Get all KPIs"""
        return {
            'engagement_rate': self.calculate_engagement_rate(),
            'satisfaction_score': self.calculate_satisfaction_score(),
            'completion_rate': self.calculate_completion_rate(),
            'department_coverage': self.calculate_department_coverage(),
            'submission_velocity_7d': self.calculate_submission_velocity(7),
            'submission_velocity_30d': self.calculate_submission_velocity(30),
        }

    def get_kpi_health_status(self) -> Dict:
        """Get health status of KPIs (green/yellow/red)"""
        kpis = self.get_all_kpis()

        status = {}
        thresholds = {
            'engagement_rate': {'green': 70, 'yellow': 50},
            'satisfaction_score': {'green': 80, 'yellow': 60},
            'completion_rate': {'green': 90, 'yellow': 75},
            'department_coverage': {'green': 90, 'yellow': 70},
        }

        for kpi_name, kpi_value in kpis.items():
            if kpi_name in thresholds:
                threshold = thresholds[kpi_name]
                if kpi_value >= threshold['green']:
                    health = 'GREEN'
                elif kpi_value >= threshold['yellow']:
                    health = 'YELLOW'
                else:
                    health = 'RED'
                status[kpi_name] = {
                    'value': kpi_value,
                    'health': health,
                }
            else:
                status[kpi_name] = {'value': kpi_value}

        return status
