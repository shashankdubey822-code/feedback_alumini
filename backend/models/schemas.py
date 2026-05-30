"""
Data models and schemas for validation and serialization
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class FeedbackRecord:
    """Main feedback record schema"""
    id: Optional[int] = None
    timestamp_original: str = ''
    name_of_student: str = ''
    department_original: str = ''
    roll_no_original: str = ''
    date_of_lecture: str = ''
    alumni_speaker_name: str = ''
    session_help_understanding: str = ''
    session_rating: Optional[int] = None
    session_technical_clarity: Optional[int] = None
    aspect_most_valuable: str = ''
    improvements_suggestions: str = ''
    future_topics: str = ''

    # Cleaned and metadata fields
    timestamp_normalized: Optional[str] = None
    name_normalized: Optional[str] = None
    department_cleaned: Optional[str] = None
    roll_no_cleaned: Optional[str] = None
    form_source: Optional[str] = None
    data_quality_score: Optional[float] = None
    is_duplicate_flag: Optional[int] = None
    record_status: Optional[str] = None
    cleaned_at: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'timestamp_original': self.timestamp_original,
            'name_of_student': self.name_of_student,
            'department_original': self.department_original,
            'roll_no_original': self.roll_no_original,
            'date_of_lecture': self.date_of_lecture,
            'alumni_speaker_name': self.alumni_speaker_name,
            'session_help_understanding': self.session_help_understanding,
            'session_rating': self.session_rating,
            'session_technical_clarity': self.session_technical_clarity,
            'aspect_most_valuable': self.aspect_most_valuable,
            'improvements_suggestions': self.improvements_suggestions,
            'future_topics': self.future_topics,
            'timestamp_normalized': self.timestamp_normalized,
            'name_normalized': self.name_normalized,
            'department_cleaned': self.department_cleaned,
            'roll_no_cleaned': self.roll_no_cleaned,
            'form_source': self.form_source,
            'data_quality_score': self.data_quality_score,
            'is_duplicate_flag': self.is_duplicate_flag,
            'record_status': self.record_status,
            'cleaned_at': self.cleaned_at,
        }


@dataclass
class FormDefinition:
    """Form configuration and metadata"""
    form_id: Optional[int] = None
    form_name: str = ''
    speaker_name: str = ''
    venue_date: str = ''
    google_form_id: str = ''
    google_form_url: str = ''
    status: str = 'active'
    password_protected: bool = True
    created_at: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'form_id': self.form_id,
            'form_name': self.form_name,
            'speaker_name': self.speaker_name,
            'venue_date': self.venue_date,
            'google_form_id': self.google_form_id,
            'google_form_url': self.google_form_url,
            'status': self.status,
            'password_protected': self.password_protected,
            'created_at': self.created_at,
        }


@dataclass
class Department:
    """Standardized department schema"""
    id: Optional[int] = None
    department_name: str = ''
    department_code: str = ''
    record_count: int = 0
    is_active: bool = True

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'department_name': self.department_name,
            'department_code': self.department_code,
            'record_count': self.record_count,
            'is_active': self.is_active,
        }


@dataclass
class WebhookPayload:
    """Webhook payload schema for Google Forms"""
    timestamp: str
    form_id: str
    responses: dict

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp,
            'form_id': self.form_id,
            'responses': self.responses,
        }


@dataclass
class AnalyticsResponse:
    """Analytics data response schema"""
    total_records: int
    average_rating: Optional[float]
    department_distribution: dict
    top_speakers: List[tuple]
    top_keywords: List[tuple]
    sentiment_distribution: dict
    data_quality_metrics: dict

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'total_records': self.total_records,
            'average_rating': self.average_rating,
            'department_distribution': self.department_distribution,
            'top_speakers': self.top_speakers,
            'top_keywords': self.top_keywords,
            'sentiment_distribution': self.sentiment_distribution,
            'data_quality_metrics': self.data_quality_metrics,
        }


@dataclass
class ErrorResponse:
    """Standard error response schema"""
    error: str
    message: str
    status_code: int
    timestamp: str = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'error': self.error,
            'message': self.message,
            'status_code': self.status_code,
            'timestamp': self.timestamp,
        }
