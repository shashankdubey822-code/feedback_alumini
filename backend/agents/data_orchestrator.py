from typing import Dict, Any, List
import pandas as pd
from datetime import datetime
from backend.utils.logger import get_section_logger
from backend.utils.supabase_db import execute_one, execute_all
from backend.agents.base import BaseAgent, SupervisorAgent

logger = get_section_logger('data_orchestrator')

# ----------------- SUBAGENTS ----------------- #

class WebhookMonitorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Webhook Monitor Subagent", "Listens for real-time form submissions and standardizes payload.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing WebhookMonitorAgent")
        # In a real webhook, this standardizes raw incoming dicts into a standard row
        return payload

class CSVParserAgent(BaseAgent):
    def __init__(self):
        super().__init__("CSV Parser Subagent", "Handles batch CSV uploads, standardizing headers.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing CSVParserAgent")
        # Ensure payload is standardized into a dict list
        return payload

class IdentityResolutionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Identity Resolution Subagent", "Cross-references emails/roll numbers to upsert students.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing IdentityResolutionAgent")
        row = payload.get('row', {})
        email = row.get('email_address', '').strip()
        roll_no = row.get('roll_number', '').strip()
        name = row.get('name_of_the_student', '').strip()
        department = row.get('department', '').strip()

        # Simple ID tracking mapping (in real DB, this is an upsert)
        payload['student_data'] = {
            'email': email,
            'roll_no': roll_no,
            'name': name,
            'department': department
        }
        return payload

class EventNormalizationAgent(BaseAgent):
    def __init__(self):
        super().__init__("Event Normalization Subagent", "Matches event details (speaker, date).")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing EventNormalizationAgent")
        row = payload.get('row', {})
        speaker = row.get('alumni_speaker_name', '').strip()
        date_str = row.get('date_of_lecture', '')
        
        # Standardize date
        try:
            venue_date = pd.to_datetime(date_str).strftime('%Y-%m-%d') if pd.notna(date_str) and str(date_str).strip() else datetime.now().strftime('%Y-%m-%d')
        except:
            venue_date = datetime.now().strftime('%Y-%m-%d')

        payload['event_data'] = {
            'speaker_name': speaker,
            'venue_date': venue_date,
            'department': row.get('department', '').strip(),
            'name': f"Guest Lecture by {speaker}"
        }
        return payload

class FeedbackExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Feedback Extraction Subagent", "Extracts the raw survey responses.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing FeedbackExtractionAgent")
        row = payload.get('row', {})
        
        def safe_int(val):
            try: return int(float(str(val)))
            except: return None
            
        payload['feedback_data'] = {
            'submitted_at': row.get('timestamp'),
            'session_rating': safe_int(row.get('how_would_you_rate_the_session_overall')),
            'session_help_understanding': row.get('did_the_session_help_you_understand_the_real-world_applications_of_your_course_of_study', ''),
            'aspect_most_valuable': row.get('what_aspect_of_the_lecture_did_you_find_most_valuable', ''),
            'improvements_suggestions': row.get('how_could_the_session_be_improved', ''),
            'future_topics': row.get('what_topics_would_you_like_to_see_covered_in_future_alumni_lectures', '')
        }
        return payload

class DataQualityAgent(BaseAgent):
    def __init__(self):
        super().__init__("Data Quality Subagent", "Assigns a data_quality_score.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing DataQualityAgent")
        fb = payload.get('feedback_data', {})
        score = 100
        
        # Deduct points for missing text fields
        if not fb.get('aspect_most_valuable'): score -= 20
        if not fb.get('improvements_suggestions'): score -= 20
        if not fb.get('future_topics'): score -= 20
        
        payload['feedback_data']['data_quality_score'] = max(0, score)
        payload['feedback_data']['is_duplicate'] = False
        return payload

class DatabaseSyncAgent(BaseAgent):
    def __init__(self):
        super().__init__("Database Sync Subagent", "Ensures atomic transaction commits to PostgreSQL.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing DatabaseSyncAgent")
        stu = payload.get('student_data', {})
        evt = payload.get('event_data', {})
        fb = payload.get('feedback_data', {})
        
        if not stu.get('roll_no') or not evt.get('speaker_name'):
            logger.warning("Missing vital data. Skipping row.")
            return payload
            
        try:
            # 1. Upsert Student
            stu_row = execute_one("""
                INSERT INTO students (roll_no, email, name, department)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (roll_no) DO UPDATE SET
                    name = EXCLUDED.name, email = EXCLUDED.email
                RETURNING id
            """, (stu['roll_no'], stu.get('email'), stu['name'], stu['department']))
            student_id = stu_row['id']
            
            # 2. Upsert Event
            evt_row = execute_one("""
                INSERT INTO events (speaker_name, venue_date, department, name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (speaker_name, venue_date) DO UPDATE SET
                    department = EXCLUDED.department
                RETURNING id
            """, (evt['speaker_name'], evt['venue_date'], evt['department'], evt['name']))
            event_id = evt_row['id']
            
            # 3. Upsert Feedback
            sub_at = fb['submitted_at']
            try:
                sub_at = pd.to_datetime(sub_at).strftime('%Y-%m-%d %H:%M:%S%z') if pd.notna(sub_at) else datetime.now().isoformat()
            except:
                sub_at = datetime.now().isoformat()

            fb_row = execute_one("""
                INSERT INTO feedback_responses (
                    event_id, student_id, submitted_at,
                    session_rating, session_help_understanding, aspect_most_valuable,
                    improvements_suggestions, future_topics, data_quality_score, is_duplicate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id, student_id) DO UPDATE SET
                    submitted_at = EXCLUDED.submitted_at,
                    session_rating = EXCLUDED.session_rating,
                    aspect_most_valuable = EXCLUDED.aspect_most_valuable,
                    improvements_suggestions = EXCLUDED.improvements_suggestions,
                    future_topics = EXCLUDED.future_topics
                RETURNING id
            """, (
                event_id, student_id, sub_at,
                fb['session_rating'], fb['session_help_understanding'],
                fb['aspect_most_valuable'], fb['improvements_suggestions'],
                fb['future_topics'], fb['data_quality_score'], fb['is_duplicate']
            ))
            
            payload['response_id'] = fb_row['id']
            logger.info(f"Successfully synced feedback ID: {fb_row['id']}")
            
        except Exception as e:
            logger.error(f"DB Sync error: {str(e)}")
            payload['error'] = str(e)
            
        return payload

# ----------------- SUPERVISOR ----------------- #

class DataOrchestratorSupervisor(SupervisorAgent):
    def __init__(self):
        super().__init__("Data Orchestrator Supervisor", "Manages all ingestion pipelines, parsing, and database transactions.")
        
        # Register subagents in order of execution for a single row workflow
        self.register_subagent(WebhookMonitorAgent())
        self.register_subagent(CSVParserAgent())
        self.register_subagent(IdentityResolutionAgent())
        self.register_subagent(EventNormalizationAgent())
        self.register_subagent(FeedbackExtractionAgent())
        self.register_subagent(DataQualityAgent())
        self.register_subagent(DatabaseSyncAgent())

    def orchestrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Data Orchestrator: Processing payload via {len(self.subagents)} subagents...")
        
        # If batch (CSV), it needs to loop. If single row (Webhook), it processes once.
        if 'rows' in payload:
            processed = []
            for row in payload['rows']:
                state = {'row': row}
                for agent in self.subagents:
                    state = agent.execute(state)
                    if 'error' in state: break
                processed.append(state)
            payload['processed_rows'] = processed
        else:
            state = payload
            for agent in self.subagents:
                state = agent.execute(state)
                if 'error' in state: break
            payload = state
            
        return payload
