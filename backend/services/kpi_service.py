"""
KPI Service — Key Performance Indicators using native Supabase PostgreSQL.
"""

from typing import Dict
from datetime import datetime, timedelta
from backend.utils.supabase_db import execute_one


class KPIService:
    """Calculate KPIs directly from Supabase PostgreSQL."""

    def calculate_engagement_rate(self) -> float:
        """% of responses that include written feedback."""
        try:
            row = execute_one("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE (aspect_most_valuable IS NOT NULL AND aspect_most_valuable <> '')
                           OR (improvements_suggestions IS NOT NULL AND improvements_suggestions <> '')
                    ) AS with_feedback
                FROM feedback_responses
            """)
            total = row['total'] or 0
            with_feedback = row['with_feedback'] or 0
            return round((with_feedback / total) * 100, 2) if total else 0.0
        except Exception as e:
            raise Exception(f"Error calculating engagement rate: {e}")

    def calculate_satisfaction_score(self) -> float:
        """% of rated responses with rating >= 4."""
        try:
            row = execute_one("""
                SELECT
                    COUNT(*) AS total_rated,
                    COUNT(*) FILTER (WHERE session_rating >= 4) AS satisfied
                FROM feedback_responses
                WHERE session_rating IS NOT NULL
            """)
            total = row['total_rated'] or 0
            satisfied = row['satisfied'] or 0
            return round((satisfied / total) * 100, 2) if total else 0.0
        except Exception as e:
            raise Exception(f"Error calculating satisfaction score: {e}")

    def calculate_completion_rate(self) -> float:
        """% of responses with all required fields filled."""
        try:
            row = execute_one("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE s.name IS NOT NULL AND s.name <> ''
                          AND e.department IS NOT NULL AND e.department <> ''
                          AND r.session_rating IS NOT NULL
                    ) AS complete
                FROM feedback_responses r
                LEFT JOIN students s ON r.student_id = s.id
                LEFT JOIN events e ON r.event_id = e.id
            """)
            total = row['total'] or 0
            complete = row['complete'] or 0
            return round((complete / total) * 100, 2) if total else 0.0
        except Exception as e:
            raise Exception(f"Error calculating completion rate: {e}")

    def calculate_department_coverage(self) -> float:
        """% of known departments that have submitted feedback."""
        try:
            row = execute_one("""
                SELECT COUNT(DISTINCT e.department) AS unique_depts
                FROM feedback_responses r
                LEFT JOIN events e ON r.event_id = e.id
                WHERE e.department IS NOT NULL AND e.department <> ''
            """)
            unique_depts = row['unique_depts'] or 0
            total_depts = 40  # Expected number of departments
            return round((unique_depts / total_depts) * 100, 2)
        except Exception as e:
            raise Exception(f"Error calculating department coverage: {e}")

    def calculate_submission_velocity(self, days: int = 7) -> float:
        """Average submissions per day for the last N days."""
        try:
            start_date = (datetime.utcnow() - timedelta(days=days)).date()
            row = execute_one("""
                SELECT COUNT(*) AS count
                FROM feedback_responses
                WHERE submitted_at >= %s
            """, (start_date,))
            total = row['count'] or 0
            return round(total / days, 2)
        except Exception as e:
            raise Exception(f"Error calculating submission velocity: {e}")

    def get_all_kpis(self) -> Dict:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                'engagement_rate': executor.submit(self.calculate_engagement_rate),
                'satisfaction_score': executor.submit(self.calculate_satisfaction_score),
                'completion_rate': executor.submit(self.calculate_completion_rate),
                'department_coverage': executor.submit(self.calculate_department_coverage),
                'submission_velocity_7d': executor.submit(self.calculate_submission_velocity, 7),
                'submission_velocity_30d': executor.submit(self.calculate_submission_velocity, 30),
            }
            return {k: v.result() for k, v in futures.items()}

    def get_kpi_health_status(self) -> Dict:
        kpis = self.get_all_kpis()
        thresholds = {
            'engagement_rate':     {'green': 70, 'yellow': 50},
            'satisfaction_score':  {'green': 80, 'yellow': 60},
            'completion_rate':     {'green': 90, 'yellow': 75},
            'department_coverage': {'green': 90, 'yellow': 70},
        }
        status = {}
        for kpi_name, kpi_value in kpis.items():
            if kpi_name in thresholds:
                t = thresholds[kpi_name]
                health = 'GREEN' if kpi_value >= t['green'] else ('YELLOW' if kpi_value >= t['yellow'] else 'RED')
                status[kpi_name] = {'value': kpi_value, 'health': health}
            else:
                status[kpi_name] = {'value': kpi_value}
        return status
