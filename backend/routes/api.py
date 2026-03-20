"""
API Routes - REST endpoints for analytics and data retrieval
"""

from flask import Blueprint, jsonify, request
from ..services.analytics import AnalyticsService
from ..services.chart_service import ChartService
from ..services.nlp_service import NLPService
from ..services.speaker_service import SpeakerService
from ..services.kpi_service import KPIService
from ..services.time_trend_service import TimeTrendService
from ..utils.logger import get_logger, log_endpoint_access

logger = get_logger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


def get_services(app):
    """Initialize services"""
    db_path = app.config.get('DATABASE_PATH', 'database/dashboard.db')
    return {
        'analytics': AnalyticsService(db_path),
        'charts': ChartService(db_path),
        'nlp': NLPService(),
        'speakers': SpeakerService(db_path),
        'kpi': KPIService(db_path),
        'trends': TimeTrendService(db_path),
    }


@api_bp.route('/health', methods=['GET'])
@log_endpoint_access
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'API is running',
    }), 200


@api_bp.route('/analytics/summary', methods=['GET'])
@log_endpoint_access
def get_analytics_summary():
    """Get comprehensive analytics summary"""
    try:
        from flask import current_app
        services = get_services(current_app)
        summary = services['analytics'].get_statistics_summary()
        return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Error getting analytics summary: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/records', methods=['GET'])
@log_endpoint_access
def get_records():
    """Get all feedback records with optional filtering"""
    try:
        from flask import current_app
        services = get_services(current_app)

        # Get filters from query parameters
        department = request.args.get('department', None)
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        limit = request.args.get('limit', 100, type=int)

        if department:
            records = services['analytics'].get_records_by_department(department, limit)
        elif start_date and end_date:
            records = services['analytics'].get_records_by_date_range(start_date, end_date)
        else:
            # Get all records
            from backend.models.schemas import FeedbackRecord
            conn = services['analytics'].get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM dashboard_data ORDER BY timestamp_normalized DESC LIMIT ?', (limit,))
            records = [dict(row) for row in cursor.fetchall()]
            conn.close()

        return jsonify({
            'count': len(records),
            'records': records[:limit]
        }), 200
    except Exception as e:
        logger.error(f"Error getting records: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/departments', methods=['GET'])
@log_endpoint_access
def get_department_analytics():
    """Get department-wise analytics"""
    try:
        from flask import current_app
        services = get_services(current_app)
        distribution = services['analytics'].get_department_distribution()
        return jsonify({'departments': distribution}), 200
    except Exception as e:
        logger.error(f"Error getting department analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/quality', methods=['GET'])
@log_endpoint_access
def get_data_quality():
    """Get data quality metrics"""
    try:
        from flask import current_app
        services = get_services(current_app)
        metrics = services['analytics'].get_data_quality_metrics()
        return jsonify(metrics), 200
    except Exception as e:
        logger.error(f"Error getting data quality: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/charts/all', methods=['GET'])
@log_endpoint_access
def get_all_charts():
    """Get all chart data"""
    try:
        from flask import current_app
        services = get_services(current_app)
        charts = services['charts'].get_all_chart_data()
        return jsonify(charts), 200
    except Exception as e:
        logger.error(f"Error getting charts: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/speakers', methods=['GET'])
@log_endpoint_access
def get_speakers():
    """Get all speakers"""
    try:
        from flask import current_app
        services = get_services(current_app)
        speakers = services['speakers'].get_all_speakers()
        return jsonify({'speakers': speakers}), 200
    except Exception as e:
        logger.error(f"Error getting speakers: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/speakers/<speaker_name>', methods=['GET'])
@log_endpoint_access
def get_speaker_detail(speaker_name):
    """Get speaker profile and feedback"""
    try:
        from flask import current_app
        services = get_services(current_app)
        profile = services['speakers'].get_speaker_profile(speaker_name)
        feedback = services['speakers'].get_speaker_feedback_summary(speaker_name)
        return jsonify({
            'profile': profile,
            'feedback': feedback,
        }), 200
    except Exception as e:
        logger.error(f"Error getting speaker detail: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/kpi/all', methods=['GET'])
@log_endpoint_access
def get_all_kpis():
    """Get all KPIs"""
    try:
        from flask import current_app
        services = get_services(current_app)
        kpis = services['kpi'].get_all_kpis()
        health = services['kpi'].get_kpi_health_status()
        return jsonify({
            'kpis': kpis,
            'health_status': health,
        }), 200
    except Exception as e:
        logger.error(f"Error getting KPIs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/trends/all', methods=['GET'])
@log_endpoint_access
def get_all_trends():
    """Get all trend data"""
    try:
        from flask import current_app
        services = get_services(current_app)
        trends = services['trends'].get_all_trends()
        return jsonify(trends), 200
    except Exception as e:
        logger.error(f"Error getting trends: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500
