"""
Diagnostics API - for isolating and reading module-specific error logs
"""

from flask import Blueprint, jsonify, request, current_app
from backend.utils.logger import get_section_logger
from backend.services.diagnostics_service import DiagnosticsService
import os

diagnostics_bp = Blueprint('diagnostics', __name__, url_prefix='/api/v1/diagnostics')
logger = get_section_logger('api')

def get_service():
    return DiagnosticsService(current_app.config)

@diagnostics_bp.route('/health', methods=['GET'])
def check_health():
    """Quick health check for basic component status"""
    try:
        service = get_service()
        db_check = service.check_database()
        apps_script_check = service.check_apps_script()
        
        return jsonify({
            'status': 'healthy' if db_check['status'] == 'ok' else 'degraded',
            'database': db_check['status'],
            'apps_script': apps_script_check['status'],
            'nlp_ready': db_check.get('nlp_ready', False)
        }), 200
    except Exception as e:
        logger.error(f"Quick Healthcheck Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@diagnostics_bp.route('/full-check', methods=['GET'])
def perform_full_check():
    """Deep diagnostic check of the entire pipeline"""
    try:
        service = get_service()
        # Use request.host_url as a fallback for the public URL
        report = service.perform_full_checkup(request.host_url)
        return jsonify(report), 200
    except Exception as e:
        logger.error(f"Full Diagnostic Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@diagnostics_bp.route('/logs/<section>', methods=['GET'])
def read_section_logs(section):
    """Read the last 100 lines of a specific section's error log."""
    try:
        log_dir = os.path.join(current_app.root_path, 'logs')
        filename = f"{section}_errors.log"
        file_path = os.path.join(log_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'section': section, 'status': 'no_logs_found', 'lines': []}), 200
            
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
