"""
Chart Service — Generate chart data using native InsForge PostgreSQL.
"""

from typing import Dict, List
from datetime import datetime, timedelta
from backend.utils.insforge_db import execute_all, execute_one


class ChartService:
    """Generate chart data from InsForge PostgreSQL."""

    def get_timeline_data(self, df, days: int = 30) -> List[Dict]:
        if df.empty: return []
        now = pd.Timestamp.utcnow().tz_localize(None)
        df_dates = pd.to_datetime(df['submitted_at']).dt.tz_localize(None)
        mask = df_dates >= (now - pd.Timedelta(days=days))
        recent = df[mask].copy()
        if recent.empty: return []
        
        recent['date_str'] = df_dates[mask].dt.strftime('%Y-%m-%d')
        grouped = recent.groupby('date_str').agg(
            submissions=('response_id', 'count'),
            average_rating=('session_rating', 'mean')
        ).reset_index().sort_values('date_str')
        
        return [
            {
                'date': str(r['date_str']),
                'submissions': int(r['submissions']),
                'average_rating': round(float(r['average_rating']), 2) if pd.notna(r['average_rating']) else None
            }
            for _, r in grouped.iterrows()
        ]

    def get_department_ratings(self, df) -> List[Dict]:
        if df.empty: return []
        dept_df = df.dropna(subset=['department', 'session_rating'])
        dept_df = dept_df[dept_df['department'] != '']
        if dept_df.empty: return []
        
        grouped = dept_df.groupby('department').agg(
            count=('response_id', 'count'),
            avg_rating=('session_rating', 'mean')
        ).reset_index().sort_values('avg_rating', ascending=False)
        
        return [
            {
                'department': str(r['department']),
                'count': int(r['count']),
                'average_rating': round(float(r['avg_rating']), 2)
            }
            for _, r in grouped.iterrows()
        ]

    def get_speaker_statistics(self, df, limit: int = 10) -> List[Dict]:
        if df.empty: return []
        speaker_df = df.dropna(subset=['speaker_name'])
        speaker_df = speaker_df[speaker_df['speaker_name'] != '']
        if speaker_df.empty: return []
        
        grouped = speaker_df.groupby('speaker_name').agg(
            session_count=('response_id', 'count'),
            avg_rating=('session_rating', 'mean')
        ).reset_index().sort_values('session_count', ascending=False).head(limit)
        
        return [
            {
                'speaker': str(r['speaker_name']),
                'sessions': int(r['session_count']),
                'average_rating': round(float(r['avg_rating']), 2) if pd.notna(r['avg_rating']) else None
            }
            for _, r in grouped.iterrows()
        ]

    def get_rating_pie_chart(self, df) -> List[Dict]:
        if df.empty: return []
        ratings = df.dropna(subset=['session_rating'])
        if ratings.empty: return []
        
        counts = ratings['session_rating'].value_counts().sort_index()
        rating_labels = {
            1: '1 - Poor', 2: '2 - Fair', 3: '3 - Average',
            4: '4 - Good', 5: '5 - Excellent',
        }
        
        return [
            {
                'label': rating_labels.get(int(rating), f"Rating {int(rating)}"),
                'value': int(count),
                'rating': int(rating)
            }
            for rating, count in counts.items()
        ]

    def get_monthly_comparison(self, df) -> List[Dict]:
        if df.empty: return []
        df_dates = pd.to_datetime(df['submitted_at']).dropna()
        if df_dates.empty: return []
        
        df_copy = df.loc[df_dates.index].copy()
        df_copy['month'] = df_dates.dt.strftime('%Y-%m')
        
        grouped = df_copy.groupby('month').agg(
            submissions=('response_id', 'count'),
            avg_rating=('session_rating', 'mean')
        ).reset_index().sort_values('month', ascending=False).head(12)
        
        results = [
            {
                'month': str(r['month']),
                'submissions': int(r['submissions']),
                'average_rating': round(float(r['avg_rating']), 2) if pd.notna(r['avg_rating']) else None
            }
            for _, r in grouped.iterrows()
        ]
        return list(reversed(results))

    def get_all_chart_data(self) -> Dict:
        from backend.services.analytics_engine import analytics_engine
        import pandas as pd
        global pd
        
        df = analytics_engine.get_dataframe()
        return {
            'timeline':            self.get_timeline_data(df),
            'department_ratings':  self.get_department_ratings(df),
            'speakers':            self.get_speaker_statistics(df),
            'rating_distribution': self.get_rating_pie_chart(df),
            'monthly_comparison':  self.get_monthly_comparison(df),
        }
