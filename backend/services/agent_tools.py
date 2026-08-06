"""
agent_tools.py — Database, Schema, and RAG Agent Tools for Dashboard Mode.

Exports:
  - get_schema_info() -> str
  - execute_readonly_sql(sql_query: str) -> str
  - semantic_vector_search(query: str, top_k: int = 5, filter_year=None, filter_semester=None, filter_dept=None) -> str
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any

from backend.utils.insforge_db import execute_all
from backend.services.rag_service import RAGService

logger = logging.getLogger(__name__)

# Output capping constants to prevent context window blowup and LLM timeouts
MAX_TOOL_OUTPUT_CHARS = 3000
MAX_RESULT_ROWS = 50

_STATIC_SCHEMA = """Database Tables and Columns:
1. students:
   - id (BIGSERIAL PRIMARY KEY)
   - name (TEXT NOT NULL)
   - roll_no (TEXT UNIQUE)
   - department (TEXT)
   - email (TEXT)
   - created_at (TIMESTAMPTZ)

2. events:
   - id (BIGSERIAL PRIMARY KEY)
   - name (TEXT)
   - speaker_name (TEXT NOT NULL)
   - venue_date (TEXT NOT NULL)
   - form_id (TEXT UNIQUE)
   - status (TEXT: 'pending', 'creating_form', 'active', 'closed')
   - template_id (TEXT)
   - send_certificates (BOOLEAN)
   - created_at (TIMESTAMPTZ)

3. feedback_responses:
   - id (BIGSERIAL PRIMARY KEY)
   - event_id (BIGINT FK -> events.id)
   - student_id (BIGINT FK -> students.id)
   - submitted_at (TIMESTAMPTZ)
   - session_rating (SMALLINT 1-5)
   - aspect_most_valuable (TEXT)
   - improvements_suggestions (TEXT)
   - session_help_understanding (TEXT)
   - future_topics (TEXT)
   - created_at (TIMESTAMPTZ)

4. feedback_analysis:
   - id (BIGSERIAL PRIMARY KEY)
   - response_id (BIGINT UNIQUE FK -> feedback_responses.id)
   - sentiment_score (NUMERIC(6,4))
   - sentiment_label (TEXT: 'POSITIVE', 'NEUTRAL', 'NEGATIVE')
   - keywords_json (JSONB)
   - processed_at (TIMESTAMPTZ)

5. certificate_jobs:
   - id (BIGSERIAL PRIMARY KEY)
   - event_id (BIGINT FK -> events.id)
   - student_id (BIGINT FK -> students.id)
   - status (TEXT: 'pending', 'processing', 'completed', 'failed')
   - created_at (TIMESTAMPTZ)
   - updated_at (TIMESTAMPTZ)

6. wiki_pages:
   - id (BIGSERIAL PRIMARY KEY)
   - title (TEXT)
   - path (TEXT UNIQUE)
   - content (TEXT)
   - category (TEXT)
   - updated_at (TIMESTAMPTZ)"""


def get_schema_info() -> str:
    """
    Queries dynamic schema from InsForge DB / information_schema or provides
    a comprehensive fallback schema string for core tables.
    """
    try:
        query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('students', 'events', 'feedback_responses', 'feedback_analysis', 'certificate_jobs', 'wiki_pages')
            ORDER BY table_name, ordinal_position;
        """
        rows = execute_all(query)
        if not rows:
            return _STATIC_SCHEMA.strip()

        tables: Dict[str, List[str]] = {}
        for r in rows:
            t_name = r.get('table_name')
            c_name = r.get('column_name')
            d_type = r.get('data_type')
            if t_name not in tables:
                tables[t_name] = []
            tables[t_name].append(f"{c_name} ({d_type})")

        output_lines = ["Database Tables and Columns:"]
        for t_name, cols in sorted(tables.items()):
            output_lines.append(f"\nTable: {t_name}")
            for col in cols:
                output_lines.append(f"  - {col}")

        return "\n".join(output_lines)
    except Exception as e:
        logger.warning(f"Failed to query information_schema, using static schema fallback: {e}")
        return _STATIC_SCHEMA.strip()


def execute_readonly_sql(sql_query: str) -> str:
    """
    Strips markdown code fences, validates that SQL is strictly read-only SELECT/WITH,
    executes against InsForge DB, and formats the output (capped at 3000 chars / 50 rows).
    """
    if not sql_query or not isinstance(sql_query, str):
        return "Error: Empty or invalid SQL query provided."

    # 1. Strip markdown fences and whitespace
    cleaned = sql_query.strip()
    cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Strip trailing semicolons
    cleaned = cleaned.rstrip(";").strip()

    if not cleaned:
        return "Error: SQL query is empty after stripping formatting."

    # 2. Prevent multi-statement query execution
    if ";" in cleaned:
        return "Error: Only single SQL statements are allowed (multiple statements separated by ';' are rejected)."

    # 3. Strip SQL comments (line comments -- and block comments /* */) for validation checks
    stripped_for_check = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)
    stripped_for_check = re.sub(r"/\*.*?\*/", "", stripped_for_check, flags=re.DOTALL).strip()

    # 4. Enforce query starting with SELECT or WITH
    if not re.match(r"^(?:WITH\b|SELECT\b)", stripped_for_check, re.IGNORECASE):
        return "Error: Only read-only SELECT or WITH ... SELECT queries are allowed."

    # 5. Reject forbidden DDL / mutation statements
    forbidden_pattern = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE|VACUUM)\b"
    if re.search(forbidden_pattern, stripped_for_check, re.IGNORECASE):
        return "Error: Forbidden DDL/mutation statement detected. Only read-only queries are allowed."

    # 6. Execute against database
    try:
        rows = execute_all(cleaned)
        if not rows:
            return "Query executed successfully. 0 rows returned."

        total_rows = len(rows)
        truncated_rows = rows[:MAX_RESULT_ROWS]
        result_json = json.dumps(truncated_rows, indent=2, default=str)

        if len(result_json) > MAX_TOOL_OUTPUT_CHARS:
            result_json = result_json[:MAX_TOOL_OUTPUT_CHARS] + "\n... [Truncated: output exceeded max length]"
        elif total_rows > MAX_RESULT_ROWS:
            result_json += f"\n... [Truncated: showing {MAX_RESULT_ROWS} of {total_rows} rows]"

        return result_json
    except Exception as e:
        logger.error(f"Error executing readonly SQL query: {e}")
        return f"Database error: {str(e)}"


def semantic_vector_search(
    query: str,
    top_k: int = 5,
    filter_year: Optional[int] = None,
    filter_semester: Optional[str] = None,
    filter_dept: Optional[str] = None,
    **kwargs
) -> str:
    """
    Performs semantic vector search over feedback data and returns formatted snippets
    with similarity scores. Accepts optional filter parameters.
    """
    if not query or not isinstance(query, str):
        return "Error: Empty query provided for vector search."

    cleaned_query = query.strip().strip('"').strip("'")
    if not cleaned_query:
        return "Error: Query is empty after cleaning."

    try:
        rag = RAGService()
        results = rag.search_similar_feedback(cleaned_query, limit=top_k)

        if not results:
            return f"No matching semantic feedback found for query: '{cleaned_query}'."

        # Apply secondary python filters if provided and fields exist in results
        filtered_results = []
        for r in results:
            if filter_dept:
                dept = str(r.get('department') or r.get('dept') or '').lower()
                if dept and str(filter_dept).lower() not in dept:
                    continue
            if filter_year:
                year = r.get('year') or r.get('submitted_year')
                if year and str(year) != str(filter_year):
                    continue
            if filter_semester:
                sem = str(r.get('semester') or '').lower()
                if sem and str(filter_semester).lower() not in sem:
                    continue
            filtered_results.append(r)

        # If secondary filtering removed everything, fall back to unfiltered results to avoid empty responses
        display_results = filtered_results if filtered_results else results

        formatted_snippets = []
        for i, item in enumerate(display_results, 1):
            sim = item.get('similarity', 0.5)
            speaker = item.get('alumni_speaker_name') or item.get('speaker_name', 'N/A')
            student = item.get('name_of_student') or item.get('student_name', 'N/A')
            aspect = item.get('aspect_most_valuable', 'N/A')
            improvement = item.get('improvements_suggestions', 'N/A')
            future = item.get('future_topics', 'N/A')
            rating = item.get('session_rating', 'N/A')

            snippet = (
                f"Result {i} (Similarity: {sim:.2f}):\n"
                f"  - Speaker: {speaker}\n"
                f"  - Student: {student}\n"
                f"  - Session Rating: {rating}/5\n"
                f"  - Aspect Most Valuable: {aspect}\n"
                f"  - Improvement Suggestions: {improvement}\n"
                f"  - Future Topics: {future}"
            )
            formatted_snippets.append(snippet)

        output = f"Semantic Search Results for '{cleaned_query}':\n\n" + "\n\n".join(formatted_snippets)
        if len(output) > MAX_TOOL_OUTPUT_CHARS:
            output = output[:MAX_TOOL_OUTPUT_CHARS] + "\n... [Truncated output]"

        return output
    except Exception as e:
        logger.error(f"Error executing semantic vector search: {e}")
        return f"Vector search error: {str(e)}"
