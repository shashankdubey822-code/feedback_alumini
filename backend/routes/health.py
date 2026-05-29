"""
Health Routes - Service health and status monitoring
"""

from flask import Blueprint, jsonify
from backend.utils import pg_helper as sqlite3
from ..utils.logger import get_logger
from ..utils.db_helper import get_db_connection

logger = get_logger(__name__)

health_bp = Blueprint('health', __name__, url_prefix='/api/v1')


def check_database_health(db_path: str) -> dict:
    """Check database connection and basic statistics"""
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        # Check if main table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_data'"
        )
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # Get record count
            cursor.execute('SELECT COUNT(*) as count FROM dashboard_data')
            record_count = cursor.fetchone()[0]

            cursor.execute(
                'SELECT COUNT(*) as count FROM dashboard_data WHERE data_quality_score >= 80'
            )
            quality_count = cursor.fetchone()[0]

            health_percentage = (quality_count / record_count * 100) if record_count > 0 else 0

            conn.close()

            return {
                'status': 'healthy',
                'table_exists': True,
                'record_count': record_count,
                'good_quality_records': quality_count,
                'health_percentage': round(health_percentage, 2),
            }
        else:
            conn.close()
            return {
                'status': 'unhealthy',
                'table_exists': False,
                'message': 'Dashboard data table not found',
            }

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
        }


@health_bp.route('/health', methods=['GET'])
def health_check():
    """Overall application health check"""
    try:
        from flask import current_app

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        db_health = check_database_health(db_path)

        overall_status = 'healthy' if db_health.get('status') == 'healthy' else 'degraded'

        return jsonify({
            'status': overall_status,
            'database': db_health,
            'version': '1.0.0',
        }), 200

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
        }), 500


@health_bp.route('/health/database', methods=['GET'])
def database_health():
    """Check database health"""
    try:
        from flask import current_app

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        db_health = check_database_health(db_path)

        status_code = 200 if db_health.get('status') == 'healthy' else 503

        return jsonify(db_health), status_code

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
        }), 500


@health_bp.route('/status', methods=['GET'])
def status():
    """Get application status"""
    try:
        from flask import current_app

        return jsonify({
            'status': 'operational',
            'environment': current_app.config.get('FLASK_ENV', 'production'),
            'debug': current_app.debug,
            'api_version': '1.0.0',
        }), 200

    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
        }), 500
