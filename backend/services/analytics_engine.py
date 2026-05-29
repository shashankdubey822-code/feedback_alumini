import pandas as pd
from backend.utils.insforge_db import execute_all
from backend.utils.logger import get_section_logger
from datetime import datetime

logger = get_section_logger('analytics_engine')

class AnalyticsEngine:
    """
    In-Memory Analytics Engine.
    Fetches all normalized data from InsForge and performs blazing fast
    filtering, aggregation, and analytics using pandas DataFrames.
    """
    def __init__(self):
        self._df = pd.DataFrame()
        self._last_refresh = None
        
    def refresh_data(self):
        """Fetch all data from the database and rebuild the master DataFrame."""
        logger.info("Refreshing in-memory analytics data...")
        try:
            # We fetch a joined flat view of all responses for easy dataframe manipulation
            query = """
            SELECT 
                r.id as response_id,
                r.submitted_at,
                r.session_rating,
                r.aspect_most_valuable,
                r.improvements_suggestions,
                r.session_help_understanding,
                r.future_topics,
                e.id as event_id,
                e.speaker_name,
                e.venue_date,
                e.department,
                s.id as student_id,
                s.name as student_name,
                s.roll_no,
                a.sentiment_label,
                a.sentiment_score,
                a.key_topics as keywords_json
            FROM feedback_responses r
            JOIN events e ON r.event_id = e.id
            JOIN students s ON r.student_id = s.id
            LEFT JOIN feedback_analysis a ON r.id = a.response_id
            ORDER BY r.submitted_at DESC
            """
            rows = execute_all(query)
            if rows:
                self._df = pd.DataFrame(rows)
                # Ensure datetime types
                self._df['submitted_at'] = pd.to_datetime(self._df['submitted_at'])
            else:
                self._df = pd.DataFrame(columns=[
                    'response_id', 'submitted_at', 'session_rating', 'aspect_most_valuable',
                    'improvements_suggestions', 'session_help_understanding', 'future_topics',
                    'event_id', 'speaker_name', 'venue_date', 'event_name',
                    'student_id', 'student_name', 'roll_no', 'department',
                    'sentiment_label', 'sentiment_score', 'keywords_json'
                ])
                
            self._last_refresh = datetime.now()
            logger.info(f"Analytics Engine refreshed. Loaded {len(self._df)} records.")
        except Exception as e:
            logger.error(f"Error refreshing analytics data: {e}")

    def refresh_single_record(self, response_id: int):
        """Fetch a single record from the database and prepend it to the master DataFrame."""
        logger.info(f"Incremental update for in-memory analytics data: #{response_id}")
        try:
            query = """
            SELECT 
                r.id as response_id,
                r.submitted_at,
                r.session_rating,
                r.aspect_most_valuable,
                r.improvements_suggestions,
                r.session_help_understanding,
                r.future_topics,
                e.id as event_id,
                e.speaker_name,
                e.venue_date,
                e.department,
                s.id as student_id,
                s.name as student_name,
                s.roll_no,
                a.sentiment_label,
                a.sentiment_score,
                a.key_topics as keywords_json
            FROM feedback_responses r
            JOIN events e ON r.event_id = e.id
            JOIN students s ON r.student_id = s.id
            LEFT JOIN feedback_analysis a ON r.id = a.response_id
            WHERE r.id = %s
            """
            from backend.utils.insforge_db import execute_all
            rows = execute_all(query, (response_id,))
            if rows:
                new_df = pd.DataFrame(rows)
                new_df['submitted_at'] = pd.to_datetime(new_df['submitted_at'])
                
                # If dataframe is not empty, concat. Otherwise just assign
                if not self._df.empty:
                    # Remove any existing row with this ID just in case (upsert behavior)
                    self._df = self._df[self._df['response_id'] != response_id]
                    self._df = pd.concat([new_df, self._df], ignore_index=True)
                else:
                    self._df = new_df
                    
                self._df.sort_values(by='submitted_at', ascending=False, inplace=True)
                self._last_refresh = datetime.now()
                logger.info(f"Analytics Engine incremental update complete for #{response_id}.")
        except Exception as e:
            logger.error(f"Error in incremental refresh: {e}")
            
    def get_dataframe(self) -> pd.DataFrame:
        """Returns a copy of the current DataFrame"""
        if self._df.empty and self._last_refresh is None:
            self.refresh_data()
        return self._df.copy()

    def filter_data(self, speaker: str = None, date: str = None, department: str = None) -> pd.DataFrame:
        df = self.get_dataframe()
        if df.empty:
            return df
            
        if speaker and speaker != "All Speakers":
            df = df[df['speaker_name'] == speaker]
            
        if date and date != "All Dates":
            df = df[df['venue_date'] == date]
            
        if department and department != "All Departments":
            df = df[df['department'] == department]
            
        return df

    def get_initial_payload(self):
        """Fast initial payload mimicking the old /api/initial"""
        df = self.get_dataframe()
        total = len(df)
        
        # Take top 25 recent
        sample = df.head(25) if not df.empty else df
        
        meta = {
            'columns': ['submitted_at', 'speaker_name', 'session_rating', 'aspect_most_valuable'],
            'columnTypes': {
                'submitted_at': 'date',
                'speaker_name': 'text',
                'session_rating': 'numeric',
                'aspect_most_valuable': 'text'
            },
            'filename': 'Live_Preview'
        }
        
        table_data = []
        for _, row in sample.iterrows():
            table_data.append({
                'id': row['response_id'],
                'submitted_at': row['submitted_at'].isoformat() if pd.notnull(row['submitted_at']) else None,
                'alumni_speaker_name': row['speaker_name'], # keep legacy key for frontend table mapping for now
                'session_rating': row['session_rating'],
                'aspect_most_valuable': row['aspect_most_valuable']
            })
            
        return {
            'meta': meta,
            'tableData': table_data,
            'totalResponses': total,
        }

    def get_filter_options(self):
        df = self.get_dataframe()
        if df.empty:
            return {'speakers': [], 'dates': [], 'departments': []}
            
        speakers = df['speaker_name'].dropna().unique().tolist()
        dates = df['venue_date'].dropna().unique().tolist()
        depts = df['department'].dropna().unique().tolist()
        
        return {
            'speakers': sorted(speakers),
            'dates': sorted(dates),
            'departments': sorted(depts)
        }

# Global singleton
analytics_engine = AnalyticsEngine()
