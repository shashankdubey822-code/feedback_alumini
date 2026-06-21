import re
import json
from backend.utils.insforge_db import execute_all
from backend.services.rag_service import RAGService

def execute_readonly_sql(query: str) -> str:
    """
    Executes raw SQL using InsForge API, strictly allowing only SELECT queries.
    Blocks mutation statements.
    """
    forbidden_keywords = r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|REPLACE|GRANT|REVOKE|COMMIT|ROLLBACK|EXEC)\b'
    
    if re.search(forbidden_keywords, query, re.IGNORECASE):
        return "Error: Only SELECT queries are permitted."
    
    if not re.match(r'^\s*SELECT\b', query, re.IGNORECASE):
        return "Error: Query must begin with SELECT."
        
    try:
        rows = execute_all(query)
        return json.dumps(rows, default=str)
    except Exception as e:
        return f"Database Error: {str(e)}"

def semantic_vector_search(
    query: str,
    filter_year: int = None,
    filter_semester: str = None,
    filter_dept: str = None,
) -> str:
    """
    Performs semantic vector search on feedback using RAGService.
    Supports optional year/semester/department filters matching the active dashboard filters.
    filter_semester must be 'Odd' (Jul-Dec) or 'Even' (Jan-Jun) or None.
    """
    try:
        rag = RAGService()
        rows = rag.search_similar_feedback(
            query,
            limit=50,
            filter_year=filter_year,
            filter_semester=filter_semester,
            filter_dept=filter_dept,
        )

        if not rows:
            return "No similar feedback found in the database matching the active filters."

        result_lines = [f"Retrieved {len(rows)} matching feedback record(s):"]
        for r in rows:
            line = (
                f"ID: {r.get('id', 'N/A')} | "
                f"Student: {r.get('name_of_student', 'N/A')} | "
                f"Speaker: {r.get('alumni_speaker_name', 'N/A')} | "
                f"Valuable: {r.get('aspect_most_valuable', 'N/A')} | "
                f"Improvements: {r.get('improvements_suggestions', 'N/A')} | "
                f"Future Topics: {r.get('future_topics', 'N/A')} | "
                f"Rating: {r.get('session_rating', 'N/A')}/5 | "
                f"Similarity: {float(r.get('similarity') or 0.0):.3f}"
            )
            result_lines.append(line)

        return "\n".join(result_lines)
    except Exception as e:
        return f"Vector Search Error: {str(e)}"

def get_schema_info() -> str:
    """
    Returns schema info for feedback_responses, students, and events tables,
    including vector search capabilities.
    """
    schema = (
        "SCHEMA INFORMATION:\n\n"
        "Table: students\n"
        "Columns: id (uuid), name (text), email (text), roll_no (text), department (text)\n\n"
        "Table: events\n"
        "Columns: id (uuid), speaker_name (text), venue_date (date), department (text), "
        "status (text), lecture_title (text)\n\n"
        "Table: feedback_responses\n"
        "Columns: id (uuid), student_id (uuid), event_id (uuid), session_rating (int), "
        "session_help_understanding (text), aspect_most_valuable (text), "
        "improvements_suggestions (text), future_topics (text), submitted_at (timestamp), "
        "embedding (vector(768) — populated automatically)\n"
        "Join conditions: feedback_responses.student_id = students.id, "
        "feedback_responses.event_id = events.id\n\n"
        "SEMESTER LOGIC:\n"
        "  Odd Session  = July, August, September, October, November, December (months 7-12)\n"
        "  Even Session = January, February, March, April, May, June (months 1-6)\n"
        "  Use: EXTRACT(MONTH FROM e.venue_date) IN (7,8,9,10,11,12) for Odd\n\n"
        "VECTOR SEARCH: Use semantic_vector_search tool for qualitative questions. "
        "The match_feedback_filtered() SQL function supports year/semester/dept filters.\n"
        "AGGREGATION: Use execute_readonly_sql for counts, averages, and statistics."
    )
    return schema
