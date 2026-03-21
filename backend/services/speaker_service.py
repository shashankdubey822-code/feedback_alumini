"""
Speaker Service - Speaker-specific analytics and insights
"""

import sqlite3
from typing import Dict, List, Optional
from backend.utils.db_helper import get_db_connection


class SpeakerService:
    """Analyze speaker performance and feedback"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self):
        """Get database connection"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_speaker_profile(self, speaker_name: str) -> Dict:
        """Get complete profile for a speaker"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Basic stats
            cursor.execute(
                'SELECT '
                'COUNT(*) as total_sessions, '
                'AVG(session_rating) as avg_rating, '
                'MIN(session_rating) as min_rating, '
                'MAX(session_rating) as max_rating, '
                'AVG(session_technical_clarity) as avg_clarity '
                'FROM dashboard_data '
                'WHERE alumni_speaker_name = ?',
                (speaker_name,)
            )

            stats = cursor.fetchone()

            conn.close()

            return {
                'speaker_name': speaker_name,
                'total_sessions': stats['total_sessions'],
                'average_rating': round(stats['avg_rating'], 2) if stats['avg_rating'] else None,
                'min_rating': stats['min_rating'],
                'max_rating': stats['max_rating'],
                'technical_clarity_score': round(stats['avg_clarity'], 2) if stats['avg_clarity'] else None,
            }
        except Exception as e:
            raise Exception(f"Error getting speaker profile: {str(e)}")

    def get_speaker_feedback_summary(self, speaker_name: str) -> Dict:
        """Get aggregated feedback for a speaker"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get all feedback records
            cursor.execute(
                'SELECT aspect_most_valuable, improvements_suggestions '
                'FROM dashboard_data '
                'WHERE alumni_speaker_name = ?',
                (speaker_name,)
            )

            records = cursor.fetchall()
            conn.close()

            positive_feedback = []
            suggestions = []

            for record in records:
                if record['aspect_most_valuable'] and record['aspect_most_valuable'] not in ['NO_RESPONSE', 'N/A']:
                    positive_feedback.append(record['aspect_most_valuable'])
                if record['improvements_suggestions'] and record['improvements_suggestions'] not in ['NO_RESPONSE', 'N/A']:
                    suggestions.append(record['improvements_suggestions'])

            return {
                'speaker_name': speaker_name,
                'total_feedback_records': len(records),
                'positive_feedback_count': len(positive_feedback),
                'suggestion_count': len(suggestions),
                'positive_feedback': positive_feedback[:10],  # Top 10
                'suggestions': suggestions[:10],  # Top 10
            }
        except Exception as e:
            raise Exception(f"Error getting speaker feedback summary: {str(e)}")

    def get_all_speakers(self) -> List[Dict]:
        """Get all speakers with their statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT '
                'alumni_speaker_name, '
                'COUNT(*) as session_count, '
                'AVG(session_rating) as avg_rating, '
                'MAX(timestamp_normalized) as last_session '
                'FROM dashboard_data '
                'WHERE alumni_speaker_name IS NOT NULL AND alumni_speaker_name != "" '
                'GROUP BY alumni_speaker_name '
                'ORDER BY session_count DESC'
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'speaker_name': row['alumni_speaker_name'],
                    'session_count': row['session_count'],
                    'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else None,
                    'last_session': row['last_session'],
                })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error getting all speakers: {str(e)}")

    def get_speaker_comparison(self, speakers: List[str] = None) -> List[Dict]:
        """Compare multiple speakers"""
        if speakers is None:
            # Get top 5 speakers by default
            all_speakers = self.get_all_speakers()
            speakers = [s['speaker_name'] for s in all_speakers[:5]]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            results = []
            for speaker in speakers:
                cursor.execute(
                    'SELECT '
                    'alumni_speaker_name, '
                    'COUNT(*) as session_count, '
                    'AVG(session_rating) as avg_rating, '
                    'AVG(session_technical_clarity) as avg_clarity '
                    'FROM dashboard_data '
                    'WHERE alumni_speaker_name = ? '
                    'GROUP BY alumni_speaker_name',
                    (speaker,)
                )

                row = cursor.fetchone()
                if row:
                    results.append({
                        'speaker_name': row['alumni_speaker_name'],
                        'session_count': row['session_count'],
                        'average_rating': round(row['avg_rating'], 2) if row['avg_rating'] else 0,
                        'technical_clarity': round(row['avg_clarity'], 2) if row['avg_clarity'] else 0,
                    })

            conn.close()
            return results
        except Exception as e:
            raise Exception(f"Error comparing speakers: {str(e)}")

    def get_speaker_trend(self, speaker_name: str, limit: int = 10) -> List[Dict]:
        """Get rating trend for a speaker over time"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT timestamp_normalized, session_rating '
                'FROM dashboard_data '
                'WHERE alumni_speaker_name = ? '
                'ORDER BY timestamp_normalized DESC '
                'LIMIT ?',
                (speaker_name, limit)
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    'date': row['timestamp_normalized'],
                    'rating': row['session_rating'],
                })

            conn.close()
            return list(reversed(results))  # Return chronologically ordered
        except Exception as e:
            raise Exception(f"Error getting speaker trend: {str(e)}")
