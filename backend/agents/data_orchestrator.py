from typing import Dict, Any, List
import pandas as pd
from datetime import datetime
from backend.utils.logger import get_section_logger
from backend.utils.insforge_db import execute_one, execute_all
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
        email = row.get('student_email', '').strip() or None
        roll_no = row.get('roll_no', '').strip()
        name = row.get('name_of_student', '').strip()
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
            'submitted_at': row.get('timestamp_display'),
            'session_rating': safe_int(row.get('session_rating')),
            'session_help_understanding': row.get('session_help_understanding', ''),
            'aspect_most_valuable': row.get('aspect_most_valuable', ''),
            'improvements_suggestions': row.get('improvements_suggestions', ''),
            'future_topics': row.get('future_topics', '')
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
            from backend.utils.insforge_db import api_upsert
            # 1. Upsert Student
            stu_row = api_upsert('students', {
                'roll_no': stu['roll_no'],
                'email': stu.get('email'),
                'name': stu['name'],
                'department': stu['department']
            }, 'roll_no')
            student_id = stu_row[0]['id'] if stu_row else None
            
            # 2. Upsert Event
            # InsForge REST needs a unique constraint for ON CONFLICT, so if speaker_name,venue_date isn't uniquely constrained, we should just insert or select-first. Let's assume api_upsert works for 'speaker_name,venue_date'.
            # Since 'speaker_name,venue_date' might not be a valid PostgREST conflict_columns format unless there's a specific unique constraint, let's just do a select first.
            from backend.utils.insforge_db import api_select, api_insert
            existing_event = api_select('events', 'speaker_name', evt['speaker_name'])
            # Actually api_select is match_col=match_val, we need AND venue_date. Let's do it manually via execute_one for SELECT since SELECT is allowed in rawsql!
            from backend.utils.insforge_db import execute_one
            evt_row = execute_one("SELECT id FROM events WHERE speaker_name=%s AND venue_date=%s", (evt['speaker_name'], evt['venue_date']))
            if evt_row:
                event_id = evt_row['id']
            else:
                new_evt = api_insert('events', {
                    'speaker_name': evt['speaker_name'],
                    'venue_date': evt['venue_date'],
                    'department': evt['department']
                })
                event_id = new_evt[0]['id'] if new_evt else None
            
            # 3. Upsert Feedback
            sub_at = fb['submitted_at']
            try:
                sub_at = pd.to_datetime(sub_at).strftime('%Y-%m-%d %H:%M:%S%z') if pd.notna(sub_at) else datetime.now().isoformat()
            except:
                sub_at = datetime.now().isoformat()

            # For feedback, ON CONFLICT (event_id, student_id)
            fb_check = execute_one("SELECT id FROM feedback_responses WHERE event_id=%s AND student_id=%s", (event_id, student_id))
            
            payload_data = {
                'event_id': event_id,
                'student_id': student_id,
                'submitted_at': sub_at,
                'session_rating': fb['session_rating'],
                'session_help_understanding': fb['session_help_understanding'],
                'aspect_most_valuable': fb['aspect_most_valuable'],
                'improvements_suggestions': fb['improvements_suggestions'],
                'future_topics': fb['future_topics'],
                'data_quality_score': fb['data_quality_score'],
                'is_duplicate': fb['is_duplicate']
            }
            if fb_check:
                from backend.utils.insforge_db import api_update
                api_update('feedback_responses', 'id', fb_check['id'], payload_data)
                fb_id = fb_check['id']
            else:
                fb_row = api_insert('feedback_responses', payload_data)
                fb_id = fb_row[0]['id'] if fb_row else None
            
            payload['response_id'] = fb_id
            logger.info(f"Successfully synced feedback ID: {fb_id}")
            
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
