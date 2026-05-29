"""
API Routes - REST endpoints for analytics and data retrieval
"""

import json
import os
import time
from flask import Blueprint, jsonify, request
from ..services.chart_service import ChartService
from ..services.nlp_service import NLPService
from ..services.kpi_service import KPIService
from ..utils.logger import get_section_logger, log_endpoint_access
from ..utils.supabase_db import get_db, execute_all, execute_one
from ..services.analytics_engine import analytics_engine

logger = get_section_logger('api')

_DL_STATUS_CACHE = {'value': 0, 'timestamp': 0.0}
_DL_STATUS_CACHE_TTL = float(os.getenv('DL_STATUS_CACHE_TTL', '5'))

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
legacy_bp = Blueprint('legacy', __name__, url_prefix='/api')


def get_services(app):
    """Initialize services — NLPService is cached on the app object (singleton)."""
    if not hasattr(app, '_nlp_service'):
        app._nlp_service = NLPService()
    return {
        'charts': ChartService(),
        'nlp': app._nlp_service,
        'kpi': KPIService(),
    }


@api_bp.route('/health', methods=['GET'])
@log_endpoint_access
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'API is running',
    }), 200


@api_bp.route('/initial', methods=['GET'])
@log_endpoint_access
def get_initial():
    """Return a minimal, fast payload for initial page rendering.
    Keeps DB work small: total counts and a tiny sample of recent rows.
    """
    try:
        # Get data from the blazing fast in-memory pandas engine
        payload = analytics_engine.get_initial_payload()
        return jsonify(payload), 200
    except Exception as e:
        logger.error(f"Error getting initial payload: {e}")
        return jsonify({'error': 'Failed to fetch initial payload'}), 500


# Backwards-compatible legacy endpoint for older frontend builds that call /api/initial
@legacy_bp.route('/initial', methods=['GET'])
@log_endpoint_access
def legacy_get_initial():
    """Legacy wrapper to support frontend requests to /api/initial (no version prefix)."""
    return get_initial()


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
    """Get all trend data (time-series from feedback_responses)"""
    try:
        rows = execute_all("""
            SELECT DATE(submitted_at) AS date, COUNT(*) AS count
            FROM feedback_responses
            WHERE submitted_at IS NOT NULL
            GROUP BY DATE(submitted_at)
            ORDER BY date ASC
        """)
        return jsonify({'trends': [dict(r) for r in rows]}), 200
    except Exception as e:
        logger.error(f"Error getting trends: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dl-status', methods=['GET'])
@log_endpoint_access
def get_dl_status():
    """Get Deep Learning background processing status (unprocessed feedback_responses)"""
    try:
        now = time.time()
        if now - _DL_STATUS_CACHE['timestamp'] < _DL_STATUS_CACHE_TTL:
            return jsonify({'processing_count': _DL_STATUS_CACHE['value'], 'cached': True}), 200

        row = execute_one("""
            SELECT COUNT(*) AS cnt FROM feedback_responses r
            WHERE NOT EXISTS (
                SELECT 1 FROM feedback_analysis a WHERE a.response_id = r.id
            )
        """)
        count = row['cnt'] if row else 0
        _DL_STATUS_CACHE['value'] = count
        _DL_STATUS_CACHE['timestamp'] = now
        return jsonify({'processing_count': count, 'cached': False}), 200
    except Exception as e:
        logger.error(f"Error getting DL status: {str(e)}")
        if _DL_STATUS_CACHE['timestamp'] > 0:
            return jsonify({'processing_count': _DL_STATUS_CACHE['value'], 'cached': True, 'stale': True, 'error': str(e)}), 200
        return jsonify({'processing_count': 0, 'error': str(e)}), 500


@api_bp.route('/errors/report', methods=['GET'])
@log_endpoint_access
def get_error_report():
    """Run all page-level error detectors and return a structured report."""
    try:
        from flask import current_app
        from ..error_detection.reporter import run_all_checks
        db_path = current_app.config.get('DATABASE_PATH', 'dashboard.db')
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'uploads')
        report = run_all_checks(db_path, upload_dir)
        return jsonify(report), 200
    except Exception as e:
        logger.error(f"Error running error report: {str(e)}")
        return jsonify({'error': str(e)}), 500


@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


# ════════════════════════════════════════════════════════════════════
#  CONSOLIDATED ANALYTICS  —  used by /api/data and /api/filter
#  This bridges the modular backend to the Premium frontend (app.js)
# ════════════════════════════════════════════════════════════════════

@legacy_bp.route('/data', methods=['GET'])
@log_endpoint_access
def get_legacy_data():
    """Unified analytics payload for the Premium frontend (app.js)"""
    try:
        from flask import current_app
        return jsonify(get_consolidated_analytics(current_app)), 200
    except Exception as e:
        logger.exception(f"CRITICAL Error in /api/data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@legacy_bp.route('/filter', methods=['POST'])
@log_endpoint_access
def get_legacy_filter():
    """Filtered analytics payload for the Premium frontend"""
    try:
        from flask import current_app
        body = request.get_json() or {}
        filters = body.get('filters', {})
        search = body.get('search', '')
        # Pagination support
        page = int(body.get('page', 1)) if body.get('page') else 1
        page_size = int(body.get('page_size', 25)) if body.get('page_size') else 25
        return jsonify(get_consolidated_analytics(current_app, filters=filters, search=search, page=page, page_size=page_size)), 200
    except Exception as e:
        logger.error(f"Error in /api/filter: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_consolidated_analytics(app, filters=None, search=None, page=1, page_size=25):
    """Consolidate analytics data for the dashboard using in-memory Analytics Engine."""
    from ..services.analytics_engine import analytics_engine
    import json
    
    try:
        from ..services.kpi_service import KPIService
        kpi_service = KPIService()
        kpi_dict = kpi_service.get_all_kpis()
    except Exception:
        kpi_dict = {}

    try:
        from ..services.chart_service import ChartService
        chart_service = ChartService()
        raw_charts = chart_service.get_all_chart_data()
    except Exception:
        raw_charts = {}

    formatted_charts = []
    rd = raw_charts.get('rating_distribution', [])
    if rd:
        formatted_charts.append({
            'title': 'Session Rating Distribution', 'type': 'doughnut',
            'labels': [d.get('label', '') for d in rd],
            'data':   [d.get('value', 0)  for d in rd],
            'column': 'session_rating', 'columnType': 'numeric',
            'binBoundaries': [{'exact': d.get('rating')} for d in rd]
        })
    dr = raw_charts.get('department_ratings', [])
    if dr:
        formatted_charts.append({
            'title': 'Avg Rating by Department', 'type': 'bar',
            'labels': [d.get('department', '')    for d in dr],
            'data':   [d.get('average_rating', 0) for d in dr],
            'yLabel': 'Avg Rating', 'xLabel': 'Department',
            'column': 'department', 'columnType': 'text'
        })
    speaker_stats_payload = []

    # ── 3. Table data (from pandas) ──────────────────────────────────
    import pandas as pd
    df = analytics_engine.get_dataframe()
    
    if filters:
        for col, val in filters.items():
            if val and col in df.columns:
                if isinstance(val, list):
                    df = df[df[col].isin(val)]
                else:
                    df = df[df[col] == val]
                    
    if search:
        search_lower = search.lower()
        search_cols = ['student_name', 'department', 'speaker_name', 'aspect_most_valuable', 'improvements_suggestions', 'future_topics']
        if not df.empty:
            mask = df[search_cols].astype(str).apply(lambda x: x.str.lower().str.contains(search_lower)).any(axis=1)
            df = df[mask]
        
    total_count = len(df)
    
    offset = max((int(page) - 1), 0) * int(page_size)
    page_df = df.iloc[offset:offset+int(page_size)] if not df.empty else df
    
    table_data = []
    for _, row in page_df.iterrows():
        table_data.append({
            'id': row['response_id'],
            'timestamp_display': row['submitted_at'].strftime('%d-%m-%Y %H:%M:%S') if pd.notnull(row['submitted_at']) else '',
            'name_of_student': row.get('student_name', ''),
            'roll_no': row.get('roll_no', ''),
            'department': row.get('department', ''),
            'date_of_lecture': row.get('venue_date', ''),
            'alumni_speaker_name': row.get('speaker_name', ''),
            'session_rating': row.get('session_rating', ''),
            'aspect_most_valuable': row.get('aspect_most_valuable', ''),
            'improvements_suggestions': row.get('improvements_suggestions', ''),
            'session_help_understanding': row.get('session_help_understanding', ''),
            'future_topics': row.get('future_topics', ''),
            'dl_sentiment_label': row.get('sentiment_label', ''),
            'dl_sentiment_score': row.get('sentiment_score', ''),
            'dl_keywords': row.get('keywords_json', None)
        })

    formatted_filters = []
    if not df.empty:
        for col, label in [('department', 'department'), ('speaker_name', 'alumni_speaker_name')]:
            counts = df[col].value_counts()
            opts = [{'value': k, 'count': v} for k, v in counts.items() if k]
            if opts:
                formatted_filters.append({'column': label, 'type': 'categorical', 'options': opts})

    kpis = list(kpi_dict.values()) if isinstance(kpi_dict, dict) else kpi_dict
    
    columns = list(table_data[0].keys()) if table_data else []
    col_types = {c: 'text' for c in columns}
    col_types['session_rating'] = 'numeric'
    col_types['timestamp_display'] = 'date'
    
    sentiment_counts = df['sentiment_label'].value_counts().to_dict() if not df.empty and 'sentiment_label' in df else {}
    actionable_stats = {'actionable': 0, 'non_actionable': 0}
    category_counts = {}
    
    if not df.empty and 'keywords_json' in df:
        for kws in df['keywords_json'].dropna():
            if isinstance(kws, dict):
                if kws.get('is_actionable') == 1:
                    actionable_stats['actionable'] += 1
                else:
                    actionable_stats['non_actionable'] += 1
                cat = kws.get('category', 'Other')
                category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        'meta': {
            'columns': columns,
            'columnTypes': col_types,
            'filters': formatted_filters,
            'filename': 'Analytics',
            'page': page,
            'pageSize': page_size,
            'totalPages': (total_count // int(page_size)) + (1 if total_count % int(page_size) > 0 else 0)
        },
        'tableData': table_data,
        'charts': formatted_charts,
        'kpis': kpis,
        'speaker_stats': speaker_stats_payload,
        'deep_analytics': {
            'actionable_stats': actionable_stats,
            'category_counts': category_counts,
            'sentiment_counts': sentiment_counts
        },
        'totalResponses': total_count
    }

