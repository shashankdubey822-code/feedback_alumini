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

def semantic_vector_search(query: str) -> str:
    """
    Performs semantic vector search on feedback using RAGService.
    """
    try:
        rag = RAGService()
        rows = rag.search_similar_feedback(query, limit=50)
        
        if not rows:
            return "No similar feedback found."
            
        result_lines = []
        for r in rows:
            line = (
                f"ID: {r.get('id', 'N/A')} | "
                f"Student: {r.get('name_of_student', 'N/A')} | "
                f"Event: {r.get('alumni_speaker_name', 'N/A')} | "
                f"Valuable: {r.get('aspect_most_valuable', 'N/A')} | "
                f"Improvements: {r.get('improvements_suggestions', 'N/A')} | "
                f"Future Topics: {r.get('future_topics', 'N/A')} | "
                f"Rating: {r.get('session_rating', 'N/A')} | "
                f"Similarity: {r.get('similarity', 'N/A')}"
            )
            result_lines.append(line)
            
        return "\n".join(result_lines)
    except Exception as e:
        return f"Vector Search Error: {str(e)}"

def get_schema_info() -> str:
    """
    Returns hardcoded string describing schema for feedback_responses, students, and events tables.
    """
    schema = (
        "SCHEMA INFORMATION:\n\n"
        "Table: students\n"
        "Columns: id, name, email\n\n"
        "Table: events\n"
        "Columns: id, speaker_name, topic, event_date\n\n"
        "Table: feedback_responses\n"
        "Columns: id, student_id, event_id, aspect_most_valuable, improvements_suggestions, future_topics, session_rating, submitted_at\n"
        "Join conditions: feedback_responses.student_id = students.id, feedback_responses.event_id = events.id"
    )
    return schema
