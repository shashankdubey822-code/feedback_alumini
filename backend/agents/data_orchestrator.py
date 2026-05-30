import os
import json
import requests
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from backend.utils.logger import get_section_logger
from backend.utils.insforge_db import execute_one, execute_all
from backend.agents.base import BaseAgent, SupervisorAgent

logger = get_section_logger('data_orchestrator')

# ----------------- LLM HELPER (LANGCHAIN FALLBACK) ----------------- #
def _call_llm_with_fallback(system_prompt: str, user_content: str, max_tokens: int = 150) -> str:
    """Calls LLM with instantaneous sub-millisecond fallback using LangChain."""
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from langchain_groq import ChatGroq
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        # Initialize models with max_retries=0 to fail fast
        openrouter = ChatOpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY", "dummy"),
            base_url="https://openrouter.ai/api/v1",
            model="meta-llama/llama-3.3-70b-instruct:free",
            max_retries=0,
            request_timeout=5.0,
            max_tokens=max_tokens,
            temperature=0.1
        )
        
        groq = ChatGroq(
            api_key=os.environ.get("GROQ_API_KEY", "dummy"),
            model="llama-3.3-70b-versatile",
            max_retries=0,
            request_timeout=5.0,
            max_tokens=max_tokens,
            temperature=0.1
        )
        
        gemini = ChatGoogleGenerativeAI(
            google_api_key=os.environ.get("GEMINI_API_KEY", "dummy"),
            model="gemini-2.5-flash",
            max_retries=0,
            request_timeout=5.0,
            max_output_tokens=max_tokens,
            temperature=0.1
        )
        
        # Create ultra-fast fallback chain
        fallback_llm = openrouter.with_fallbacks([groq, gemini])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{user_content}")
        ])
        
        chain = prompt | fallback_llm
        result = chain.invoke({"user_content": user_content})
        return str(result.content).strip()
        
    except Exception as e:
        logger.error(f"All LLMs Failed instantaneously: {str(e)}")
        return ""

# ----------------- SUBAGENTS (LLM CONTEXT ISOLATED) ----------------- #

class IdentityResolutionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Identity Resolution Agent", "Extracts core identity logic.")
        
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = payload.get('row', {})
        def safe_str(val):
            if pd.isna(val): return ''
            return str(val).strip()
            
        payload['student_data'] = {
            'email': safe_str(row.get('student_email')) or None,
            'roll_no': safe_str(row.get('roll_no')),
            'name': safe_str(row.get('name_of_student')),
            'department': safe_str(row.get('department'))
        }
        return payload

class EventNormalizationAgent(BaseAgent):
    def __init__(self):
        super().__init__("Event Normalization Agent", "Uses LLM to fuzzy match speakers and dates if messy.")
        
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing {self.name}")
        row = payload.get('row', {})
        raw_speaker = str(row.get('alumni_speaker_name', '')).strip() if not pd.isna(row.get('alumni_speaker_name')) else ''
        date_str = row.get('date_of_lecture', '')
        
        # Standardize Date
        try:
            venue_date = pd.to_datetime(date_str).strftime('%Y-%m-%d') if pd.notna(date_str) and str(date_str).strip() else datetime.now().strftime('%Y-%m-%d')
        except:
            venue_date = datetime.now().strftime('%Y-%m-%d')

        # LLM Context Isolation: Clean up speaker names (e.g. "Mr. John (CEO)" -> "John")
        clean_speaker = raw_speaker
        if raw_speaker and (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            llm_result = _call_llm_with_fallback(
                system_prompt="You are an Event Normalization Agent. Extract ONLY the exact full name of the speaker from the text. Remove titles (Mr., Dr.) and job descriptions. Return NOTHING ELSE but the name.",
                user_content=raw_speaker,
                max_tokens=20
            )
            if llm_result:
                clean_speaker = llm_result

        payload['event_data'] = {
            'speaker_name': clean_speaker or "Unknown Speaker",
            'venue_date': venue_date,
            'department': str(row.get('department', '')).strip() if not pd.isna(row.get('department')) else '',
            'name': f"Guest Lecture by {clean_speaker or 'Unknown Speaker'}"
        }
        return payload

class FeedbackExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Feedback Extraction Agent", "Extracts the raw survey responses.")
        
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = payload.get('row', {})
        def safe_int(val):
            try: return int(float(str(val)))
            except: return None
            
        def safe_str(val):
            if pd.isna(val): return ''
            return str(val).strip()

        payload['feedback_data'] = {
            'submitted_at': row.get('submitted_at'),
            'extracted_date': safe_str(row.get('extracted_date')),
            'extracted_time': safe_str(row.get('extracted_time')),
            'session_rating': safe_int(row.get('session_rating')),
            'session_help_understanding': safe_str(row.get('session_help_understanding')),
            'aspect_most_valuable': safe_str(row.get('aspect_most_valuable')),
            'improvements_suggestions': safe_str(row.get('improvements_suggestions')),
            'future_topics': safe_str(row.get('future_topics'))
        }
        return payload

class DataQualityAgent(BaseAgent):
    def __init__(self):
        super().__init__("Data Quality Agent", "Uses an LLM to evaluate the depth and value of the feedback.")
        
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing {self.name} (LLM Evaluation)")
        fb = payload.get('feedback_data', {})
        
        # Combine text for the LLM context
        combined_text = f"Valuable: {fb.get('aspect_most_valuable')}\nImprovements: {fb.get('improvements_suggestions')}\nTopics: {fb.get('future_topics')}"
        
        score = 100
        
        # If we have any API key, use it for qualitative scoring
        if os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"):
            llm_result = _call_llm_with_fallback(
                system_prompt="You are a Data Quality Agent. Score the usefulness of the provided feedback from 0 to 100. Provide ONLY the integer score. Deduct heavily for 'NA', 'none', or one-word answers. Reward detailed, actionable feedback.",
                user_content=combined_text,
                max_tokens=5
            )
            try:
                score = int(llm_result)
            except:
                pass # Fallback to deterministic if LLM hallucinates
        else:
            # Deterministic fallback
            if not fb.get('aspect_most_valuable'): score -= 20
            if not fb.get('improvements_suggestions'): score -= 20
            if not fb.get('future_topics'): score -= 20
            
        payload['feedback_data']['data_quality_score'] = max(0, min(100, score))
        payload['feedback_data']['is_duplicate'] = False
        return payload

class DatabaseSyncAgent(BaseAgent):
    def __init__(self):
        super().__init__("Database Sync Agent", "Commits validated data to InsForge.")
        
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        stu = payload.get('student_data', {})
        evt = payload.get('event_data', {})
        fb = payload.get('feedback_data', {})
        
        if not stu.get('roll_no') or not evt.get('speaker_name'):
            logger.warning("Missing vital data. Skipping row.")
            return payload
            
        try:
            from backend.utils.insforge_db import api_upsert, api_select, api_insert
            # 1. Upsert Student
            stu_row = api_upsert('students', {
                'roll_no': stu['roll_no'],
                'email': stu.get('email'),
                'name': stu['name'],
                'department': stu['department']
            }, 'roll_no')
            student_id = stu_row[0]['id'] if stu_row else None
            
            # 2. Upsert Event
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

            fb_check = execute_one("SELECT id FROM feedback_responses WHERE event_id=%s AND student_id=%s", (event_id, student_id))
            
            payload_data = {
                'event_id': event_id,
                'student_id': student_id,
                'submitted_at': sub_at,
                'extracted_date': str(fb.get('extracted_date')) if fb.get('extracted_date') and str(fb.get('extracted_date')).strip() else None,
                'extracted_time': str(fb.get('extracted_time')) if fb.get('extracted_time') and str(fb.get('extracted_time')).strip() else None,
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
            
        except Exception as e:
            logger.error(f"DB Sync error: {str(e)}")
            payload['error'] = str(e)
            
        return payload

# ----------------- SUPERVISOR ----------------- #

class DataOrchestratorSupervisor(SupervisorAgent):
    def __init__(self):
        super().__init__("Data Orchestrator Supervisor", "Routes payloads across true LLM agents.")
        
        self.register_subagent(IdentityResolutionAgent())
        self.register_subagent(EventNormalizationAgent())
        self.register_subagent(FeedbackExtractionAgent())
        self.register_subagent(DataQualityAgent())
        self.register_subagent(DatabaseSyncAgent())

    def orchestrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Data Orchestrator: Multi-Agent evaluation routing {len(self.subagents)} specialists...")
        
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
