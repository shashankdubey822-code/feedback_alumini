"""
Wiki Routes - REST Blueprint for Wiki operations
"""

from flask import Blueprint, jsonify, request, current_app
from backend.services.wiki_service import WikiService
from backend.utils.logger import get_section_logger, log_endpoint_access
from backend.utils.insforge_db import execute_all
import os
import re

logger = get_section_logger('wiki_routes')

wiki_bp = Blueprint('wiki', __name__, url_prefix='/api/v1/wiki')


def _get_wiki_service() -> WikiService:
    """Instantiate or retrieve cached WikiService"""
    if not hasattr(current_app, '_wiki_service'):
        current_app._wiki_service = WikiService()
    return current_app._wiki_service


@wiki_bp.route('/status', methods=['GET'])
@log_endpoint_access
def get_wiki_status():
    """Get overall statistics of the Wiki"""
    try:
        service = _get_wiki_service()
        pages = service.list_wiki_pages()
        
        # Categorise pages
        speakers = [p for p in pages if p.startswith('speakers/')]
        events = [p for p in pages if p.startswith('events/')]
        concepts = [p for p in pages if p.startswith('concepts/')]
        suggestions = [p for p in pages if p.startswith('suggestions/')]
        
        is_initialized = len(pages) > 0
        
        return jsonify({
            'initialized': is_initialized,
            'gemini_configured': bool(service.gemini_key),
            'groq_configured': bool(service.groq_key),
            'ai_provider': 'groq' if service.groq_key else ('gemini' if service.gemini_key else 'offline'),
            'total_pages': len(pages),
            'counts': {
                'speakers': len(speakers),
                'events': len(events),
                'concepts': len(concepts),
                'suggestions': len(suggestions),
                'core': len(pages) - len(speakers) - len(events) - len(concepts) - len(suggestions)
            }
        }), 200
    except Exception as e:
        logger.error(f"Error checking wiki status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/groq-limits', methods=['GET'])
@log_endpoint_access
def get_groq_limits():
    """Fetch real-time Groq API rate limits using a cheap ping."""
    from backend.services.wiki_service import WikiService
    service = WikiService()
    if not service.groq_key:
        return jsonify({'error': 'No Groq API key configured'}), 404
        
    try:
        import urllib.request, json
        url = "https://api.groq.com/openai/v1/chat/completions"
        req_data = json.dumps({
            "model": "llama-3.3-70b-versatile", 
            "messages": [{"role": "user", "content": "ping"}], 
            "max_tokens": 1
        }).encode('utf-8')
        request = urllib.request.Request(url, data=req_data, headers={
            'Authorization': f'Bearer {service.groq_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'DataLens/1.0'
        })
        
        with urllib.request.urlopen(request, timeout=10) as response:
            headers = dict(response.headers)
            remaining = headers.get('x-ratelimit-remaining-requests-today') or headers.get('x-ratelimit-remaining-requests', 'Unknown')
            return jsonify({'remaining_requests': remaining})
            
    except Exception as e:
        # Check if the error contains HTTP headers (e.g. 429 Too Many Requests)
        if hasattr(e, 'headers'):
            headers = dict(e.headers)
            remaining = headers.get('x-ratelimit-remaining-requests-today') or headers.get('x-ratelimit-remaining-requests', '0')
            return jsonify({'remaining_requests': remaining})
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/initialize', methods=['POST'])
@log_endpoint_access
def initialize_wiki():
    """Initialize folders and templates"""
    try:
        service = _get_wiki_service()
        success = service.initialize_wiki(force=True)
        if success:
            return jsonify({'message': 'Wiki initialized successfully.'}), 200
        return jsonify({'error': 'Initialization failed.'}), 500
    except Exception as e:
        logger.error(f"Error initializing wiki: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/pages', methods=['GET'])
@log_endpoint_access
def get_wiki_pages():
    """Get list of pages formatted as a tree folder structure"""
    try:
        service = _get_wiki_service()
        pages = service.list_wiki_pages()
        return jsonify({'pages': pages}), 200
    except Exception as e:
        logger.error(f"Error listing wiki pages: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/pages/<path:filename>', methods=['GET'])
@log_endpoint_access
def get_wiki_page_content(filename):
    """Retrieve raw markdown and formatted HTML for a specific page"""
    try:
        service = _get_wiki_service()
        markdown_content = service.read_wiki_file(filename)
        
        if markdown_content is None:
            return jsonify({'error': f"Page '{filename}' not found."}), 404
            
        # ─── NATIVE MARKDOWN TO HTML CONVERTER ───────────────────────────────
        # Parses double bracket links [[speakers/John_Doe]] into clickable spans
        # This keeps frontend rendering 100% lightweight and fast
        html_out = markdown_content
        
        # 1. Escape HTML tags
        html_out = html_out.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # 2. Bold tags
        html_out = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_out)
        
        # 3. List bullets
        html_out = re.sub(r'^\s*-\s+(.*?)$', r'<li>\1</li>', html_out, flags=re.MULTILINE)
        
        # 4. Headers
        html_out = re.sub(r'^###\s+(.*?)$', r'<h3>\1</h3>', html_out, flags=re.MULTILINE)
        html_out = re.sub(r'^##\s+(.*?)$', r'<h2>\1</h2>', html_out, flags=re.MULTILINE)
        html_out = re.sub(r'^#\s+(.*?)$', r'<h1>\1</h1>', html_out, flags=re.MULTILINE)
        
        # 5. Double bracket WikiLinks [[path/to/page]] -> Clickable span
        # e.g. [[speakers/John_Doe]] -> <span class="wiki-link" data-page="speakers/John_Doe">John Doe</span>
        def replace_link(match):
            link = match.group(1).strip()
            # Label displays file name without path and underscores
            label = link.split('/')[-1].replace('_', ' ').replace('.md', '')
            return f'<span class="wiki-link" data-page="{link}">{label}</span>'
            
        html_out = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', replace_link, html_out)
        
        # 6. Add line break paragraph wraps
        html_out = html_out.replace('\n', '<br>')
        
        return jsonify({
            'filename': filename,
            'markdown': markdown_content,
            'html': html_out
        }), 200
    except Exception as e:
        logger.error(f"Error reading page '{filename}': {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/sessions', methods=['GET'])
@log_endpoint_access
def get_db_sessions():
    """Retrieve unique guest lecture sessions and check if compiled in wiki"""
    try:
        rows = execute_all('''
            SELECT e.speaker_name AS alumni_speaker_name, e.venue_date AS date_of_lecture, COUNT(r.id) AS cnt
            FROM feedback_responses r
            JOIN events e ON r.event_id = e.id
            WHERE e.speaker_name IS NOT NULL AND e.speaker_name <> ''
              AND e.venue_date IS NOT NULL
            GROUP BY e.speaker_name, e.venue_date
            ORDER BY e.venue_date DESC, e.speaker_name ASC
        ''')

        service = _get_wiki_service()
        pages = service.list_wiki_pages()
        
        # Map compiled status
        for r in rows:
            speaker = r['alumni_speaker_name']
            date_str = r['date_of_lecture']
            safe_speaker = speaker.replace(' ', '_').replace('.', '')
            expected_file = f"events/{date_str}_{safe_speaker}.md"
            r['compiled'] = expected_file in pages

        return jsonify({'sessions': rows}), 200
    except Exception as e:
        logger.error(f"Error loading sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/ingest', methods=['POST'])
@log_endpoint_access
def trigger_ingestion():
    """Enqueue selected sessions or all sessions for compilation"""
    try:
        body = request.get_json() or {}
        sessions = body.get('sessions', [])
        
        if not sessions:
            return jsonify({'error': 'No sessions selected.'}), 400
            
        # Parse sessions format: List[dict(speaker, date)]
        sessions_tuple = [(s['speaker'], s['date']) for s in sessions]
        
        service = _get_wiki_service()
        message = service.start_batch_ingest_queue(sessions_tuple)
        return jsonify({'message': message}), 200
    except Exception as e:
        logger.error(f"Error triggering batch ingest: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/ingest/status', methods=['GET'])
@log_endpoint_access
def get_ingest_status():
    """Fetch volatile compiler queue status and logs"""
    try:
        service = _get_wiki_service()
        status_payload = service.get_queue_status()
        return jsonify(status_payload), 200
    except Exception as e:
        logger.error(f"Error fetching queue status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/ingest/abort', methods=['POST'])
@log_endpoint_access
def abort_ingestion():
    """Abort the current background ingestion process"""
    try:
        service = _get_wiki_service()
        service.abort_batch_ingest()
        return jsonify({'message': 'Abort request sent to ingestion compiler.'}), 200
    except Exception as e:
        logger.error(f"Error aborting batch ingest: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/query', methods=['POST'])
@log_endpoint_access
def execute_wiki_query():
    """Synthesize RAG query answers from the compiled wiki"""
    try:
        body = request.get_json() or {}
        question = body.get('question', '').strip()
        history = body.get('history', [])
        session_id = body.get('session_id', 'default_session').strip()
        
        if not question:
            return jsonify({'error': 'Question cannot be empty.'}), 400
            
        service = _get_wiki_service()
        result = service.query_wiki(question, history, session_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error executing wiki query: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/clear-memory', methods=['POST'])
@log_endpoint_access
def execute_wiki_clear_memory():
    """Delete chat history for a session from the InsForge bucket"""
    try:
        body = request.get_json() or {}
        session_id = body.get('session_id', 'default_session').strip()
        service = _get_wiki_service()
        success = service.clear_memory(session_id)
        return jsonify({'success': success}), 200
    except Exception as e:
        logger.error(f"Error clearing memory: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/suggest-questions', methods=['GET'])
@log_endpoint_access
def get_suggest_questions():
    """Retrieve dynamic query suggestion questions from DB and Gemini"""
    try:
        service = _get_wiki_service()
        questions = service.suggest_questions()
        return jsonify({'questions': questions}), 200
    except Exception as e:
        logger.error(f"Error getting suggestions: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/lint', methods=['GET'])
@log_endpoint_access
def run_wiki_lint():
    """Run broken links and orphans checks"""
    try:
        service = _get_wiki_service()
        results = service.run_wiki_linter()
        return jsonify(results), 200
    except Exception as e:
        logger.error(f"Error running wiki linter: {str(e)}")
        return jsonify({'error': str(e)}), 500


@wiki_bp.route('/config', methods=['POST'])
@log_endpoint_access
def save_wiki_config():
    """Save active credentials temporarily in environment memory"""
    try:
        body = request.get_json() or {}
        gemini_key = body.get('gemini_key', '').strip()
        insforge_url = body.get('insforge_url', '').strip()
        insforge_key = body.get('insforge_key', '').strip()
        
        if gemini_key:
            current_app.config['GEMINI_API_KEY'] = gemini_key
            os.environ['GEMINI_API_KEY'] = gemini_key
            service = _get_wiki_service()
            service.gemini_key = gemini_key
            
        if insforge_url and insforge_key:
            current_app.config['INSFORGE_URL'] = insforge_url
            current_app.config['INSFORGE_SERVICE_KEY'] = insforge_key
            os.environ['INSFORGE_URL'] = insforge_url
            os.environ['INSFORGE_SERVICE_KEY'] = insforge_key
            # Reset cached insforge client to reinitialize
            from backend.utils import insforge_helper
            insforge_helper._insforge_client = None
            
        return jsonify({'message': 'Configuration updated successfully.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@wiki_bp.route('/graph', methods=['GET'])
@log_endpoint_access
def get_graph():
    """Get nodes and links for the Wiki D3 force graph"""
    try:
        service = _get_wiki_service()
        graph_data = service.get_graph_data()
        return jsonify(graph_data), 200
    except Exception as e:
        logger.error(f"Error generating graph data: {str(e)}")
        return jsonify({'error': str(e)}), 500
