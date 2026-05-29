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
        from backend.services.analytics_engine import analytics_engine
        import pandas as pd
        
        df = analytics_engine.get_dataframe()
        if df.empty:
            return {
                'engagement_rate': 0.0,
                'satisfaction_score': 0.0,
                'completion_rate': 0.0,
                'department_coverage': 0.0,
                'submission_velocity_7d': 0.0,
                'submission_velocity_30d': 0.0,
            }
            
        total = len(df)
        
        # 1. Engagement Rate (has feedback in improvements or valuable)
        has_feedback = df['improvements_suggestions'].notna() & (df['improvements_suggestions'] != '') | \
                       df['aspect_most_valuable'].notna() & (df['aspect_most_valuable'] != '')
        eng_rate = round((has_feedback.sum() / total) * 100, 2) if total else 0.0
        
        # 2. Satisfaction Score (rated >= 4)
        rated_df = df.dropna(subset=['session_rating'])
        sat_score = round((len(rated_df[rated_df['session_rating'] >= 4]) / len(rated_df)) * 100, 2) if not rated_df.empty else 0.0
        
        # 3. Completion Rate (has name, department, and rating)
        has_name = df['student_name'].notna() & (df['student_name'] != '')
        has_dept = df['department'].notna() & (df['department'] != '')
        has_rating = df['session_rating'].notna()
        completed = (has_name & has_dept & has_rating).sum()
        comp_rate = round((completed / total) * 100, 2) if total else 0.0
        
        # 4. Department Coverage
        unique_depts = df['department'].dropna().replace('', pd.NA).dropna().nunique()
        dept_cov = round((unique_depts / 40) * 100, 2)
        
        # 5. Submission Velocity
        now = pd.Timestamp.utcnow().tz_localize(None)
        
        try:
            # Ensure submitted_at is timezone-naive for comparison
            df_dates = pd.to_datetime(df['submitted_at']).dt.tz_localize(None)
            vel_7d = round(len(df[df_dates >= (now - pd.Timedelta(days=7))]) / 7, 2)
            vel_30d = round(len(df[df_dates >= (now - pd.Timedelta(days=30))]) / 30, 2)
        except Exception:
            vel_7d = 0.0
            vel_30d = 0.0
            
        return {
            'engagement_rate': eng_rate,
            'satisfaction_score': sat_score,
            'completion_rate': comp_rate,
            'department_coverage': dept_cov,
            'submission_velocity_7d': vel_7d,
            'submission_velocity_30d': vel_30d,
        }

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
