"""
API Routes - REST endpoints for analytics and data retrieval
"""

from flask import Blueprint, jsonify, request
from ..services.analytics import AnalyticsService
from ..services.chart_service import ChartService
from ..services.nlp_service import NLPService
from ..services.speaker_service import SpeakerService
from ..services.kpi_service import KPIService
from ..utils.logger import get_section_logger, log_endpoint_access
import sqlite3
import os

logger = get_section_logger('api')

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
legacy_bp = Blueprint('legacy', __name__, url_prefix='/api')


def get_services(app):
    """Initialize services"""
    db_path = app.config.get('DATABASE_PATH', 'database/dashboard.db')
    return {
        'analytics': AnalyticsService(db_path),
        'charts': ChartService(db_path),
        'nlp': NLPService(),
        'speakers': SpeakerService(db_path),
        'kpi': KPIService(db_path),
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

        department = request.args.get('department', None)
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        limit = request.args.get('limit', 100, type=int)

        if department:
            records = services['analytics'].get_records_by_department(department, limit)
        elif start_date and end_date:
            records = services['analytics'].get_records_by_date_range(start_date, end_date)
        else:
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


@api_bp.route('/dl-status', methods=['GET'])
@log_endpoint_access
def get_dl_status():
    """Get Deep Learning background processing status"""
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(dashboard_data)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'dl_processed' not in cols:
            return jsonify({'processing_count': 0}), 200

        cursor.execute("SELECT COUNT(*) FROM dashboard_data WHERE dl_processed = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({'processing_count': count}), 200
    except Exception as e:
        logger.error(f"Error getting DL status: {str(e)}")
        return jsonify({'processing_count': 0, 'error': str(e)}), 500


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
        logger.error(f"Error in /api/data: {str(e)}")
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
        return jsonify(get_consolidated_analytics(current_app, filters=filters, search=search)), 200
    except Exception as e:
        logger.error(f"Error in /api/filter: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_consolidated_analytics(app, filters=None, search=None):
    """Consolidate analytics data for the dashboard."""
    db_path = app.config.get('DATABASE_PATH')

    # ── 1. KPIs ─────────────────────────────────────────────────────
    try:
        kpi_service = KPIService(db_path)
        kpi_dict = kpi_service.get_all_kpis()   # returns Dict[str, float]
    except Exception:
        kpi_dict = {}

    LABEL_MAP = {
        'engagement_rate':         'Engagement Rate',
        'satisfaction_score':      'Satisfaction Score',
        'completion_rate':         'Completion Rate',
        'department_coverage':     'Dept Coverage',
        'submission_velocity_7d':  'Submissions / Day (7d)',
        'submission_velocity_30d': 'Submissions / Day (30d)',
    }
    UNIT_MAP = {
        'engagement_rate':     '%',
        'satisfaction_score':  '%',
        'completion_rate':     '%',
        'department_coverage': '%',
    }
    # (KPIs will be finalized after table_data aggregation)
    formatted_kpis = []

    # ── 2. Charts ────────────────────────────────────────────────────
    try:
        chart_service = ChartService(db_path)
        raw_charts = chart_service.get_all_chart_data()
    except Exception:
        raw_charts = {}

    formatted_charts = []
    rd = raw_charts.get('rating_distribution', [])
    if rd:
        formatted_charts.append({
            'title':  'Session Rating Distribution',
            'type':   'doughnut',
            'labels': [d.get('label', '') for d in rd],
            'data':   [d.get('value', 0)  for d in rd],
            'column': 'session_rating',
            'columnType': 'numeric',
            'binBoundaries': [{'exact': d.get('rating')} for d in rd]
        })
    dr = raw_charts.get('department_ratings', [])
    if dr:
        formatted_charts.append({
            'title':  'Avg Rating by Department',
            'type':   'bar',
            'labels': [d.get('department', '')      for d in dr],
            'data':   [d.get('average_rating', 0)   for d in dr],
            'yLabel': 'Avg Rating',
            'xLabel': 'Department',
            'column': 'department_cleaned',
            'columnType': 'text'
        })

    # (Removed redundant SpeakerService call - will aggregate from table_data loop below)
    speaker_stats_payload = []

    # ── 4. Table data & meta ─────────────────────────────────────────
    conn = get_db_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get column names
    cursor.execute("PRAGMA table_info(dashboard_data)")
    columns = [row['name'] for row in cursor.fetchall()]

    # Build filtered query (whitelist columns to prevent injection)
    query = "SELECT * FROM dashboard_data"
    where_clauses = []
    params = []

    if filters:
        for col, val in filters.items():
            if val is not None and col in columns:
                if isinstance(val, list):
                    placeholders = ', '.join(['?'] * len(val))
                    where_clauses.append(f"`{col}` IN ({placeholders})")
                    params.extend(val)
                else:
                    where_clauses.append(f"`{col}` = ?")
                    params.append(val)

    if search and columns:
        search_clauses = [f"`{col}` LIKE ?" for col in columns]
        where_clauses.append(f"({' OR '.join(search_clauses)})")
        params.extend([f"%{search}%"] * len(columns))

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY id DESC LIMIT 1000"

    cursor.execute(query, params)
    table_data = [dict(row) for row in cursor.fetchall()]

    # Build filter panel options
    formatted_filters = []
    for col in ['department_cleaned', 'alumni_speaker_name']:
        if col in columns:
            cursor.execute(
                f"SELECT DISTINCT `{col}`, COUNT(*) as cnt "
                f"FROM dashboard_data "
                f"WHERE `{col}` IS NOT NULL AND `{col}` != '' "
                f"GROUP BY `{col}` ORDER BY cnt DESC"
            )
            opts = [{'value': str(r[0]), 'count': r[1]} for r in cursor.fetchall()]
            if opts:
                formatted_filters.append({'column': col, 'type': 'categorical', 'options': opts})

    conn.close()

    # ── 5. Total Responses KPI ───────────────────────────────────────
    total_count = len(table_data)
    formatted_kpis.insert(0, {
        'label': 'Total Responses',
        'value': str(total_count),
        'sub':   'All-time records'
    })

    # ── 6. Column type detection ─────────────────────────────────────
    num_keywords  = {'rating', 'score', 'count', 'num', 'total', 'age', 'year'}
    date_keywords = {'date', 'time', 'timestamp'}
    col_types = {}
    for col in columns:
        cl = col.lower()
        if any(k in cl for k in date_keywords):
            col_types[col] = 'date'
        elif any(k in cl for k in num_keywords):
            col_types[col] = 'numeric'
        else:
            col_types[col] = 'text'

    # ── 7. Deep Learning Payload Aggregation ─────────────────────────
    sentiment_counts = {'POSITIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0}
    keyword_freq = {}
    
    # New Deep Analysis trackers
    imp_sentiment = {'POSITIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0, 'NO_RESPONSE': 0}
    val_sentiment = {'POSITIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0, 'NO_RESPONSE': 0}
    actionable_stats = {'actionable': 0, 'non_actionable': 0}
    category_counts = {}
    future_keyword_freq = {}
    val_keyword_freq = {}
    imp_keyword_freq = {}
    session_understanding_counts = {}
    
    import json
    speaker_tracker = {} # name -> {count, total_rating, total_sentiment}
    time_tracker    = {} # date -> count

    total_rating_sum = 0.0
    total_rating_count = 0

    for row in table_data:
        # KPI calculations (vitals)
        try:
            r_val = float(row.get('session_rating') or 0)
            if r_val > 0:
                total_rating_sum += r_val
                total_rating_count += 1
        except: pass

        # Speaker Tracking
        sp_name = row.get('alumni_speaker_name')
        if sp_name:
            if sp_name not in speaker_tracker:
                speaker_tracker[sp_name] = {'count': 0, 'total_rating': 0, 'total_sentiment': 0}
            speaker_tracker[sp_name]['count'] += 1
            try:
                speaker_tracker[sp_name]['total_rating'] += float(row.get('session_rating') or 0)
                speaker_tracker[sp_name]['total_sentiment'] += float(row.get('dl_sentiment_score') or 0)
            except: pass

        # Time Tracking
        raw_ts = row.get('timestamp_normalized') or row.get('timestamp_original')
        if raw_ts and len(str(raw_ts)) >= 10:
            date_key = str(raw_ts)[:10] # YYYY-MM-DD
            time_tracker[date_key] = time_tracker.get(date_key, 0) + 1

        # Sentiment (legacy)
        label = str(row.get('dl_sentiment_label', '')).upper()
        if label in sentiment_counts:
            sentiment_counts[label] += 1
            
        # Keywords & Deep Analytics
        kw_str = row.get('dl_keywords')
        if kw_str:
            try:
                kws = json.loads(kw_str) 
                
                if isinstance(kws, dict):
                    # Actionable vs Non Actionable
                    if kws.get('is_actionable') == 1:
                        actionable_stats['actionable'] += 1
                    else:
                        actionable_stats['non_actionable'] += 1
                        
                    # Column-level sentinel
                    imp_l = str(kws.get('improvements_sentiment', '')).upper()
                    if imp_l in imp_sentiment:
                        imp_sentiment[imp_l] += 1
                        
                    val_l = str(kws.get('valuable_sentiment', '')).upper()
                    if val_l in val_sentiment:
                        val_sentiment[val_l] += 1
                        
                    # Categories
                    cat = kws.get('category', 'Other')
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    
                    # Future words
                    for kw in kws.get('future_keywords', []):
                        word = kw[0] if isinstance(kw, (list, tuple)) else kw
                        if isinstance(word, str):
                            word = word.lower()
                            future_keyword_freq[word] = future_keyword_freq.get(word, 0) + 1
                
                # Session Help Understanding stats
                shu = row.get('session_help_understanding')
                if shu:
                    session_understanding_counts[shu] = session_understanding_counts.get(shu, 0) + 1
                            
                    # Future Topics Keywords (Specialized)
                    fut_kws = kws.get('future_keywords', [])
                    for k in fut_kws:
                        word = k[0] if isinstance(k, (list, tuple)) else k
                        if isinstance(word, str):
                            word = word.lower()
                            future_keyword_freq[word] = future_keyword_freq.get(word, 0) + 1
                        
                    # Valuable Aspects Keywords
                    val_kws = kws.get('val_keywords', [])
                    for k in val_kws:
                        word = k[0] if isinstance(k, (list, tuple)) else k
                        if isinstance(word, str):
                            word = word.lower()
                            val_keyword_freq[word] = val_keyword_freq.get(word, 0) + 1

                    # Improvements Keywords
                    imp_kws = kws.get('imp_keywords', [])
                    for k in imp_kws:
                        word = k[0] if isinstance(k, (list, tuple)) else k
                        if isinstance(word, str):
                            word = word.lower()
                            imp_keyword_freq[word] = imp_keyword_freq.get(word, 0) + 1
                            
                    # Add back general keywords for original widget
                    gen_kws = kws.get('general_keywords', [])
                    for kw in gen_kws:
                        word = kw[0] if isinstance(kw, (list, tuple)) else kw
                        if isinstance(word, str):
                            word = word.lower()
                            keyword_freq[word] = keyword_freq.get(word, 0) + 1
                            
                elif isinstance(kws, list):
                    for kw in kws:
                        word = kw[0] if isinstance(kw, (list, tuple)) else kw
                        if isinstance(word, str):
                            word = word.lower()
                            keyword_freq[word] = keyword_freq.get(word, 0) + 1
            except Exception:
                pass

    total_sentiment_processed = sum(sentiment_counts.values()) or 1
    avg_polarity = (sentiment_counts['POSITIVE'] - sentiment_counts['NEGATIVE']) / total_sentiment_processed

    formatted_sentiment = []
    
    # 1. Legacy Overall Deep Learning Network
    if total_sentiment_processed > 1 or sentiment_counts['POSITIVE'] > 0:
        formatted_sentiment.append({
            'column': 'Deep Analysis: Overall Extracted Sentiment',
            'positive': sentiment_counts['POSITIVE'],
            'neutral': sentiment_counts['NEUTRAL'],
            'negative': sentiment_counts['NEGATIVE'],
            'total': total_sentiment_processed,
            'avgPolarity': avg_polarity,
            'avgSubjectivity': 0.75,
            'nonAnswers': total_count - total_sentiment_processed
        })
        
    # 2. Deep Analysis: Improvements
    imp_total = sum(v for k, v in imp_sentiment.items() if k != 'NO_RESPONSE') or 1
    if imp_total > 1 or imp_sentiment['POSITIVE'] > 0:
        formatted_sentiment.append({
            'column': 'Deep Analysis: Suggestions & Improvements',
            'positive': imp_sentiment['POSITIVE'],
            'neutral': imp_sentiment['NEUTRAL'],
            'negative': imp_sentiment['NEGATIVE'],
            'total': imp_total,
            'avgPolarity': (imp_sentiment['POSITIVE'] - imp_sentiment['NEGATIVE']) / imp_total,
            'avgSubjectivity': 0.8,
            'nonAnswers': imp_sentiment.get('NO_RESPONSE', 0)
        })

    # 3. Deep Analysis: Valuable Aspects
    val_total = sum(v for k, v in val_sentiment.items() if k != 'NO_RESPONSE') or 1
    if val_total > 1 or val_sentiment['POSITIVE'] > 0:
        formatted_sentiment.append({
            'column': 'Deep Analysis: Valuable Aspects',
            'positive': val_sentiment['POSITIVE'],
            'neutral': val_sentiment['NEUTRAL'],
            'negative': val_sentiment['NEGATIVE'],
            'total': val_total,
            'avgPolarity': (val_sentiment['POSITIVE'] - val_sentiment['NEGATIVE']) / val_total,
            'avgSubjectivity': 0.8,
            'nonAnswers': val_sentiment.get('NO_RESPONSE', 0)
        })

    # 4. Keywords
    formatted_keywords = []

    sorted_fut_keywords = sorted(future_keyword_freq.items(), key=lambda x: x[1], reverse=True)[:40]
    if sorted_fut_keywords:
        formatted_keywords.append({
            'column': 'Deep Analysis: Requested Future Topics',
            'words': [{'text': k, 'count': v, 'type': 'unigram' if len(k.split()) == 1 else 'bigram'} for k, v in sorted_fut_keywords]
        })

    sorted_val_keywords = sorted(val_keyword_freq.items(), key=lambda x: x[1], reverse=True)[:40]
    if sorted_val_keywords:
        formatted_keywords.append({
            'column': 'Deep Analysis: Valuable Aspects',
            'words': [{'text': k, 'count': v, 'type': 'unigram' if len(k.split()) == 1 else 'bigram'} for k, v in sorted_val_keywords]
        })

    sorted_imp_keywords = sorted(imp_keyword_freq.items(), key=lambda x: x[1], reverse=True)[:40]
    if sorted_imp_keywords:
        formatted_keywords.append({
            'column': 'Deep Analysis: Improvement Suggestions',
            'words': [{'text': k, 'count': v, 'type': 'unigram' if len(k.split()) == 1 else 'bigram'} for k, v in sorted_imp_keywords]
        })
    
    # Finalize Speaker Stats from tracker
    speaker_list = []
    for name, stats in speaker_tracker.items():
        avg_rating = stats['total_rating'] / stats['count'] if stats['count'] > 0 else 0
        avg_sentiment = stats['total_sentiment'] / stats['count'] if stats['count'] > 0 else 0
        speaker_list.append({
            'name': name,
            'count': stats['count'],
            'sentiment': round(avg_sentiment, 2),
            'ratings': {'Rating': round(avg_rating, 1)}
        })
    
    # Sort speakers by response count
    speaker_list.sort(key=lambda x: x['count'], reverse=True)

    speaker_stats_payload = [{
        'column': 'alumni_speaker_name',
        'speakers': speaker_list
    }]

    # Bundle the deep analysis payload
    deep_analysis = {
        'actionableStats': actionable_stats,
        'categories': [{'name': k, 'value': v} for k, v in sorted(category_counts.items(), key=lambda x: x[1], reverse=True) if k != "Other"]
    }

    # Add Session Impact to main charts
    if session_understanding_counts:
        # Semantic order: Positive -> Neutral -> Negative
        order = {"Yes, significantly": 0, "To some extent": 1, "Not really": 2}
        sorted_shu = sorted(session_understanding_counts.items(), key=lambda x: order.get(x[0], 99))
        
        formatted_charts.append({
            'title': 'Session Impact (Understanding Level)',
            'type': 'bar',
            'labels': [k for k, v in sorted_shu],
            'data': [v for k, v in sorted_shu],
            'column': 'session_help_understanding',
            'columnType': 'text',
            'backgroundColors': ['#34d399', '#fbbf24', '#fb7185'] 
        })

    # ── 8. Dynamic AI Insights Generation ─────────────────────────────
    ai_insights = [
        {'type': 'trend',   'icon': '📈', 'text': 'Dashboard data synchronized.'},
        {'type': 'success', 'icon': '🎯', 'text': f'Found {total_count} feedback records.'}
    ]
    
    # Sentiment Insight
    total_sentiment = sum(sentiment_counts.values())
    if total_sentiment > 0:
        pos_pct = round((sentiment_counts['POSITIVE'] / total_sentiment) * 100)
        if pos_pct >= 70:
            ai_insights.append({'type': 'success', 'icon': '✨', 'text': f'Strong positive reception: {pos_pct}% of attendees enjoyed the session.'})
        elif pos_pct < 40:
            ai_insights.append({'type': 'warning', 'icon': '⚠️', 'text': f'Mixed reception: Only {pos_pct}% positive sentiment detected in detailed feedback.'})
            
    # Topic Insight
    if sorted_fut_keywords:
        top_topic = sorted_fut_keywords[0][0]
        count = sorted_fut_keywords[0][1]
        if count > 1:
            ai_insights.append({'type': 'info', 'icon': '💡', 'text': f'Future Trend: "{top_topic.title()}" is the most requested topic for upcoming sessions.'})
            
    # Actionability Insight
    act_count = actionable_stats['actionable']
    if act_count > 0:
        ai_insights.append({'type': 'warning', 'icon': '🛡️', 'text': f'Action required: {act_count} records contain specific, implementable improvement suggestions.'})
        
    # Speaker Insight
    if speaker_list:
        top_speaker = speaker_list[0]
        ts_ratings = top_speaker.get('ratings', {})
        if ts_ratings.get('Rating', 0) >= 4.5:
             ai_insights.append({'type': 'success', 'icon': '🌟', 'text': f'Top Performer: {top_speaker["name"]} achieved a perfect rating from most attendees.'})

    # Participation Insight
    if category_counts:
        top_cat = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[0]
        if top_cat[1] > total_count * 0.3:
            ai_insights.append({'type': 'info', 'icon': '🚀', 'text': f'Key Focus: Feedback is heavily centered on "{top_cat[0]}" related themes.'})

    # Finalize Time Trends
    sorted_dates = sorted(time_tracker.keys())
    formatted_trends = []
    # Finalize KPIs using the aggregated vitals
    avg_rating = 0.0
    if total_rating_count > 0:
        avg_rating = round(float(total_rating_sum) / total_rating_count, 1)
    formatted_kpis.append({
        'label': 'Total Responses',
        'value': str(total_count),
        'sub':   'Filtered results'
    })
    formatted_kpis.append({
        'label': 'Average Rating',
        'value': f"{avg_rating}/5",
        'sub':   f'From {total_rating_count} ratings'
    })
    # Add sentiment KPI
    pos_pct = round((sentiment_counts['POSITIVE'] / total_count * 100)) if total_count > 0 else 0
    formatted_kpis.append({
        'label': 'Positive Sentiment',
        'value': f"{pos_pct}%",
        'sub':   'Detailed feedback'
    })

    return {
        'kpis':         formatted_kpis,
        'filters':      formatted_filters,
        'aiInsights':   ai_insights,
        'charts':       formatted_charts,
        'sentiment':    formatted_sentiment,
        'keywords':     formatted_keywords,
        'deepAnalysis': deep_analysis,
        'speakerStats': speaker_stats_payload,
        'tableData':    table_data,
        'meta': {
            'columns':     columns,
            'columnTypes': col_types,
            'filename':    'Hugging Face Database'
        }
    }
