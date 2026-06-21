import os
import re
import json
import time
import threading
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.config import get_config
from backend.utils.logger import get_section_logger
from backend.utils.insforge_db import execute_all
from backend.utils.insforge_helper import (
    insforge_upload_file,
    insforge_download_file,
    insforge_list_files,
    insforge_delete_file,
    is_insforge_active
)
logger = get_section_logger('wiki')

# Class-level compilation logger and queue state
_ingest_logs: List[str] = []
_ingest_progress: Dict[str, Any] = {"status": "IDLE", "current": 0, "total": 0, "active_session": ""}
_abort_requested: bool = False
_queue_lock = threading.Lock()


class WikiService:
    """Manages the creation, synchronization, querying, and linting of the Markdown Wiki"""

    def __init__(self):
        config = get_config()()
        self.wiki_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'wiki')
        self.pages_dir = os.path.join(self.wiki_dir, 'pages')
        self.bucket = config.INSFORGE_BUCKET
        self.gemini_key = config.GEMINI_API_KEY
        self.groq_key = config.GROQ_API_KEY
        
        # Additional Fallback Keys
        self.hf_key = config.HF_API_KEY
        self.cohere_key = config.COHERE_API_KEY
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.mistral_key = config.MISTRAL_API_KEY
        
        # Local dir creation safety
        os.makedirs(self.wiki_dir, exist_ok=True)
        os.makedirs(self.pages_dir, exist_ok=True)
        for sub in ['events', 'speakers', 'concepts', 'suggestions']:
            os.makedirs(os.path.join(self.pages_dir, sub), exist_ok=True)

    # ─── CORE FILE ACCESSORS ──────────────────────────────────────────────────

    def write_wiki_file(self, rel_path: str, content: str) -> bool:
        """Write content to local disk AND upload to InsForge Storage if configured"""
        local_path = os.path.join(self.pages_dir, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # 1. Write locally
        try:
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Local write failed for '{rel_path}': {str(e)}")

        # 2. Upload to InsForge Storage
        if is_insforge_active():
            content_bytes = content.encode('utf-8')
            success = insforge_upload_file(self.bucket, f"pages/{rel_path}", content_bytes, "text/markdown")
            if success:
                logger.info(f"Synced '{rel_path}' to InsForge bucket '{self.bucket}'")
            return success

        return True

    def read_wiki_file(self, rel_path: str) -> Optional[str]:
        """Read content from InsForge Storage, falling back to local file if offline"""
        # 1. Try InsForge Storage first
        if is_insforge_active():
            file_bytes = insforge_download_file(self.bucket, f"pages/{rel_path}")
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
        
        if is_insforge_active():
            # List files from InsForge Storage
            # Walk through subdirectories
            for sub in ['', 'events', 'speakers', 'concepts', 'suggestions']:
                files = insforge_list_files(self.bucket, f"pages/{sub}".strip('/'))
                for f in files:
                    name = f.get('name')
                    if name and name.endswith('.md'):
                        path = f"{sub}/{name}".strip('/')
                        if path != 'schema.md':
                            all_pages.append(path)
            if all_pages:
                return sorted(list(set(all_pages)))

        # Fallback to local file scanning
        for root, _, files in os.walk(self.pages_dir):
            for file in files:
                if file.endswith('.md'):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, self.pages_dir).replace('\\', '/')
                    if rel_p != 'schema.md':
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

    def abort_batch_ingest(self) -> str:
        """Request manual abort of active ingestion queue"""
        global _abort_requested, _ingest_progress
        with _queue_lock:
            if _ingest_progress["status"] == "PROCESSING":
                _abort_requested = True
                _ingest_progress["status"] = "ABORTING"
                self.log_compilation("🛑 Abort requested. Ingestion queue is stopping...")
                return "Abort requested."
            return "No active queue to abort."

    def _probe_provider_health(self, provider: str) -> bool:
        """Perform a fast (5-second timeout) ping check on the specified AI provider to verify key and health status"""
        if provider == "gemini":
            if not self.gemini_key:
                return False
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
                req_data = json.dumps({
                    "contents": [{"parts": [{"text": "ping"}]}],
                    "generationConfig": {"maxOutputTokens": 2}
                }).encode('utf-8')
                req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except Exception as e:
                logger.warning(f"Health check failed for Gemini: {str(e)}")
                return False

        elif provider == "groq":
            if not self.groq_key:
                return False
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                req_data = json.dumps({
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 2
                }).encode('utf-8')
                req = urllib.request.Request(
                    url, data=req_data,
                    headers={
                        'Authorization': f'Bearer {self.groq_key}',
                        'Content-Type': 'application/json',
                        'User-Agent': 'DataLens/1.0'
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except Exception as e:
                logger.warning(f"Health check failed for Groq: {str(e)}")
                return False

        elif provider == "hf":
            if not self.hf_key:
                return False
            try:
                url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct/v1/chat/completions"
                req_data = json.dumps({
                    "model": "Qwen/Qwen2.5-72B-Instruct",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 2
                }).encode('utf-8')
                req = urllib.request.Request(
                    url, data=req_data,
                    headers={
                        'Authorization': f'Bearer {self.hf_key}',
                        'Content-Type': 'application/json',
                        'User-Agent': 'DataLens/1.0'
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except Exception as e:
                logger.warning(f"Health check failed for HF: {str(e)}")
                return False

        elif provider == "cohere":
            if not self.cohere_key:
                return False
            try:
                url = "https://api.cohere.com/v1/chat"
                req_data = json.dumps({
                    "message": "ping",
                    "model": "command-r",
                    "max_tokens": 2
                }).encode('utf-8')
                req = urllib.request.Request(
                    url, data=req_data,
                    headers={
                        'Authorization': f'Bearer {self.cohere_key}',
                        'Content-Type': 'application/json'
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except Exception as e:
                logger.warning(f"Health check failed for Cohere: {str(e)}")
                return False

        elif provider == "openrouter":
            if not self.openrouter_key:
                return False
            try:
                url = "https://openrouter.ai/api/v1/chat/completions"
                req_data = json.dumps({
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 2
                }).encode('utf-8')
                req = urllib.request.Request(
                    url, data=req_data,
                    headers={
                        'Authorization': f'Bearer {self.openrouter_key}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://huggingface.co/spaces/vrfefavr/alumini_feedback',
                        'X-Title': 'Alumni Feedback System'
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except Exception as e:
                logger.warning(f"Health check failed for OpenRouter: {str(e)}")
                return False

        elif provider == "mistral":
            if not self.mistral_key:
                return False
            try:
                url = "https://api.mistral.ai/v1/chat/completions"
                req_data = json.dumps({
                    "model": "open-mistral-nemo",
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 2
                }).encode('utf-8')
                req = urllib.request.Request(
                    url, data=req_data,
                    headers={
                        'Authorization': f'Bearer {self.mistral_key}',
                        'Content-Type': 'application/json',
                        'User-Agent': 'DataLens/1.0'
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status == 200
            except Exception as e:
                logger.warning(f"Health check failed for Mistral: {str(e)}")
                return False

        return False

    # ─── COMPILER ENGINE (INGEST OPERATION) ───────────────────────────────────

    def compile_session(self, speaker: str, date_str: str, feedback_rows: List[Dict[str, Any]], healthy_providers: dict = None) -> str:
        """
        Compile feedback rows into events, speaker, and concept pages.
        Runs batch prompts using Gemini, falling back to a rule-based offline generator.
        """
        global _abort_requested
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping compilation.")
            return ""

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

        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping health checks.")
            return ""

        # Only run health checks if not provided by queue
        if healthy_providers is None:
            providers = ["gemini", "groq", "hf", "cohere", "openrouter", "mistral"]
            healthy_providers = {}
            
            self.log_compilation("Starting parallel health checks for AI providers...")
            with ThreadPoolExecutor(max_workers=len(providers)) as executor:
                futures = {executor.submit(self._probe_provider_health, p): p for p in providers}
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        is_healthy = future.result()
                        healthy_providers[p] = is_healthy
                        if is_healthy:
                            self.log_compilation(f"🩺 Provider health check: {p} is ONLINE")
                        else:
                            self.log_compilation(f"🩺 Provider health check: {p} is OFFLINE / UNHEALTHY")
                    except Exception as e:
                        healthy_providers[p] = False
                        self.log_compilation(f"🩺 Provider health check: {p} failed with error: {str(e)}")

        # ─── TRIGGER COMPILER EXECUTION: MULTI-LAYER FALLBACK ────────────────────
        # Layer 1: Gemini Flash — 15 RPM, 1 million tokens/min free tier
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping Gemini call.")
            return ""
        if healthy_providers.get("gemini"):
            success, err_msg = self._run_generative_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via Gemini AI.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ Gemini failed: {err_msg}. Trying Groq...")
        else:
            self.log_compilation("Skipping Gemini: Provider is offline or unconfigured.")

        # Layer 2: Groq (Llama 3.3 70B) — backup if Gemini is unavailable
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping Groq call.")
            return ""
        if healthy_providers.get("groq"):
            success, err_msg = self._run_groq_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via Groq Llama 3.3 70B.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ Groq failed: {err_msg}. Trying HuggingFace Serverless...")
        else:
            self.log_compilation("Skipping Groq: Provider is offline or unconfigured.")

        # Layer 3: Hugging Face Serverless Inference API — backup if Groq is unavailable
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping HuggingFace call.")
            return ""
        if healthy_providers.get("hf"):
            success, err_msg = self._run_hf_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via HuggingFace Serverless Inference.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ HuggingFace failed: {err_msg}. Trying Cohere...")
        else:
            self.log_compilation("Skipping HuggingFace: Provider is offline or unconfigured.")

        # Layer 4: Cohere API — backup if HuggingFace is unavailable
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping Cohere call.")
            return ""
        if healthy_providers.get("cohere"):
            success, err_msg = self._run_cohere_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via Cohere.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ Cohere failed: {err_msg}. Trying OpenRouter...")
        else:
            self.log_compilation("Skipping Cohere: Provider is offline or unconfigured.")

        # Layer 5: OpenRouter — backup if Cohere is unavailable
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping OpenRouter call.")
            return ""
        if healthy_providers.get("openrouter"):
            success, err_msg = self._run_openrouter_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via OpenRouter.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ OpenRouter failed: {err_msg}. Trying Mistral...")
        else:
            self.log_compilation("Skipping OpenRouter: Provider is offline or unconfigured.")

        # Layer 6: Mistral AI — backup if OpenRouter is unavailable
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping Mistral call.")
            return ""
        if healthy_providers.get("mistral"):
            success, err_msg = self._run_mistral_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
            if success:
                self.log_compilation(f"✅ Compiled '{speaker}' ({date_str}) via Mistral AI.")
                return safe_event
            else:
                self.log_compilation(f"⚠️ Mistral failed: {err_msg}. Using offline heuristics...")
        else:
            self.log_compilation("Skipping Mistral: Provider is offline or unconfigured.")
        
        # Execute Offline Heuristics compilation
        if _abort_requested:
            self.log_compilation("🛑 Abort requested. Skipping offline heuristics.")
            return ""
        self._run_offline_ingest(safe_event, safe_speaker, speaker, date_str, total_responses, avg_rating, understanding_levels, valuable_aspects, critiques, requests)
        self.log_compilation(f"Successfully compiled '{speaker}' ({date_str}) using Local Offline Heuristic Compiler.")
        return safe_event

    def _run_groq_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                         total: int, avg_rating: float, shu: Dict[str, int],
                         val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call Groq API (Llama 3.3 70B) - Primary AI: 14,400 free calls/day"""
        prompt = self._build_wiki_prompt(safe_event, safe_speaker, speaker, date_str, total, avg_rating, shu, val, crit, req)
        import time
        for attempt in range(2):
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
    
                with urllib.request.urlopen(request, timeout=30) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    data = self._safe_parse_json(res_body['choices'][0]['message']['content'])
                    return self._write_wiki_pages(safe_event, safe_speaker, speaker, date_str, avg_rating, data)
    
            except urllib.error.HTTPError as e:
                try:
                    err_body = e.read().decode('utf-8')
                    err_json = json.loads(err_body)
                    exact_msg = err_json.get('error', {}).get('message', err_body)
                except:
                    exact_msg = str(e)
                
                if e.code == 429 and attempt == 0:
                    self.log_compilation("⚠️ Rate limit (429) hit. Sleeping 5 seconds before retrying...")
                    time.sleep(5)
                    continue
                    
                error_msg = f"HTTP {e.code}: {exact_msg}"
                from backend.utils.logger import log_gemini_error
                log_gemini_error("Groq-Compile", speaker, error_msg)
                return False, error_msg
            except Exception as e:
                from backend.utils.logger import log_gemini_error
                log_gemini_error("Groq-Compile", speaker, str(e))
                return False, str(e)
        return False, "Failed after retries"

    def _safe_parse_json(self, text: str) -> dict:
        """Robust JSON parser that handles code blocks, balanced brackets, and regex fallbacks"""
        cleaned = text.strip()
        
        # Strip markdown code blocks
        if cleaned.startswith("```"):
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                cleaned = cleaned[first_nl:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        # Try direct parsing
        try:
            return json.loads(cleaned)
        except Exception:
            pass
            
        # Try balancing braces and brackets
        try:
            balanced = cleaned
            # Close quote if odd count
            if balanced.count('"') % 2 != 0:
                balanced += '"'
            
            # Simple bracket balancing
            stack = []
            for char in balanced:
                if char in ('{', '['):
                    stack.append(char)
                elif char in ('}', ']'):
                    if stack:
                        top = stack[-1]
                        if (char == '}' and top == '{') or (char == ']' and top == '['):
                            stack.pop()
            while stack:
                top = stack.pop()
                if top == '{':
                    balanced += '}'
                elif top == '[':
                    balanced += ']'
            return json.loads(balanced)
        except Exception:
            pass
            
        # Fall back to regex-based property extraction
        try:
            return self._regex_fallback_extract(cleaned)
        except Exception as e:
            logger.error(f"All JSON parsing and fallback extraction failed: {str(e)}")
            # Absolute fallback
            return {
                "event_page": f"# Compiled Event\nJSON parsing failed completely.\nRaw response:\n{text}",
                "speaker_page": f"# Speaker Profile\nJSON parsing failed completely.\nRaw response:\n{text}",
                "speaker_update_summary": "Compilation failed to parse."
            }

    def _regex_fallback_extract(self, text: str) -> dict:
        """Extract JSON fields via regular expressions when JSON parsing fails"""
        data = {}
        keys = [
            "event_page", "speaker_page", 
            "new_concept_name", "new_concept_page", 
            "new_suggestion_name", "new_suggestion_page", 
            "speaker_update_summary"
        ]
        for k in keys:
            pattern = rf'"{k}"\s*:\s*"(.*?)"(?=\s*,\s*"(?:{"|".join(keys)})"\s*:|\s*\}})'
            match = re.search(pattern, text, re.DOTALL)
            if match:
                val = match.group(1)
                # Simple escape replacement
                val = val.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                data[k] = val
                
        # Fill in critical defaults if missing
        if "event_page" not in data:
            data["event_page"] = "# Compiled Session\nExtracting page content failed."
        if "speaker_page" not in data:
            data["speaker_page"] = "# Speaker Dossier\nExtracting page content failed."
        if "speaker_update_summary" not in data:
            data["speaker_update_summary"] = "Session compiled with parse warnings."
            
        return data

    def _run_hf_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                       total: int, avg_rating: float, shu: Dict[str, int],
                       val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call Hugging Face Serverless Inference API (Qwen 2.5 72B Instruct)"""
        prompt = self._build_wiki_prompt(safe_event, safe_speaker, speaker, date_str, total, avg_rating, shu, val, crit, req)
        try:
            # Using Qwen 2.5 72B Instruct which is exceptional at code, structured JSON output, and RAG compilation
            url = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct/v1/chat/completions"
            req_data = json.dumps({
                "model": "Qwen/Qwen2.5-72B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }).encode('utf-8')

            request = urllib.request.Request(
                url, data=req_data,
                headers={
                    'Authorization': f'Bearer {self.hf_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'DataLens/1.0'
                }
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                raw_content = res_body['choices'][0]['message']['content']
                data = self._safe_parse_json(raw_content)
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
            log_gemini_error("HF-Compile", speaker, error_msg)
            return False, error_msg
        except Exception as e:
            from backend.utils.logger import log_gemini_error
            log_gemini_error("HF-Compile", speaker, str(e))
            return False, str(e)

    def _run_cohere_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                           total: int, avg_rating: float, shu: Dict[str, int],
                           val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call Cohere API (Command-R-Plus)"""
        prompt = self._build_wiki_prompt(safe_event, safe_speaker, speaker, date_str, total, avg_rating, shu, val, crit, req)
        try:
            url = "https://api.cohere.com/v1/chat"
            req_data = json.dumps({
                "message": prompt,
                "model": "command-r",
                "response_format": {"type": "json_object"}
            }).encode('utf-8')

            request = urllib.request.Request(
                url, data=req_data,
                headers={
                    'Authorization': f'Bearer {self.cohere_key}',
                    'Content-Type': 'application/json'
                }
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                data = self._safe_parse_json(res_body['text'])
                return self._write_wiki_pages(safe_event, safe_speaker, speaker, date_str, avg_rating, data)

        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode('utf-8')
                err_json = json.loads(err_body)
                exact_msg = err_json.get('message', err_body)
            except:
                exact_msg = str(e)
            error_msg = f"HTTP {e.code}: {exact_msg}"
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Cohere-Compile", speaker, error_msg)
            return False, error_msg
        except Exception as e:
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Cohere-Compile", speaker, str(e))
            return False, str(e)

    def _run_openrouter_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                               total: int, avg_rating: float, shu: Dict[str, int],
                               val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call OpenRouter API (Mistral 7B Instruct Free)"""
        prompt = self._build_wiki_prompt(safe_event, safe_speaker, speaker, date_str, total, avg_rating, shu, val, crit, req)
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            req_data = json.dumps({
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }).encode('utf-8')

            request = urllib.request.Request(
                url, data=req_data,
                headers={
                    'Authorization': f'Bearer {self.openrouter_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://huggingface.co/spaces/vrfefavr/alumini_feedback',
                    'X-Title': 'Alumni Feedback System'
                }
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                raw_content = res_body['choices'][0]['message']['content']
                data = self._safe_parse_json(raw_content)
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
            log_gemini_error("OpenRouter-Compile", speaker, error_msg)
            return False, error_msg
        except Exception as e:
            from backend.utils.logger import log_gemini_error
            log_gemini_error("OpenRouter-Compile", speaker, str(e))
            return False, str(e)

    def _run_mistral_ingest(self, safe_event: str, safe_speaker: str, speaker: str, date_str: str,
                            total: int, avg_rating: float, shu: Dict[str, int],
                            val: List[str], crit: List[str], req: List[str]) -> Tuple[bool, str]:
        """Call Mistral API (Mistral Nemo / Mistral Small)"""
        prompt = self._build_wiki_prompt(safe_event, safe_speaker, speaker, date_str, total, avg_rating, shu, val, crit, req)
        try:
            url = "https://api.mistral.ai/v1/chat/completions"
            req_data = json.dumps({
                "model": "open-mistral-nemo",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7
            }).encode('utf-8')

            request = urllib.request.Request(
                url, data=req_data,
                headers={
                    'Authorization': f'Bearer {self.mistral_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'DataLens/1.0'
                }
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                res_body = json.loads(response.read().decode('utf-8'))
                raw_content = res_body['choices'][0]['message']['content']
                data = self._safe_parse_json(raw_content)
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
            log_gemini_error("Mistral-Compile", speaker, error_msg)
            return False, error_msg
        except Exception as e:
            from backend.utils.logger import log_gemini_error
            log_gemini_error("Mistral-Compile", speaker, str(e))
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
        import time
        for attempt in range(2):
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
                    data = self._safe_parse_json(text_out)
                    return self._write_wiki_pages(safe_event, safe_speaker, speaker, date_str, avg_rating, data)
            except urllib.error.HTTPError as e:
                try:
                    err_body = e.read().decode('utf-8')
                    err_json = json.loads(err_body)
                    exact_msg = err_json.get('error', {}).get('message', err_body)
                except:
                    exact_msg = str(e)
                
                if e.code == 429 and attempt == 0:
                    self.log_compilation("⚠️ Rate limit (429) hit. Sleeping 5 seconds before retrying...")
                    time.sleep(5)
                    continue
                
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
        return False, "Failed after retries"

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
{chr(10).join([f'- {v}' for v in val]) if val else '*No valuable aspects recorded.*'}

### Actionable Critiques & Suggestions
{chr(10).join([f'- {c}' for c in crit]) if crit else '*No critiques recorded.*'}

### Requested Future Focus Areas
{chr(10).join([f'- {r}' for r in req]) if req else '*No requests recorded.*'}
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
        global _ingest_progress, _ingest_logs, _abort_requested
        
        with _queue_lock:
            if _ingest_progress["status"] in ("PROCESSING", "ABORTING"):
                return "Queue already running."
            
            _abort_requested = False
            _ingest_logs = []
            _ingest_progress = {
                "status": "PROCESSING",
                "current": 0,
                "total": len(sessions),
                "active_session": ""
            }

        def run_queue():
            global _ingest_progress, _abort_requested
            logger.info(f"Starting Ingest queue for {len(sessions)} sessions...")
            
            providers = ["gemini", "groq", "hf", "cohere", "openrouter", "mistral"]
            healthy_providers = {}
            
            self.log_compilation("Starting parallel health checks for AI providers...")
            with ThreadPoolExecutor(max_workers=len(providers)) as executor:
                futures = {executor.submit(self._probe_provider_health, p): p for p in providers}
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        is_healthy = future.result()
                        healthy_providers[p] = is_healthy
                        if is_healthy:
                            self.log_compilation(f"🩺 Provider health check: {p} is ONLINE")
                        else:
                            self.log_compilation(f"🩺 Provider health check: {p} is OFFLINE / UNHEALTHY")
                    except Exception as e:
                        healthy_providers[p] = False
                        self.log_compilation(f"🩺 Provider health check: {p} failed with error: {str(e)}")
            
            aborted = False
            for idx, (speaker, date_str) in enumerate(sessions):
                with _queue_lock:
                    if _abort_requested:
                        aborted = True
                        break
                    _ingest_progress["current"] = idx + 1
                    _ingest_progress["active_session"] = f"{speaker} ({date_str})"
                
                try:
                    # Fetch student responses for this session
                    rows = execute_all(
                        '''
                        SELECT r.*
                        FROM feedback_responses r
                        JOIN events e ON r.event_id = e.id
                        WHERE e.speaker_name = %s AND e.venue_date = %s
                        ORDER BY r.submitted_at ASC
                        ''',
                        (speaker, date_str)
                    )

                    if rows:
                        self.compile_session(speaker, date_str, rows, healthy_providers=healthy_providers)
                    else:
                        self.log_compilation(f"Skipping: No feedback records found for '{speaker}' on '{date_str}'.")
                except Exception as e:
                    self.log_compilation(f"Error compiling session '{speaker}': {str(e)}")

                if _abort_requested:
                    aborted = True
                    break

                # Throttling to respect Gemini 15 RPM free tier limits (sleep 4 seconds per session, checking for aborts)
                for _ in range(40):
                    if _abort_requested:
                        aborted = True
                        break
                    time.sleep(0.1)
                
                if aborted:
                    break

            with _queue_lock:
                if aborted or _abort_requested:
                    _ingest_progress["status"] = "ABORTED"
                    self.log_compilation("🛑 Ingestion compilation queue aborted by user.")
                else:
                    _ingest_progress["status"] = "COMPLETE"
                    self.log_compilation("Ingestion queue completed successfully!")
                _ingest_progress["active_session"] = ""

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

    def query_wiki(
        self,
        question: str,
        history: List[Dict[str, str]] = None,
        session_id: str = None,
        filter_year: int = None,
        filter_semester: str = None,
        filter_dept: str = None,
    ) -> Dict[str, Any]:
        """
        Query the compiled Wiki.
        Now implemented as an Agentic ReAct Loop calling tools.
        """
        import re
        from langchain_core.prompts import ChatPromptTemplate
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        except ImportError:
            return {"answer": "LangChain message classes failed to import. Cannot run ReAct agent.", "citations": []}
        from backend.services.agent_tools import execute_readonly_sql, semantic_vector_search, get_schema_info
        
        logger.info(f"Agentic ReAct Wiki Query: '{question}' with history length {len(history) if history else 0}, session_id: {session_id}")
        
        # Build the models list from highest priority to lowest
        models_to_try = []
        
        if self.groq_key:
            try:
                from langchain_groq import ChatGroq
                models_to_try.append(("Groq (Llama-3.3)", ChatGroq(api_key=self.groq_key, model="llama-3.3-70b-versatile", temperature=0.1, max_retries=0, timeout=15)))
            except ImportError:
                pass
            
        if self.openrouter_key:
            try:
                from langchain_openai import ChatOpenAI
                models_to_try.append(("OpenRouter (Llama-3-70b)", ChatOpenAI(
                    api_key=self.openrouter_key, 
                    base_url="https://openrouter.ai/api/v1", 
                    model="meta-llama/llama-3.3-70b-instruct", 
                    temperature=0.1, 
                    max_retries=0, 
                    request_timeout=15
                )))
            except ImportError:
                pass

        if self.hf_key:
            class CustomHFEndpoint:
                def __init__(self, api_token, repo_id, temperature=0.1, max_new_tokens=512, timeout=15):
                    self.api_token = api_token
                    self.repo_id = repo_id
                    self.temperature = temperature
                    self.max_new_tokens = max_new_tokens
                    self.timeout = timeout
                    
                def invoke(self, messages):
                    prompt = ""
                    for msg in messages:
                        if msg.__class__.__name__ == 'SystemMessage':
                            prompt += f"System: {msg.content}\n"
                        elif msg.__class__.__name__ == 'HumanMessage':
                            prompt += f"User: {msg.content}\n"
                        elif msg.__class__.__name__ == 'AIMessage':
                            prompt += f"Assistant: {msg.content}\n"
                        else:
                            prompt += f"{msg.content}\n"
                    
                    import requests
                    headers = {
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "inputs": prompt,
                        "parameters": {
                            "temperature": self.temperature,
                            "max_new_tokens": self.max_new_tokens,
                            "return_full_text": False
                        }
                    }
                    url = f"https://api-inference.huggingface.co/models/{self.repo_id}"
                    resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                    resp.raise_for_status()
                    res_data = resp.json()
                    
                    if isinstance(res_data, list) and len(res_data) > 0:
                        content = res_data[0].get("generated_text", "")
                    elif isinstance(res_data, dict):
                        content = res_data.get("generated_text", "")
                    else:
                        content = str(res_data)
                        
                    if content.startswith(prompt):
                        content = content[len(prompt):].strip()
                        
                    class HFResponse:
                        def __init__(self, content):
                            self.content = content
                    return HFResponse(content)

            models_to_try.append(("HuggingFace (Mistral-7B)", CustomHFEndpoint(
                api_token=self.hf_key,
                repo_id="mistralai/Mistral-7B-Instruct-v0.2",
                temperature=0.1,
                max_new_tokens=512,
                timeout=15
            )))

        if self.gemini_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                models_to_try.append(("Gemini 2.5 Flash", ChatGoogleGenerativeAI(google_api_key=self.gemini_key, model="gemini-2.5-flash", temperature=0.1, max_retries=0, request_timeout=15)))
            except ImportError:
                pass
            
        if self.mistral_key:
            try:
                from langchain_mistralai import ChatMistralAI
                models_to_try.append(("Mistral Large", ChatMistralAI(api_key=self.mistral_key, model="mistral-large-latest", temperature=0.1, max_retries=0, timeout=15)))
            except ImportError:
                pass

        if self.cohere_key:
            try:
                from langchain_cohere import ChatCohere
                models_to_try.append(("Cohere Command-R", ChatCohere(cohere_api_key=self.cohere_key, model="command-r", temperature=0.1, max_retries=0, timeout=15)))
            except ImportError:
                pass

        if not models_to_try:
            return {"answer": "No AI available (API keys missing). Cannot execute Agentic ReAct Loop.", "citations": []}

        schema_info = get_schema_info()

        system_instruction = f"""You are a factual AI analyst for a college alumni feedback dashboard. You have ZERO knowledge outside the database.

CRITICAL RULES (NEVER BREAK THESE):
1. ONLY use information retrieved by tools. NEVER invent names, ratings, or comments.
2. If the database returns no data matching the question, respond: "No data found matching your query in the current filters."
3. NEVER say things like "typically", "usually", "in general" — only speak from actual retrieved rows.
4. When summarizing feedback, always mention how many records you retrieved (e.g., "Based on 23 retrieved responses...").
5. If uncertain, use a tool to check — do not guess.

You solve questions using a ReAct (Reasoning and Acting) loop with these tools:
- [TOOL: execute_readonly_sql] - Run a SELECT SQL query. Input: the SQL string.
- [TOOL: semantic_vector_search] - Semantic search on feedback text. Input: search phrase.
- [TOOL: get_schema_info] - Get DB schema. Input: empty string.

Current Database Schema:
{schema_info}

IMPORTANT: The embedding column is populated — semantic_vector_search will return REAL data. Always prefer semantic_vector_search for qualitative questions and execute_readonly_sql for counting/aggregation.

To use a tool:
Action: [TOOL_NAME]
Action Input: [QUERY]

Example:
Action: execute_readonly_sql
Action Input: SELECT COUNT(*) FROM feedback_responses WHERE session_rating >= 4;

When ready:
Final Answer: [ANSWER GROUNDED IN RETRIEVED DATA ONLY]

Format your final answer as bullet points. Start with a one-line summary, then supporting points. Max 80 words total.
"""

        # Prepare messages
        history_context = ""
        if history:
            history_context = "Conversation History:\n"
            for h in history:
                role = h.get('role', 'user')
                content = h.get('content', '')
                history_context += f"{role.capitalize()}: {content}\n"
        
        current_question = f"{history_context}\nUser Question: {question}"
        
        # We'll just try models sequentially until one succeeds the whole loop
        for model_name, llm in models_to_try:
            try:
                messages = [
                    SystemMessage(content=system_instruction),
                    HumanMessage(content=current_question)
                ]
                
                max_iterations = 5
                iterations = 0
                final_answer = None
                
                while iterations < max_iterations:
                    iterations += 1
                    logger.info(f"ReAct Loop Iteration {iterations} with model {model_name}")
                    
                    response = llm.invoke(messages)
                    
                    response_text = response.content if hasattr(response, 'content') else str(response)
                    logger.info(f"LLM Response:\n{response_text}")
                    
                    messages.append(AIMessage(content=response_text))
                    
                    if "Final Answer:" in response_text:
                        final_answer = response_text.split("Final Answer:", 1)[1].strip()
                        break
                        
                    action_match = re.search(r"Action:\s*(.+)", response_text)
                    action_input_match = re.search(r"Action Input:\s*(.*)", response_text)
                    
                    if action_match:
                        tool_name = action_match.group(1).strip()
                        tool_input = action_input_match.group(1).strip() if action_input_match else ""
                        
                        observation = ""
                        try:
                            if "execute_readonly_sql" in tool_name:
                                observation = execute_readonly_sql(tool_input)
                            elif "semantic_vector_search" in tool_name:
                                observation = semantic_vector_search(
                                    tool_input,
                                    filter_year=filter_year,
                                    filter_semester=filter_semester,
                                    filter_dept=filter_dept,
                                )
                            elif "get_schema_info" in tool_name:
                                observation = get_schema_info()
                            else:
                                observation = f"Unknown tool: {tool_name}"
                        except Exception as e:
                            observation = f"Tool execution error: {str(e)}"
                        
                        logger.info(f"Observation: {observation}")
                        messages.append(HumanMessage(content=f"Observation: {observation}"))
                    else:
                        messages.append(HumanMessage(content="You didn't specify an action in the correct format or provide a Final Answer. Please format as 'Action: [TOOL_NAME]' and 'Action Input: [QUERY]' or 'Final Answer: [ANSWER]'."))
                
                if final_answer:
                    return {"answer": final_answer, "citations": []}
                else:
                    return {"answer": "I apologize, but I wasn't able to reach a final answer within the allowed number of steps.", "citations": []}
                    
            except Exception as e:
                logger.warning(f"Model {model_name} failed during ReAct loop: {str(e)}")
                continue
                
        return {"answer": "Error generating response: All configured AI models failed or timed out during the ReAct loop.", "citations": []}

    def clear_memory(self, session_id: str) -> bool:
        """Delete chat history for the given session ID from InsForge bucket"""
        if is_insforge_active() and session_id:
            try:
                path = f"memory/{session_id}.json"
                insforge_delete_file(self.bucket, path)
                logger.info(f"Deleted memory for session '{session_id}' from InsForge bucket.")
                return True
            except Exception as e:
                logger.error(f"Failed to delete memory from InsForge bucket: {e}")
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
        """Dynamically generate analytical query suggestions from InsForge-backed feedback."""
        ChatGroq = None
        ChatGoogleGenerativeAI = None
        ChatOpenAI = None
        HumanMessage = None
        try:
            if self.groq_key:
                from langchain_groq import ChatGroq
            if self.gemini_key:
                from langchain_google_genai import ChatGoogleGenerativeAI
            if self.openrouter_key:
                from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage
        except ImportError:
            pass

        speakers = []
        topics = []
        try:
            speaker_rows = execute_all('''
                SELECT e.speaker_name AS alumni_speaker_name, COUNT(*) AS cnt
                FROM feedback_responses r
                JOIN events e ON r.event_id = e.id
                WHERE e.speaker_name IS NOT NULL AND e.speaker_name <> ''
                GROUP BY e.speaker_name
                ORDER BY cnt DESC, e.speaker_name ASC
            ''')
            speakers = [r['alumni_speaker_name'] for r in speaker_rows if r.get('alumni_speaker_name')]

            topic_rows = execute_all('''
                SELECT future_topics, COUNT(*) AS cnt
                FROM feedback_responses
                WHERE future_topics IS NOT NULL AND future_topics <> ''
                GROUP BY future_topics
                ORDER BY cnt DESC
            ''')
            topics = [r['future_topics'].strip() for r in topic_rows if r.get('future_topics') and len(r['future_topics'].strip()) > 3]
        except Exception as e:
            logger.error(f"Failed to query metadata for suggestions: {str(e)}")
            return []

        if not speakers and not topics:
            return [
                "What is the overall sentiment of guest lectures?",
                "Who are the top rated speakers and what makes them successful?",
                "What improvement patterns appear most often?",
                "Compare the student feedback across different topics.",
            ]

        # 2. Ask the LLM to generate 4 dynamic questions
        prompt_text = f"""You are an advanced analyst for a student feedback database.
The database contains feedback on these recent speakers: {', '.join(speakers) if speakers else 'None'}.
The database contains requests for these future topics: {', '.join(topics) if topics else 'None'}.

Based strictly on this data, formulate exactly 4 insightful, analytical questions that a user could ask you to discover deeper trends in the database.
Make the questions sound natural, like: "What was the overall sentiment for [Speaker Name]?" or "Which speaker covered [Topic] best?"
Do NOT include generic questions that don't use the data. 

Return ONLY the 4 questions, one per line. Do not use bullet points, numbering, or introductory text."""

        # Attempt to get an LLM to generate the questions
        llm = None
        if self.groq_key and ChatGroq is not None:
            llm = ChatGroq(api_key=self.groq_key, model="llama-3.3-70b-versatile", temperature=0.3, max_retries=0, timeout=5)
        elif self.gemini_key and ChatGoogleGenerativeAI is not None:
            llm = ChatGoogleGenerativeAI(google_api_key=self.gemini_key, model="gemini-2.5-flash", temperature=0.3, max_retries=0, request_timeout=5)
        elif self.openrouter_key and ChatOpenAI is not None:
            try:
                llm = ChatOpenAI(api_key=self.openrouter_key, base_url="https://openrouter.ai/api/v1", model="meta-llama/llama-3.3-70b-instruct", temperature=0.3, max_retries=0, request_timeout=5)
            except:
                pass
                
        if llm:
            try:
                res = llm.invoke([HumanMessage(content=prompt_text)])
                questions = [q.strip().strip('-*0123456789. ') for q in res.content.split('\n') if q.strip()]
                if len(questions) >= 4:
                    return questions[:4]
            except Exception as e:
                logger.warning(f"Failed to dynamically generate questions with LLM: {e}")

        fallback_questions = [
            "What is the overall sentiment of guest lectures?",
            "Who are the top rated speakers and what makes them successful?",
            f"What was the most valuable aspect of {speakers[0] if speakers else 'the last'} lecture?",
            "Compare the student feedback across different topics.",
        ]
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
