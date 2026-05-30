import os
import json
import time
import random
import requests
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.utils.logger import get_section_logger
from backend.utils.insforge_db import execute_one, execute_all
from backend.agents.base import BaseAgent, SupervisorAgent

logger = get_section_logger('data_orchestrator')

# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON LLM CHAIN  —  initialized ONCE, reused across all rows/agents
#  This prevents hammering the provider auth endpoints on every single call.
# ─────────────────────────────────────────────────────────────────────────────
_llm_chain = None          # module-level singleton
_llm_prompt = None         # shared prompt template

def _get_llm_chain():
    """Return the cached fallback LLM chain, building it on first call."""
    global _llm_chain, _llm_prompt

    if _llm_chain is not None:
        return _llm_chain, _llm_prompt

    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from langchain_groq import ChatGroq
        from langchain_google_genai import ChatGoogleGenerativeAI

        # All models: max_retries=0 so LangChain fails-fast and hands off to next
        openrouter = ChatOpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY", "dummy"),
            base_url="https://openrouter.ai/api/v1",
            model="meta-llama/llama-3.3-70b-instruct:free",
            max_retries=0,
            request_timeout=8.0,
            max_tokens=80,
            temperature=0.1,
        )

        groq = ChatGroq(
            api_key=os.environ.get("GROQ_API_KEY", "dummy"),
            model="llama-3.3-70b-versatile",
            max_retries=0,
            request_timeout=8.0,
            max_tokens=80,
            temperature=0.1,
        )

        gemini = ChatGoogleGenerativeAI(
            google_api_key=os.environ.get("GEMINI_API_KEY", "dummy"),
            model="gemini-2.5-flash",
            max_retries=0,
            request_timeout=8.0,
            max_output_tokens=80,
            temperature=0.1,
        )

        # OpenRouter → Groq → Gemini fallback chain
        _llm_chain = openrouter.with_fallbacks([groq, gemini])

        _llm_prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("user", "{user_content}"),
        ])

        logger.info("LLM singleton chain initialised (OpenRouter→Groq→Gemini).")

    except Exception as e:
        logger.error(f"Failed to build LLM chain: {e}")
        _llm_chain = None
        _llm_prompt = None

    return _llm_chain, _llm_prompt


# ─────────────────────────────────────────────────────────────────────────────
#  RATE-LIMIT-AWARE LLM CALLER  —  exponential back-off with jitter
#  Handles 429 / ResourceExhausted across all three providers gracefully.
# ─────────────────────────────────────────────────────────────────────────────
_RATE_LIMIT_KEYWORDS = ("429", "rate limit", "quota", "resourceexhausted", "too many requests")
_MAX_BACKOFF_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 2.0


def _call_llm_with_fallback(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 80,
) -> str:
    """
    Call the singleton LLM fallback chain with exponential back-off on 429 errors.
    Returns an empty string on total failure (never raises).
    """
    chain_model, prompt_template = _get_llm_chain()

    if chain_model is None or prompt_template is None:
        logger.warning("LLM chain unavailable — skipping LLM call.")
        return ""

    chain = prompt_template | chain_model

    for attempt in range(_MAX_BACKOFF_ATTEMPTS):
        try:
            result = chain.invoke({
                "system_prompt": system_prompt,
                "user_content": user_content,
            })
            return str(result.content).strip()

        except Exception as e:
            err_lower = str(e).lower()
            is_rate_limit = any(kw in err_lower for kw in _RATE_LIMIT_KEYWORDS)

            if is_rate_limit and attempt < _MAX_BACKOFF_ATTEMPTS - 1:
                wait = (_BASE_BACKOFF_SECONDS ** (attempt + 1)) + random.uniform(0, 1.0)
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{_MAX_BACKOFF_ATTEMPTS}). "
                    f"Back-off {wait:.1f}s before retry."
                )
                time.sleep(wait)
                continue

            # Non-rate-limit error OR final attempt — log and bail
            logger.error(f"LLM call failed after {attempt + 1} attempt(s): {e}")
            return ""

    return ""


# ─────────────────────────────────────────────────────────────────────────────
#  COMBINED LLM TASK HELPER
#  Merges speaker-cleaning AND quality-scoring into ONE LLM call per row.
#  This halves the total number of API requests vs. calling each agent separately.
# ─────────────────────────────────────────────────────────────────────────────
_COMBINED_SYSTEM_PROMPT = (
    "You are a data processing assistant. Given a speaker name and feedback text, "
    "return a JSON object with exactly two keys:\n"
    "  \"speaker\": the cleaned full name (remove titles like Mr./Dr. and job descriptions),\n"
    "  \"quality\": an integer 0-100 rating how actionable/detailed the feedback is "
    "(penalise 'NA', 'none', or one-word answers; reward specific suggestions).\n"
    "Return ONLY the raw JSON object, no markdown, no extra text."
)


def _combined_llm_call(raw_speaker: str, feedback_text: str) -> Dict[str, Any]:
    """
    Single LLM call that returns {'speaker': str, 'quality': int}.
    Falls back to safe defaults on any failure.
    """
    default = {"speaker": raw_speaker or "Unknown Speaker", "quality": 100}

    has_key = any([
        os.environ.get("OPENROUTER_API_KEY"),
        os.environ.get("GROQ_API_KEY"),
        os.environ.get("GEMINI_API_KEY"),
    ])
    if not has_key:
        return default

    user_content = json.dumps({"speaker": raw_speaker, "feedback": feedback_text})
    raw = _call_llm_with_fallback(_COMBINED_SYSTEM_PROMPT, user_content)

    if not raw:
        return default

    # Strip accidental markdown fences
    clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        parsed = json.loads(clean)
        return {
            "speaker": str(parsed.get("speaker", raw_speaker) or raw_speaker).strip() or "Unknown Speaker",
            "quality": max(0, min(100, int(parsed.get("quality", 100)))),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning(f"LLM returned non-JSON: {raw!r}")
        return default


# ─────────────────────────────────────────────────────────────────────────────
#  SUBAGENTS
# ─────────────────────────────────────────────────────────────────────────────

class IdentityResolutionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Identity Resolution Agent", "Extracts core identity fields from raw row.")

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = payload.get("row", {})

        def safe_str(val):
            if pd.isna(val):
                return ""
            return str(val).strip()

        payload["student_data"] = {
            "email": safe_str(row.get("student_email")) or None,
            "roll_no": safe_str(row.get("roll_no")),
            "name": safe_str(row.get("name_of_student")),
            "department": safe_str(row.get("department")),
        }
        return payload


class EventNormalizationAgent(BaseAgent):
    """
    Extracts event metadata from the raw row.
    Speaker-name cleaning is deferred to the COMBINED LLM call in DataQualityAgent
    so we only hit the LLM ONCE per row total.
    """

    def __init__(self):
        super().__init__("Event Normalization Agent", "Parses speaker and date; LLM clean-up is merged.")

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing {self.name}")
        row = payload.get("row", {})
        raw_speaker = (
            str(row.get("alumni_speaker_name", "")).strip()
            if not pd.isna(row.get("alumni_speaker_name"))
            else ""
        )
        date_str = row.get("date_of_lecture", "")

        # Standardise date
        try:
            venue_date = (
                pd.to_datetime(date_str).strftime("%Y-%m-%d")
                if pd.notna(date_str) and str(date_str).strip()
                else datetime.now().strftime("%Y-%m-%d")
            )
        except Exception:
            venue_date = datetime.now().strftime("%Y-%m-%d")

        # Store raw speaker — will be cleaned by the combined LLM call
        payload["event_data"] = {
            "raw_speaker": raw_speaker,
            "speaker_name": raw_speaker or "Unknown Speaker",  # placeholder until LLM runs
            "venue_date": venue_date,
            "department": str(row.get("department", "")).strip() if not pd.isna(row.get("department")) else "",
            "name": f"Guest Lecture by {raw_speaker or 'Unknown Speaker'}",
        }
        return payload


class FeedbackExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Feedback Extraction Agent", "Extracts raw survey response fields.")

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = payload.get("row", {})

        def safe_int(val):
            try:
                return int(float(str(val)))
            except Exception:
                return None

        def safe_str(val):
            if pd.isna(val):
                return ""
            return str(val).strip()

        payload["feedback_data"] = {
            "submitted_at": row.get("submitted_at"),
            "extracted_date": safe_str(row.get("extracted_date")),
            "extracted_time": safe_str(row.get("extracted_time")),
            "session_rating": safe_int(row.get("session_rating")),
            "session_help_understanding": safe_str(row.get("session_help_understanding")),
            "aspect_most_valuable": safe_str(row.get("aspect_most_valuable")),
            "improvements_suggestions": safe_str(row.get("improvements_suggestions")),
            "future_topics": safe_str(row.get("future_topics")),
        }
        return payload


class DataQualityAgent(BaseAgent):
    """
    Makes the SINGLE combined LLM call per row:
    - Cleans speaker name  (updates event_data)
    - Scores feedback quality  (updates feedback_data)
    """

    def __init__(self):
        super().__init__("Data Quality Agent", "Combined LLM: speaker clean + quality score in one call.")

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing {self.name} (combined LLM call)")
        fb = payload.get("feedback_data", {})
        evt = payload.get("event_data", {})

        raw_speaker = evt.get("raw_speaker", "")
        feedback_text = (
            f"Valuable: {fb.get('aspect_most_valuable', '')}\n"
            f"Improvements: {fb.get('improvements_suggestions', '')}\n"
            f"Topics: {fb.get('future_topics', '')}"
        )

        result = _combined_llm_call(raw_speaker, feedback_text)

        # Update event_data with cleaned speaker name
        clean_speaker = result["speaker"]
        evt["speaker_name"] = clean_speaker
        evt["name"] = f"Guest Lecture by {clean_speaker}"
        payload["event_data"] = evt

        # Update feedback_data with quality score
        fb["data_quality_score"] = result["quality"]
        fb["is_duplicate"] = False
        payload["feedback_data"] = fb

        return payload


class DatabaseSyncAgent(BaseAgent):
    def __init__(self):
        super().__init__("Database Sync Agent", "Commits validated data to InsForge via REST API.")

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        stu = payload.get("student_data", {})
        evt = payload.get("event_data", {})
        fb = payload.get("feedback_data", {})

        if not stu.get("roll_no") or not evt.get("speaker_name"):
            logger.warning("Missing vital data (roll_no / speaker_name). Skipping row.")
            return payload

        try:
            from backend.utils.insforge_db import api_upsert, api_select, api_insert

            # 1. Upsert Student
            stu_row = api_upsert(
                "students",
                {
                    "roll_no": stu["roll_no"],
                    "email": stu.get("email"),
                    "name": stu["name"],
                    "department": stu["department"],
                },
                "roll_no",
            )
            student_id = stu_row[0]["id"] if stu_row else None

            # 2. Upsert Event
            evt_row = execute_one(
                "SELECT id FROM events WHERE speaker_name=%s AND venue_date=%s",
                (evt["speaker_name"], evt["venue_date"]),
            )
            if evt_row:
                event_id = evt_row["id"]
            else:
                new_evt = api_insert(
                    "events",
                    {
                        "speaker_name": evt["speaker_name"],
                        "venue_date": evt["venue_date"],
                        "department": evt["department"],
                    },
                )
                event_id = new_evt[0]["id"] if new_evt else None

            # 3. Upsert Feedback Response
            sub_at = fb["submitted_at"]
            try:
                sub_at = (
                    pd.to_datetime(sub_at).strftime("%Y-%m-%d %H:%M:%S%z")
                    if pd.notna(sub_at)
                    else datetime.now().isoformat()
                )
            except Exception:
                sub_at = datetime.now().isoformat()

            fb_check = execute_one(
                "SELECT id FROM feedback_responses WHERE event_id=%s AND student_id=%s",
                (event_id, student_id),
            )

            payload_data = {
                "event_id": event_id,
                "student_id": student_id,
                "submitted_at": sub_at,
                "extracted_date": str(fb.get("extracted_date")) if fb.get("extracted_date") and str(fb.get("extracted_date")).strip() else None,
                "extracted_time": str(fb.get("extracted_time")) if fb.get("extracted_time") and str(fb.get("extracted_time")).strip() else None,
                "session_rating": fb["session_rating"],
                "session_help_understanding": fb["session_help_understanding"],
                "aspect_most_valuable": fb["aspect_most_valuable"],
                "improvements_suggestions": fb["improvements_suggestions"],
                "future_topics": fb["future_topics"],
                "data_quality_score": fb["data_quality_score"],
                "is_duplicate": fb["is_duplicate"],
            }

            if fb_check:
                from backend.utils.insforge_db import api_update
                api_update("feedback_responses", "id", fb_check["id"], payload_data)
                fb_id = fb_check["id"]
            else:
                fb_row = api_insert("feedback_responses", payload_data)
                fb_id = fb_row[0]["id"] if fb_row else None

            payload["response_id"] = fb_id

        except Exception as e:
            logger.error(f"DB Sync error: {e}")
            payload["error"] = str(e)

        return payload


# ─────────────────────────────────────────────────────────────────────────────
#  SUPERVISOR
# ─────────────────────────────────────────────────────────────────────────────

class DataOrchestratorSupervisor(SupervisorAgent):
    def __init__(self):
        super().__init__("Data Orchestrator Supervisor", "Routes payloads across isolated LLM agents.")

        self.register_subagent(IdentityResolutionAgent())
        self.register_subagent(EventNormalizationAgent())
        self.register_subagent(FeedbackExtractionAgent())
        self.register_subagent(DataQualityAgent())   # ← single combined LLM call here
        self.register_subagent(DatabaseSyncAgent())

    def orchestrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(
            f"Data Orchestrator: routing through {len(self.subagents)} specialists "
            f"(1 combined LLM call / row)..."
        )

        if "rows" in payload:
            processed = []
            for row in payload["rows"]:
                state: Dict[str, Any] = {"row": row}
                for agent in self.subagents:
                    state = agent.execute(state)
                    if "error" in state:
                        break
                processed.append(state)
            payload["processed_rows"] = processed
        else:
            state = payload
            for agent in self.subagents:
                state = agent.execute(state)
                if "error" in state:
                    break
            payload = state

        return payload
