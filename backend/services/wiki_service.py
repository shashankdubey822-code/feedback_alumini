"""
Wiki Service - Manages Karpathy's LLM Wiki (Ingest, Query, Lint, and Supabase Storage Sync)
"""

import os
import re
import sqlite3
import json
import time
import threading
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import urllib.request
import urllib.parse
import urllib.error
from backend.config import get_config
from backend.utils.logger import get_section_logger
from backend.utils.supabase_helper import (
    supabase_upload_file,
    supabase_download_file,
    supabase_list_files,
    supabase_delete_file,
    is_supabase_active
)
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

logger = get_section_logger('wiki')

# Class-level compilation logger and queue state
_ingest_logs: List[str] = []
_ingest_progress: Dict[str, Any] = {"status": "IDLE", "current": 0, "total": 0, "active_session": ""}
_queue_lock = threading.Lock()

class SupabaseChatMessageHistory(BaseChatMessageHistory):
    """Custom LangChain memory class for Supabase Storage"""
    def __init__(self, session_id: str, bucket: str, fallback_history: List[Dict[str, str]] = None):
        self.session_id = session_id
        self.bucket = bucket
        self.path = f"memory/{session_id}.json"
        self.fallback_history = fallback_history or []
        
    @property
    def messages(self) -> List[BaseMessage]:
        if is_supabase_active():
            try:
                file_bytes = supabase_download_file(self.bucket, self.path)
                if file_bytes:
                    items = json.loads(file_bytes.decode('utf-8'))
                    return messages_from_dict(items)
            except Exception:
                pass
                
        # Fallback to frontend history
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        msgs = []
        for h in self.fallback_history:
            role = h.get('role', 'user')
            content = h.get('content', '')
            if role == 'user':
                msgs.append(HumanMessage(content=content))
            elif role in ('ai', 'assistant', 'model'):
                msgs.append(AIMessage(content=content))
        return msgs

    def add_messages(self, messages: List[BaseMessage]) -> None:
        if not is_supabase_active():
            return
        try:
            current_messages = self.messages
            current_messages.extend(messages)
            items = messages_to_dict(current_messages)
            history_bytes = json.dumps(items, indent=2).encode('utf-8')
            supabase_upload_file(self.bucket, self.path, history_bytes, "application/json")
        except Exception as e:
            logger.error(f"Error saving chat history to Supabase: {str(e)}")

    def clear(self) -> None:
        if is_supabase_active():
            supabase_delete_file(self.bucket, self.path)


class WikiService:
    """Manages the creation, synchronization, querying, and linting of the Markdown Wiki"""

    def __init__(self):
        config = get_config()()
        self.wiki_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'wiki')
        self.pages_dir = os.path.join(self.wiki_dir, 'pages')
        self.bucket = config.SUPABASE_BUCKET
        self.gemini_key = config.GEMINI_API_KEY
        self.groq_key = config.GROQ_API_KEY
        
        # Local dir creation safety
        os.makedirs(self.wiki_dir, exist_ok=True)
        os.makedirs(self.pages_dir, exist_ok=True)
        for sub in ['events', 'speakers', 'concepts', 'suggestions']:
            os.makedirs(os.path.join(self.pages_dir, sub), exist_ok=True)

    # ─── CORE FILE ACCESSORS ──────────────────────────────────────────────────

    def write_wiki_file(self, rel_path: str, content: str) -> bool:
        """Write content to local disk AND upload to Supabase Storage if configured"""
        local_path = os.path.join(self.pages_dir, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # 1. Write locally
        try:
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Local write failed for '{rel_path}': {str(e)}")

        # 2. Upload to Supabase Storage
        if is_supabase_active():
            content_bytes = content.encode('utf-8')
            success = supabase_upload_file(self.bucket, f"pages/{rel_path}", content_bytes, "text/markdown")
            if success:
                logger.info(f"Synced '{rel_path}' to Supabase bucket '{self.bucket}'")
            return success

        return True

    def read_wiki_file(self, rel_path: str) -> Optional[str]:
        """Read content from Supabase Storage, falling back to local file if offline"""
        # 1. Try Supabase Storage first
        if is_supabase_active():
            file_bytes = supabase_download_file(self.bucket, f"pages/{rel_path}")
            if file_bytes is not None:
                return file_bytes.decode('utf-8')

        # 2. Fallback to Local Disk
        local_path = os.path.join(self.pages_dir, rel_path)
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Local read failed for '{rel_path}': {str(e)}")
        return None

    def list_wiki_pages(self) -> List[str]:
        """Get relative paths of all pages in the Wiki"""
        all_pages = []
        
        if is_supabase_active():
            # List files from Supabase Storage
            # Walk through subdirectories
            for sub in ['', 'events', 'speakers', 'concepts', 'suggestions']:
                files = supabase_list_files(self.bucket, f"pages/{sub}".strip('/'))
                for f in files:
                    name = f.get('name')
                    if name and name.endswith('.md'):
                        path = f"{sub}/{name}".strip('/')
                        all_pages.append(path)
            if all_pages:
                return sorted(list(set(all_pages)))

        # Fallback to local file scanning
        for root, _, files in os.walk(self.pages_dir):
            for file in files:
                if file.endswith('.md'):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, self.pages_dir).replace('\\', '/')
                    all_pages.append(rel_p)
        return sorted(all_pages)

    # ─── INITIALIZATION ───────────────────────────────────────────────────────

    def initialize_wiki(self, force: bool = False) -> bool:
        """Set up initial directory structure, index, logs, and schema"""
        logger.info("Initializing Wiki schemas and templates...")
        
        # Check if already initialized
        if not force and self.read_wiki_file('index.md') is not None:
            logger.info("Wiki is already initialized. Skipping template injection.")
            return True

        # 1. Create schema.md
        schema_content = """# Wiki Schema & Guidelines

Welcome to the AI-maintained Knowledge Base of guest lecture feedback.

## Directory Structure
- `events/` - Summaries of individual guest lectures, named as `[YYYY-MM-DD]_[Speaker_Name].md`.
- `speakers/` - Dossier pages compiling history, rating trends, and sentiments for each speaker, named as `[Speaker_Name].md`.
- `concepts/` - Concept or topic pages tracking student interest in specific areas (e.g. `[[Resume_Building]]`, `[[Artificial_Intelligence]]`), named as `[Topic_Name].md`.
- `suggestions/` - Specific critique categories (e.g. `[[More_Interaction]]`, `[[Duration_and_Pacing]]`), named as `[Category_Name].md`.
- `index.md` - Content catalog/index.
- `log.md` - Chronological log of operations.

## Linking Rules
- Use double-bracket wiki links to interconnect entities (e.g., `[[Jane_Doe]]` inside an event page).
- Every event page must link back to its corresponding `[[speakers/Speaker_Name]]` and relevant `[[concepts/Concept_Name]]`.
"""
        self.write_wiki_file('schema.md', schema_content)

        # 2. Create index.md
        index_content = """# AI Knowledge Wiki Index

Welcome to the central knowledge index. This index is automatically updated by the AI.

## Index of Pages

### Master Logs
- [[schema.md]] - Schema & guidelines.
- [[log.md]] - Chronological log of actions.

### 🎤 Speaker Profiles
*No speakers compiled yet.*

### 📅 Guest Lectures
*No guest lectures compiled yet.*

### 💡 Core Concept Hubs
*No topics compiled yet.*

### 🛠️ Suggestion Categories
*No suggestions compiled yet.*
"""
        self.write_wiki_file('index.md', index_content)

        # 3. Create log.md
        log_content = f"""# Operation Log

Append-only history of Wiki operations.

## [{datetime.now().strftime('%Y-%m-%d')}] system | Initialization
- Initialized directory structures.
- Created `schema.md`, `index.md`, and `log.md`.
"""
        self.write_wiki_file('log.md', log_content)
        return True

    # ─── COMPILER ENGINE (INGEST OPERATION) ───────────────────────────────────

    def compile_session(self, speaker: str, date_str: str, feedback_rows: List[Dict[str, Any]]) -> str:
        """
        Compile feedback rows into events, speaker, and concept pages.
        Runs batch prompts using Gemini, falling back to a rule-based offline generator.
        """
        self.log_compilation(f"Compiling feedback for '{speaker}' ({date_str}) - {len(feedback_rows)} responses...")
        
        # Prepare aggregated data payload
        total_responses = len(feedback_rows)
        ratings = [r.get('session_rating') for r in feedback_rows if r.get('session_rating') is not None]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
        
        understanding_levels = {}
        for r in feedback_rows:
            shu = r.get('session_help_understanding')
            if shu:
                understanding_levels[shu] = understanding_levels.get(shu, 0) + 1
        
        valuable_aspects = [r.get('aspect_most_valuable') for r in feedback_rows if r.get('aspect_most_valuable') and len(str(r.get('aspect_most_valuable')).strip()) > 5]
        critiques = [r.get('improvements_suggestions') for r in feedback_rows if r.get('improvements_suggestions') and len(str(r.get('improvements_suggestions')).strip()) > 5]
        requests = [r.get('future_topics') for r in feedback_rows if r.get('future_topics') and len(str(r.get('future_topics')).strip()) > 5]

        # Normalize file names (replace spaces with underscores)
        safe_speaker = speaker.replace(' ', '_').replace('.', '')
        safe_event = f"{date_str}_{safe_speaker}"

        # ─── TRIGGER COMPILER EXECUTION: 3-LAYER FALLBACK ────────────────────────
        # Layer 1: Gemini Flash — 15 RPM, 1 million tokens/min free tier
        if self.gemini_key:
            success, err_msg = self._run_generative_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via Gemini AI.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ Gemini failed: {err_msg}. Trying Groq...")

        # Layer 2: Groq (Llama 3.3 70B) — backup if Gemini is unavailable
        if self.groq_key:
            success, err_msg = self._run_groq_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via Groq Llama 3.3 70B.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ Groq failed: {err_msg}. Using offline heuristics...")
        
        # Execute Offline Heuristics compilation
        self._run_offline_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
        self.log_compilation(f"Successfully compiled '{speaker}' ({date_str}) using Local Offline Heuristic Compiler.")
        return safe_event

    def _run_groq_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                         total: int, avg_rating: float, shu: Dict[str, int],
                         val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call Groq API (Llama 3.3 70B) - Primary AI: 14,400 free calls/day"""
        prompt = self._build_wiki_prompt(safe_event, safe_speaker, speaker, date_str, total, avg_rating, shu, val, crit, req)
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            req_data = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7
            }).encode('utf-8')

            request = urllib.request.Request(
                url, data=req_data,
                headers={
                    'Authorization': f'Bearer {self.groq_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'DataLens/1.0'
                }
            )

            with urllib.request.urlopen(request, timeout=60) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                data = json.loads(res_body['choices'][0]['message']['content'])
                return self._write_wiki_pages(safe_event, safe_speaker, speaker, date_str, avg_rating, data)

        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                err_json = json.loads(err_body)
                exact_msg = err_json.get('error', {}).get('message', err_body)
            except:
                exact_msg = str(e)
            error_msg = f"HTTP {e.code}: {exact_msg}"
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Groq-Compile", speaker, error_msg)
            return False, error_msg
        except Exception as e:
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Groq-Compile", speaker, str(e))
            return False, str(e)

    def _build_wiki_prompt(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                           total: int, avg_rating: float, shu: Dict[str, int],
                           val: List[str], crit: List[str], req: List[str]) -> str:
        """Shared prompt builder for all AI providers"""
        return f"""
[SYSTEM INITIALIZATION] 
ROLE: Chief Pedagogical Data Scientist & Alumni Relations Expert
CAPABILITY: Extreme Deep Data Analysis, Psychological Sentiment Profiling, and Actionable Intelligence Synthesis.

You are analyzing raw student survey data from an alumni guest lecture. Do NOT just summarize. You must uncover hidden correlations, diagnose pedagogical friction points, and generate highly structured, authoritative executive reports.

[SESSION DATA STREAM]
- Target Entity (Speaker): {speaker}
- Chronology: {date_str}
- Sample Size: {total} student responses
- Quantitative Baseline (Avg Rating): {avg_rating}/5
- Pedagogical Impact Matrix (Understanding Levels): {json.dumps(shu)}
- High-Value Anchors (What worked): {json.dumps(val[:30])}
- Friction Points & Critiques (What failed): {json.dumps(crit[:30])}
- Forward Trajectory (Requested topics): {json.dumps(req[:30])}

[MISSION DIRECTIVE]
Generate THREE high-density intelligence dossiers formatted in strict Markdown. Use double-bracket WikiLinks (e.g. `[[speakers/{safe_speaker}]]`, `[[concepts/Advanced_AI]]`) liberally.

1. `events/{safe_event}.md`: Executive Summary, Quantitative Breakdown, Deep Sentiment Analysis, Pedagogical Successes, Critical Failure Points.
2. `speakers/{safe_speaker}.md`: Speaker Archetype & Style Profile, Aggregate Historical Performance, Core Strengths, Actionable Directives. If rating below 3.5, include "Risk Mitigation Strategy".
3. `concepts/New_Concept.md` or `suggestions/New_Critique.md`: Identify the single most critical recurring systemic issue (suggestion) OR highest-velocity emerging interest (concept).

[OUTPUT SCHEMA]
Strict JSON object only. No markdown fences outside the JSON values.
{{
  "event_page": "markdown text for events/{safe_event}.md",
  "speaker_page": "markdown text for speakers/{safe_speaker}.md",
  "new_concept_name": "Name_of_Concept",
  "new_concept_page": "markdown text for concepts/Name_of_Concept.md",
  "new_suggestion_name": "Name_of_Suggestion",
  "new_suggestion_page": "markdown text for suggestions/Name_of_Suggestion.md",
  "speaker_update_summary": "1 sentence executive tl;dr for the speaker's log"
}}
"""

    def _write_wiki_pages(self, safe_event: str, safe_speaker: str, speaker: str,
                          date_str: str, avg_rating: float, data: dict) -> Tuple[bool, str]:
        """Shared page-writing logic used by all AI providers"""
        self.write_wiki_file(f"events/{safe_event}.md", data['event_page'])

        existing_speaker = self.read_wiki_file(f"speakers/{safe_speaker}.md")
        speaker_content = data['speaker_page']
        if existing_speaker:
            speaker_content = f"{existing_speaker}\n\n## Update: Session on {date_str}\n- Aggregated score: {avg_rating}/5\n- {data.get('speaker_update_summary', 'Lecture processed.')}"
        self.write_wiki_file(f"speakers/{safe_speaker}.md", speaker_content)

        c_name = data.get('new_concept_name')
        if c_name:
            self.write_wiki_file(f"concepts/{c_name.replace(' ', '_')}.md", data['new_concept_page'])
        s_name = data.get('new_suggestion_name')
        if s_name:
            self.write_wiki_file(f"suggestions/{s_name.replace(' ', '_')}.md", data['new_suggestion_page'])

        self._update_wiki_indexes(speaker, date_str, safe_event, safe_speaker, c_name, s_name)
        return True, "Success"

    def _run_generative_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str, 
                               total: int, avg_rating: float, shu: Dict[str, int], 
                               val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call Gemini API to generate professional interlinked markdown pages"""
        prompt = f"""
[SYSTEM INITIALIZATION] 
ROLE: Chief Pedagogical Data Scientist & Alumni Relations Expert
CAPABILITY: Extreme Deep Data Analysis, Psychological Sentiment Profiling, and Actionable Intelligence Synthesis.

You are analyzing raw student survey data from an alumni guest lecture. Do NOT just summarize. You must uncover hidden correlations, diagnose pedagogical friction points (why students struggled or excelled), and generate highly structured, authoritative executive reports.

[SESSION DATA STREAM]
- Target Entity (Speaker): {speaker}
- Chronology: {date_str}
- Sample Size: {total} student responses
- Quantitative Baseline (Avg Rating): {avg_rating}/5
- Pedagogical Impact Matrix (Understanding Levels): {json.dumps(shu)}
- High-Value Anchors (What worked): {json.dumps(val[:30])}
- Friction Points & Critiques (What failed): {json.dumps(crit[:30])}
- Forward Trajectory (Requested topics): {json.dumps(req[:30])}

[MISSION DIRECTIVE]
Generate THREE high-density intelligence dossiers formatted in strict Markdown. You must liberally use double-bracket WikiLinks (e.g. `[[speakers/{safe_speaker}]]`, `[[concepts/Advanced_AI]]`, `[[suggestions/Pacing_Control]]`) to weave a massive, interconnected knowledge graph.

1. `events/{safe_event}.md`:
   - Must contain: Executive Summary, Quantitative Breakdown, Deep Sentiment Analysis, Pedagogical Successes, and Critical Failure Points. Connect all findings to specific student quotes or trends.

2. `speakers/{safe_speaker}.md`:
   - Must contain: Speaker Archetype & Style Profile, Aggregate Historical Performance, Core Strengths, and Actionable Directives for their next lecture. If rating is below 3.5, provide a "Risk Mitigation Strategy". 

3. `concepts/New_Concept.md` or `suggestions/New_Critique.md`:
   - Identify the single most critical recurring systemic issue (suggestion) OR the highest-velocity emerging interest (concept). Write an abstract defining this and its impact on the curriculum.

[OUTPUT SCHEMA]
Strict JSON object only. No markdown fences outside the JSON values.
{{
  "event_page": "markdown text for events/{safe_event}.md",
  "speaker_page": "markdown text for speakers/{safe_speaker}.md",
  "new_concept_name": "Name_of_Concept",
  "new_concept_page": "markdown text for concepts/Name_of_Concept.md",
  "new_suggestion_name": "Name_of_Suggestion",
  "new_suggestion_page": "markdown text for suggestions/Name_of_Suggestion.md",
  "speaker_update_summary": "1 sentence executive tl;dr for the speaker's log"
}}
"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
            req_data = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }).encode('utf-8')
            
            request = urllib.request.Request(
                url, 
                data=req_data, 
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(request, timeout=30) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                text_out = res_body['candidates'][0]['content']['parts'][0]['text']
                data = json.loads(text_out)
                return self._write_wiki_pages(safe_event, safe_speaker, speaker, date_str, avg_rating, data)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                err_json = json.loads(err_body)
                exact_msg = err_json.get('error', {}).get('message', err_body)
            except:
                exact_msg = str(e)
            
            error_msg = f"HTTP {e.code}: {exact_msg}"
            logger.error(f"Generative ingest HTTPError: {error_msg}")
            
            # Log specifically to gemini errors
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Compile", speaker, error_msg, err_body if 'err_body' in locals() else str(e))
            return False, error_msg
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Generative ingest failed: {error_msg}")
            
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Compile", speaker, error_msg, str(e))
            return False, error_msg

    def _run_offline_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str, 
                             total: int, avg_rating: float, shu: Dict[str, int], 
                             val: List[str], crit: List[str], req: List[str]):
        """Rules-based offline backup generator when no API keys are available"""
        # 1. Event page
        event_md = f"""# Guest Lecture Summary: {speaker}
- **Date**: {date_str}
- **Speaker**: [[speakers/{safe_speaker}]]
- **Total Submissions**: {total} student responses
- **Average Lecture Rating**: {avg_rating}/5

## Overall Reception
Students rated this lecture with an average score of {avg_rating}/5. 

## Student Feedback Highlights
### Valuable Aspects
{chr(10).join([f'- {v}' for v in val[:5]]) if val else '*No valuable aspects recorded.*'}

### Actionable Critiques & Suggestions
{chr(10).join([f'- {c}' for c in crit[:5]]) if crit else '*No critiques recorded.*'}

### Requested Future Focus Areas
{chr(10).join([f'- {r}' for r in req[:5]]) if req else '*No requests recorded.*'}
"""
        self.write_wiki_file(f"events/{safe_event}.md", event_md)

        # 2. Speaker Profile
        existing_speaker = self.read_wiki_file(f"speakers/{safe_speaker}.md")
        if existing_speaker:
            speaker_md = f"""{existing_speaker}
            
## Update: Session on {date_str}
- **Lecture Date**: {date_str}
- **Aggregate Rating**: {avg_rating}/5
- **Responses Analysed**: {total}
"""
        else:
            speaker_md = f"""# Speaker Dossier: {speaker}
- **Aggregate Historical Rating**: {avg_rating}/5
- **Lectures Hosted**: 1

## Historical Record
- [[events/{safe_event}]] ({date_str}) - Rating: {avg_rating}/5 from {total} reviews.

## Performance Overview
This speaker has hosted 1 guest lecture. Students highlighted their valuable insights.
"""
        self.write_wiki_file(f"speakers/{safe_speaker}.md", speaker_md)

        # 3. Simple topic extracting
        c_name = None
        if req:
            c_name = req[0].strip().title()
            c_safe = c_name.replace(' ', '_').replace('.', '')
            c_md = f"""# Concept Hub: {c_name}

This concept page compiles student feedback and interests about **{c_name}**.

## Associated Events
- [[events/{safe_event}]] ({date_str}) - Students requested this topic for future sessions.
"""
            self.write_wiki_file(f"concepts/{c_safe}.md", c_md)

        # 4. Simple suggestion extracting
        s_name = None
        if crit:
            s_name = "Duration_and_Pacing" if any(w in crit[0].lower() for w in ['time', 'duration', 'long', 'slow', 'pace']) else "Interaction_and_Q&A"
            s_safe = s_name.replace(' ', '_')
            s_md = f"""# Suggestion Category: {s_name.replace('_', ' ')}

This page logs constructive critiques regarding **{s_name.replace('_', ' ')}** in guest lectures.

## Associated Incidents
- [[events/{safe_event}]] ({date_str}) - Students suggested adjustments in this category.
"""
            self.write_wiki_file(f"suggestions/{s_safe}.md", s_md)

        # 5. Update index & logs
        self._update_wiki_indexes(speaker, date_str, safe_event, safe_speaker, c_name, s_name)

    def _update_wiki_indexes(self, speaker: str, date_str: str, safe_event: str, safe_speaker: str, 
                             concept: Optional[str], suggestion: Optional[str]):
        """Add new entries into the central index.md and appends to log.md"""
        # Update log.md
        log_content = self.read_wiki_file('log.md') or "# Operation Log\n"
        log_entry = f"## [{datetime.now().strftime('%Y-%m-%d')}] ingest | {speaker} ({date_str})\n- Compiled new event page [[events/{safe_event}]]\n- Updated speaker dossier [[speakers/{safe_speaker}]]\n"
        if concept:
            log_entry += f"- Created/Updated concept hub [[concepts/{concept.replace(' ', '_')}]]\n"
        self.write_wiki_file('log.md', f"{log_content}\n{log_entry}")

        # Update index.md
        index_content = self.read_wiki_file('index.md') or "# AI Knowledge Wiki Index\n"
        
        # 1. Update Speaker list
        sp_link = f"- [[speakers/{safe_speaker}]] - Profile for {speaker}."
        if sp_link not in index_content:
            if "*No speakers compiled yet.*" in index_content:
                index_content = index_content.replace("*No speakers compiled yet.*", sp_link)
            else:
                index_content = index_content.replace("### 🎤 Speaker Profiles", f"### 🎤 Speaker Profiles\n{sp_link}")

        # 2. Update Event list
        ev_link = f"- [[events/{safe_event}]] - Session on {date_str}."
        if ev_link not in index_content:
            if "*No guest lectures compiled yet.*" in index_content:
                index_content = index_content.replace("*No guest lectures compiled yet.*", ev_link)
            else:
                index_content = index_content.replace("### 📅 Guest Lectures", f"### 📅 Guest Lectures\n{ev_link}")

        # 3. Update Concept list
        if concept:
            c_safe = concept.replace(' ', '_')
            c_link = f"- [[concepts/{c_safe}]] - Student interest in {concept}."
            if c_link not in index_content:
                if "*No topics compiled yet.*" in index_content:
                    index_content = index_content.replace("*No topics compiled yet.*", c_link)
                else:
                    index_content = index_content.replace("### 💡 Core Concept Hubs", f"### 💡 Core Concept Hubs\n{c_link}")

        # 4. Update Suggestion list
        if suggestion:
            s_safe = suggestion.replace(' ', '_')
            s_link = f"- [[suggestions/{s_safe}]] - Improvement track: {suggestion.replace('_', ' ')}."
            if s_link not in index_content:
                if "*No suggestions compiled yet.*" in index_content:
                    index_content = index_content.replace("*No suggestions compiled yet.*", s_link)
                else:
                    index_content = index_content.replace("### 🛠️ Suggestion Categories", f"### 🛠️ Suggestion Categories\n{s_link}")

        self.write_wiki_file('index.md', index_content)

    # ─── BATCH INGESTION QUEUE (RPM THROTTLED) ───────────────────────────────

    def start_batch_ingest_queue(self, sessions: List[Tuple[str, str]]) -> str:
        """Start a background compilation queue processing sessions sequentially"""
        global _ingest_progress, _ingest_logs
        
        with _queue_lock:
            if _ingest_progress["status"] == "PROCESSING":
                return "Queue already running."
            
            _ingest_logs = []
            _ingest_progress = {
                "status": "PROCESSING",
                "current": 0,
                "total": len(sessions),
                "active_session": ""
            }

        def run_queue():
            global _ingest_progress
            logger.info(f"Starting Ingest queue for {len(sessions)} sessions...")
            from backend.utils.db_helper import get_db_connection
            
            db_path = get_config()().DATABASE_PATH
            
            for idx, (speaker, date_str) in enumerate(sessions):
                with _queue_lock:
                    _ingest_progress["current"] = idx + 1
                    _ingest_progress["active_session"] = f"{speaker} ({date_str})"
                
                try:
                    # Fetch student responses for this session
                    conn = get_db_connection(db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT * FROM dashboard_data 
                        WHERE alumni_speaker_name = ? AND date_of_lecture = ?
                    ''', (speaker, date_str))
                    rows = [dict(r) for r in cursor.fetchall()]
                    conn.close()

                    if rows:
                        self.compile_session(speaker, date_str, rows)
                    else:
                        self.log_compilation(f"Skipping: No database records found for '{speaker}' on '{date_str}'.")
                except Exception as e:
                    self.log_compilation(f"Error compiling session '{speaker}': {str(e)}")

                # Throttling to respect Gemini 15 RPM free tier limits (sleep 4 seconds per session)
                time.sleep(4.0)

            with _queue_lock:
                _ingest_progress["status"] = "COMPLETE"
                _ingest_progress["active_session"] = ""
            self.log_compilation("Ingestion queue completed successfully!")

        threading.Thread(target=run_queue, daemon=True).start()
        return "Queue started."

    def log_compilation(self, text: str):
        """Append log message to volatile queue log cache"""
        global _ingest_logs
        timestamp = datetime.now().strftime('%H:%M:%S')
        msg = f"[{timestamp}] {text}"
        logger.info(text)
        _ingest_logs.append(msg)

    def get_queue_status(self) -> Dict[str, Any]:
        """Fetch current ingestion queue status and logs for the frontend console"""
        global _ingest_progress, _ingest_logs
        with _queue_lock:
            return {
                "progress": _ingest_progress.copy(),
                "logs": list(_ingest_logs)
            }

    # ─── QUERY SYNTHESIZER (RAG ON WIKI) ──────────────────────────────────────

    def query_wiki(self, question: str, history: List[Dict[str, str]] = None, session_id: str = None) -> Dict[str, Any]:
        """
        Query the compiled Wiki.
        Performs vector-RAG, loads relevant files, and feeds them into the LLM context.
        """
        logger.info(f"RAG Wiki Query: '{question}' with history length {len(history) if history else 0}, session_id: {session_id}")
        
        # 1. Fetch relevant feedback hits via vector RAG
        search_query = question
        if history:
            user_msgs = [h.get('content', '') for h in history if h.get('role') == 'user']
            if user_msgs:
                search_query += " " + " ".join(user_msgs[-2:])
                
        from backend.services.rag_service import RAGService
        rag = RAGService()
        similar_rows = rag.search_similar_feedback(search_query, limit=5)
        
        # 2. Extract matching entities (find matching markdown pages)
        pages = self.list_wiki_pages()
        matched_pages = []
        tokens = [t.lower() for t in search_query.split() if len(t) > 3]
        for p in pages:
            p_lower = p.lower()
            if any(t in p_lower for t in tokens):
                content = self.read_wiki_file(p)
                if content:
                    matched_pages.append((p, content))
        matched_pages = matched_pages[:3]
        
        # 3. SYNTHESIZE RESPONSE
        context_str = ""
        if matched_pages:
            context_str += "=== RELEVANT WIKI PAGES ===\n"
            for p_path, p_content in matched_pages:
                context_str += f"File: [[{p_path}]]\n{p_content}\n\n"
        
        if similar_rows:
            context_str += "=== STUDENT FEEDBACK DATA ===\n"
            for r in similar_rows:
                student_name = r.get('name_of_student') or 'Anonymous'
                context_str += f"- Student: {student_name}, Speaker: {r.get('alumni_speaker_name')}, Valuable aspect: {r.get('aspect_most_valuable')}, Critique/Suggestions: {r.get('improvements_suggestions')}\n"

        if not context_str.strip():
            context_str = "No compiled wiki pages or feedback records matched this query in the database."

        # Softened Prompt for Factual Integrity and Counter-Questioning
        system_instruction = """You are a smart, highly empathetic, and human-like AI analyst for a college alumni feedback dashboard. 

CRITICAL RULES:
1. You have access to the data provided below in the "AVAILABLE DATA" section. Base your answers heavily on this context.
2. If the user asks about a specific person, event, or topic that is not in the AVAILABLE DATA, politely explain that you don't have that specific data in your current context yet, but offer to answer based on what you do know or ask them to compile that session. Do NOT sound like a robotic data parser.
3. If the user asks general-knowledge questions (e.g., how to code, general trivia, math), decline politely: "I am your alumni feedback assistant. I focus on guest lecture data. Please ask questions about the compiled sessions."
4. If the data is empty, suggest they compile the lectures first.
5. If the user asks to "name the students" or "name them", inspect the "Student:" prefix in the AVAILABLE DATA. If no names are present, explain that the feedback is anonymous.
6. If the user's question is ambiguous, ask a clarifying counter-question.
7. Be conversational, warm, and highly humanized. Use words like "I", "you", "we". Greet the user by their name if they told you it previously!

FORMATTING AND LENGTH RULES (CRITICAL):
1. NO PARAGRAPHS ALLOWED. You must respond ONLY in short, concise bullet points (pointers).
2. Maximum length of the entire response is 50 words. Be ultra-brief.
3. NEVER put multiple bullet points on the same line or inside a paragraph. You MUST separate each bullet point with a newline.
4. Put the direct answer or main statistic FIRST.
5. Only use double-bracket WikiLinks (e.g. [[speakers/Name]]) when referring to compiled files that actually exist in the AVAILABLE DATA.

=== AVAILABLE DATA ===
{context_str}
"""

        # Setup LangChain LLM with fallback support for API limits
        llm = None
        gemini_fallback = None
        
        if self.gemini_key:
            gemini_fallback = ChatGoogleGenerativeAI(google_api_key=self.gemini_key, model="gemini-2.5-flash", temperature=0.1, max_retries=1)
            
        if self.groq_key:
            llm = ChatGroq(api_key=self.groq_key, model="llama-3.3-70b-versatile", temperature=0.1, max_retries=1)
            if gemini_fallback:
                llm = llm.with_fallbacks([gemini_fallback])
        elif gemini_fallback:
            llm = gemini_fallback
        if llm:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_instruction),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}")
            ])
            
            chain = prompt | llm
            
            # Use RunnableWithMessageHistory for real AI memory
            with_message_history = RunnableWithMessageHistory(
                chain,
                lambda sid: SupabaseChatMessageHistory(sid, self.bucket, fallback_history=history),
                input_messages_key="question",
                history_messages_key="history",
            )
            
            try:
                # If no session_id is provided, generate a fallback local session ID for this request
                effective_session_id = session_id if session_id else "default_session"
                response = with_message_history.invoke(
                    {
                        "question": question,
                        "context_str": context_str
                    },
                    config={"configurable": {"session_id": effective_session_id}}
                )
                synthesis = response.content
            except Exception as e:
                logger.error(f"LangChain Runnable error: {str(e)}")
                synthesis = f"Error generating response: {str(e)}"
        else:
            synthesis = f"""No AI available (API keys missing). Here's what the database shows for your query:
- **Matching Wiki Pages**: {', '.join([f'[[{p[0]}]]' for p in matched_pages]) if matched_pages else 'None'}
- **Feedback rows matched**: {len(similar_rows)}"""

        return {"answer": synthesis, "citations": [p[0] for p in matched_pages]}

    def clear_memory(self, session_id: str) -> bool:
        """Delete chat history for the given session ID from Supabase bucket"""
        if is_supabase_active() and session_id:
            try:
                path = f"memory/{session_id}.json"
                supabase_delete_file(self.bucket, path)
                logger.info(f"Deleted memory for session '{session_id}' from Supabase bucket.")
                return True
            except Exception as e:
                logger.error(f"Failed to delete memory from Supabase bucket: {e}")
        return False

    # ─── WIKI LINTER (HEALTH CHECKS) ──────────────────────────────────────────

    def run_wiki_linter(self) -> Dict[str, Any]:
        """Scan the wiki files for broken wiki links, orphans, and empty files"""
        pages = self.list_wiki_pages()
        
        broken_links = []
        orphan_pages = []
        empty_files = []
        
        # Trace link map
        incoming_links = {p: [] for p in pages}
        
        # Regex to find links: [[file_name]]
        link_pattern = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
        
        for p in pages:
            content = self.read_wiki_file(p)
            if not content or not content.strip():
                empty_files.append(p)
                continue
            
            # Find links
            links = link_pattern.findall(content)
            for link in links:
                link = link.strip()
                # Try relative paths
                resolved = None
                
                # Check direct match
                if link in pages:
                    resolved = link
                elif f"{link}.md" in pages:
                    resolved = f"{link}.md"
                else:
                    # Check in folders
                    for folder in ['events', 'speakers', 'concepts', 'suggestions']:
                        check_path = f"{folder}/{link}".replace('//', '/')
                        if check_path in pages:
                            resolved = check_path
                            break
                        elif f"{check_path}.md" in pages:
                            resolved = f"{check_path}.md"
                            break
                            
                if resolved:
                    incoming_links[resolved].append(p)
                else:
                    # Link is broken
                    broken_links.append({
                        "source_file": p,
                        "broken_link": link
                    })
                    
        # Find orphans (excluding index.md, log.md, and schema.md)
        for p, sources in incoming_links.items():
            if not sources and p not in ['index.md', 'log.md', 'schema.md']:
                orphan_pages.append(p)
                
        return {
            "status": "COMPLETED",
            "total_pages": len(pages),
            "broken_links": broken_links,
            "orphan_pages": orphan_pages,
            "empty_files": empty_files
        }

    def suggest_questions(self) -> List[str]:
        """Dynamically generate analytical query suggestions using SQLite metadata and optionally Gemini"""
        config = get_config()()
        db_path = config.DATABASE_PATH
        
        # 1. Fetch metadata from local DB
        speakers = []
        topics = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # If DB is empty, don't show any suggestions
            cursor.execute('SELECT COUNT(*) FROM dashboard_data')
            if cursor.fetchone()[0] == 0:
                conn.close()
                return []
            
            # Fetch distinct speakers
            cursor.execute('''
                SELECT alumni_speaker_name, COUNT(*) as cnt 
                FROM dashboard_data 
                WHERE alumni_speaker_name IS NOT NULL AND alumni_speaker_name != ''
                GROUP BY alumni_speaker_name 
                ORDER BY cnt DESC 
                LIMIT 5
            ''')
            speakers = [r[0] for r in cursor.fetchall()]
            
            # Fetch common topics
            cursor.execute('''
                SELECT future_topics 
                FROM dashboard_data 
                WHERE future_topics IS NOT NULL AND future_topics != '' 
                LIMIT 15
            ''')
            topics = [r[0] for r in cursor.fetchall() if len(r[0].strip()) > 3]
            
            conn.close()
        except Exception as e:
            logger.error(f"Failed to query metadata for suggestions: {str(e)}")
            
        # Default offline fallback questions based on actual database entities
        fallback_questions = [
            "What is the overall sentiment of guest lectures?",
            "Who are the top rated speakers and what makes them successful?"
        ]
        if speakers:
            fallback_questions.append(f"What was the most valuable aspect of [[speakers/{speakers[0].replace(' ', '_')}]]'s lecture?")
            if len(speakers) > 1:
                fallback_questions.append(f"Compare the student feedback for [[speakers/{speakers[0].replace(' ', '_')}]] and [[speakers/{speakers[1].replace(' ', '_')}]]")
            else:
                fallback_questions.append(f"What were the key improvement areas suggested for [[speakers/{speakers[0].replace(' ', '_')}]]?")
        
        if not self.gemini_key:
            return fallback_questions
            
        # 2. Try generating via Gemini using the metadata context
        try:
            prompt = f"""
You are the Alumni Feedback AI assistant. Generate exactly 4 distinct, analytical, and highly specific suggested questions that a university administrator might want to ask about our guest lecture feedback database.
Use the actual speakers and topics list below to construct these questions.
Format your output as a strict JSON list of strings (no markdown fences, just the JSON).

Metadata:
- Speakers: {json.dumps(speakers)}
- Sample Student Topic Requests: {json.dumps(topics[:10])}

Example Output:
[
  "What improvements were suggested for SpeakerName's session?",
  "Did students find the Resume Writing topic valuable?",
  "What is the historical performance trend of SpeakerName?"
]
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
            req_data = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }).encode('utf-8')
            
            request = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=10) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                text_out = res_body['candidates'][0]['content']['parts'][0]['text']
                questions = json.loads(text_out)
                if isinstance(questions, list) and len(questions) >= 3:
                    return [str(q) for q in questions]
        except Exception as e:
            logger.error(f"Generative question suggestion failed: {str(e)}")
            
        return fallback_questions

    def get_graph_data(self) -> Dict[str, Any]:
        """Parse all markdown files to build nodes and links for the D3 force graph"""
        pages = self.list_wiki_pages()
        nodes = []
        links = []
        
        # Link extraction regex (e.g., [[speakers/John_Doe]])
        link_pattern = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
        
        for p in pages:
            # Add node
            nodes.append({"id": p})
            
            # Read content to find edges
            content = self.read_wiki_file(p)
            if not content:
                continue
                
            matches = link_pattern.findall(content)
            for linked in matches:
                linked = linked.strip()
                resolved = None
                
                # Resolve link to an actual page path
                if linked in pages:
                    resolved = linked
                elif f"{linked}.md" in pages:
                    resolved = f"{linked}.md"
                else:
                    for folder in ['events', 'speakers', 'concepts', 'suggestions']:
                        test_p = f"{folder}/{linked}".replace('//', '/')
                        if test_p in pages:
                            resolved = test_p
                            break
                        elif f"{test_p}.md" in pages:
                            resolved = f"{test_p}.md"
                            break
                
                if resolved and resolved != p:
                    links.append({"source": p, "target": resolved})
                    
        return {"nodes": nodes, "links": links}
