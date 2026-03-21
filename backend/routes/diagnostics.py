"""
Diagnostics API - for isolating and reading module-specific error logs
"""

from flask import Blueprint, jsonify
from backend.utils.logger import get_section_logger
import os
import sqlite3

diagnostics_bp = Blueprint('diagnostics', __name__, url_prefix='/api/v1/diagnostics')
logger = get_section_logger('api')  # Use generic API logger for diagnostics routing

def get_logs_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')

@diagnostics_bp.route('/health', methods=['GET'])
def check_health():
    """Overall system diagnostic health check"""
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(dashboard_data)")
        cols = [row[1] for row in cursor.fetchall()]
        db_status = "OK" if cols else "ERROR"
        
        has_nlp = "dl_processed" in cols
        counts = {}
        if has_nlp:
            cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE dl_processed = 0")
            counts['dl_pending'] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE dl_processed = 1")
            counts['dl_completed'] = cursor.fetchone()[0]
            
        conn.close()
        
        log_dir = get_logs_dir()
        log_files = []
        if os.path.exists(log_dir):
            log_files = os.listdir(log_dir)
            
        return jsonify({
            'status': 'healthy' if db_status == "OK" else 'degraded',
            'components': {
                'database': db_status,
                'nlp_schema_ready': has_nlp
            },
            'queue_metrics': counts,
            'active_error_logs': log_files
        }), 200
    except Exception as e:
        logger.error(f"Diagnostics Healthcheck Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@diagnostics_bp.route('/logs/<section>', methods=['GET'])
def read_section_logs(section):
    """
    Read the last 100 lines of a specific section's error log.
    Sections: api, nlp, webhook, db, dl_worker
    """
    try:
        log_dir = get_logs_dir()
        filename = f"{section}_errors.log"
        file_path = os.path.join(log_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'section': section,
                'status': 'no_logs_found',
                'lines': []
            }), 200
            
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]
            
        return jsonify({
            'section': section,
            'status': 'found',
            'line_count': len(lines),
            'lines': [line.strip() for line in lines]
        }), 200
    except Exception as e:
        logger.error(f"Log Read Error for {section}: {str(e)}")
        return jsonify({'error': str(e)}), 500
