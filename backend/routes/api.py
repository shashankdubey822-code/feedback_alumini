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
import sqlite3
import os

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


def get_consolidated_analytics(app, filters=None, search=None):
    """
    Consolidate data from all services into the format expected by the Premium frontend.
    This function bridges the modular backend services with the 'Premium' UI.
    """
    services = get_services(app)
    db_path = app.config.get('DATABASE_PATH', 'database/dashboard.db')
    
    # 1. Basic Stats & KPIs
    kpi_service = services['kpi']
    kpis = kpi_service.get_all_kpis()
    
    # Format KPIs for frontend
    formatted_kpis = []
    for k in kpis:
        formatted_kpis.append({
            'label': k.get('name', k.get('label', 'KPI')),
            'value': k.get('value', 0),
            'sub': k.get('change_label', '')
        })

    # 2. Charts
    chart_service = services['charts']
    raw_charts = chart_service.get_all_chart_data()
    
    # Transform raw charts into Premium format if needed
    formatted_charts = []
    # (Simplified transformation for now, would ideally match Chart.js schema)
    for chart_type, data in raw_charts.items():
        if chart_type == 'rating_distribution':
            formatted_charts.append({
                'title': 'Session Ratings',
                'type': 'doughnut',
                'labels': [d['label'] for d in data],
                'data': [d['value'] for d in data]
            })
        elif chart_type == 'department_ratings':
            formatted_charts.append({
                'title': 'Department Ratings',
                'type': 'bar',
                'labels': [d['department'] for d in data],
                'data': [d['average_rating'] for d in data],
                'yLabel': 'Avg Rating'
            })

    # 3. Speakers
    speaker_service = services['speakers']
    speakers = speaker_service.get_all_speakers()
    
    # 4. Table Data & Meta
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get columns
    cursor.execute("PRAGMA table_info(dashboard_data)")
    cols_info = cursor.fetchall()
    columns = [c['name'] for c in cols_info]
    
    # Simple query for all data
    query = "SELECT * FROM dashboard_data"
    where_clauses = []
    params = []
    
    if filters:
        for col, val in filters.items():
            if val:
                where_clauses.append(f"{col} = ?")
                params.append(val)
    
    if search:
        search_clauses = [f"{col} LIKE ?" for col in columns]
        where_clauses.append(f"({' OR '.join(search_clauses)})")
        params.extend([f"%{search}%"] * len(columns))
        
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " ORDER BY id DESC LIMIT 1000"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    table_data = [dict(r) for r in rows]
    conn.close()

    # 5. Filters
    formatted_filters = []
    # Identify categorical columns (e.g., Department)
    target_filter_cols = ['department_cleaned', 'alumni_speaker_name', 'session_rating']
    for col in target_filter_cols:
        if col in columns:
            cursor.execute(f"SELECT DISTINCT {col} FROM dashboard_data WHERE {col} IS NOT NULL AND {col} != ''")
            options = [{'value': str(r[0]), 'count': 0} for r in cursor.fetchall()]
            formatted_filters.append({
                'column': col,
                'type': 'categorical' if col != 'session_rating' else 'numeric',
                'options': options
            })

    # 6. NLP / Sentiment (Stub for now, can be populated via NLPService)
    # nlp_service = services['nlp']
    
    conn.close()

    # Construct final object
    return {
        'kpis': formatted_kpis,
        'filters': formatted_filters,
        'aiInsights': [
            {'type': 'trend', 'icon': '📈', 'text': 'Data synchronized successfully.'},
            {'type': 'success', 'icon': '🎯', 'text': f'Found {len(table_data)} feedback records in database.'}
        ],
        'charts': formatted_charts,
        'timeTrends': [],
        'sentiment': [],
        'keywords': [],
        'speakerStats': [{'speaker': s, 'sessions': 1} for s in speakers[:5]],
        'tableData': table_data,
        'meta': {
            'columns': columns,
            'columnTypes': {c: 'text' for c in columns}, # Simplified
            'filename': 'Hugging Face Database'
        }
    }
