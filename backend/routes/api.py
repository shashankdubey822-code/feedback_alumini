"""
API Routes - REST endpoints for analytics and data retrieval
"""

from flask import Blueprint, jsonify, request
from ..services.chart_service import ChartService
from ..services.nlp_service import NLPService
from ..services.kpi_service import KPIService
from ..utils.logger import get_section_logger, log_endpoint_access
import sqlite3
import os
from ..utils.db_helper import get_db_connection

logger = get_section_logger('api')

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
legacy_bp = Blueprint('legacy', __name__, url_prefix='/api')


def get_services(app):
    """Initialize services — NLPService is cached on the app object (singleton)."""
    db_path = app.config.get('DATABASE_PATH', 'dashboard.db')
    if not hasattr(app, '_nlp_service'):
        app._nlp_service = NLPService()
    return {
        'charts': ChartService(db_path),
        'nlp': app._nlp_service,
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
    """Get all trend data (time-series from dashboard_data)"""
    try:
        from flask import current_app
        db_path = current_app.config.get('DATABASE_PATH', 'dashboard.db')
        conn = get_db_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE(timestamp_normalized) as date, COUNT(*) as count
            FROM dashboard_data
            WHERE timestamp_normalized IS NOT NULL
            GROUP BY DATE(timestamp_normalized)
            ORDER BY date ASC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'trends': rows}), 200
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
    query += " ORDER BY id DESC"

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
    topic_freq = {}  # BERTopic cluster label → count
    dept_counts = {}  # department → response count
    rating_by_dept = {}  # department → [ratings]
    
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

        # Department tracking
        dept = row.get('department_cleaned') or row.get('Department') or ''
        if dept:
            # Shorten long school names for display
            short = dept.replace('School of Engineering: ', '').replace('School of ', '')
            dept_counts[short] = dept_counts.get(short, 0) + 1
            try:
                r_val2 = float(row.get('session_rating') or 0)
                if r_val2 > 0:
                    if short not in rating_by_dept:
                        rating_by_dept[short] = []
                    rating_by_dept[short].append(r_val2)
            except: pass

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

                    # BERTopic cluster label
                    topic_lbl = kws.get('topic_label')
                    if topic_lbl and topic_lbl not in ('Uncategorised', ''):
                        topic_freq[topic_lbl] = topic_freq.get(topic_lbl, 0) + 1
                            
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
        'categories': [{'name': k, 'value': v} for k, v in sorted(category_counts.items(), key=lambda x: x[1], reverse=True) if k != "Other"],
        'topicClusters': [{'name': k, 'value': v} for k, v in sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)],
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

    # Department response breakdown
    if dept_counts:
        sorted_depts = sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)
        formatted_charts.append({
            'title': 'Responses by Department',
            'type': 'horizontalBar',
            'labels': [d for d, _ in sorted_depts],
            'data': [v for _, v in sorted_depts],
            'column': 'department_cleaned',
            'columnType': 'text',
        })

    # Avg rating by department (if we have enough data)
    dept_avg_ratings = {d: round(sum(rs) / len(rs), 2) for d, rs in rating_by_dept.items() if len(rs) >= 2}
    if dept_avg_ratings:
        sorted_dept_ratings = sorted(dept_avg_ratings.items(), key=lambda x: x[1], reverse=True)
        formatted_charts.append({
            'title': 'Avg Session Rating by Department',
            'type': 'bar',
            'labels': [d for d, _ in sorted_dept_ratings],
            'data': [v for _, v in sorted_dept_ratings],
            'column': 'department_cleaned',
            'columnType': 'text',
            'yLabel': 'Avg Rating',
        })

    # ── 8. Dynamic AI Insights Generation ─────────────────────────────
    ai_insights = [
        {'type': 'trend',   'icon': '📈', 'text': 'Dashboard data synchronized.'},
        {'type': 'success', 'icon': '🎯', 'text': f'Analysed {total_count} feedback records across {len(dept_counts)} department{"s" if len(dept_counts) != 1 else ""}.'}
    ]

    # Department participation insight
    if dept_counts:
        top_dept = sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)[0]
        dept_pct = round(top_dept[1] / total_count * 100) if total_count else 0
        ai_insights.append({'type': 'info', 'icon': '🏫', 'text': f'Highest participation: {top_dept[0]} contributed {top_dept[1]} responses ({dept_pct}% of total).'})

    # Session understanding insight
    if session_understanding_counts:
        sig_count = session_understanding_counts.get('Yes, significantly', 0)
        sig_pct = round(sig_count / total_count * 100) if total_count else 0
        not_really = session_understanding_counts.get('Not really', 0)
        if sig_pct >= 60:
            ai_insights.append({'type': 'success', 'icon': '🎓', 'text': f'High impact: {sig_pct}% of students said the session significantly helped their understanding of industry trends.'})
        elif not_really > 0:
            ai_insights.append({'type': 'warning', 'icon': '📉', 'text': f'Engagement gap: {not_really} student{"s" if not_really != 1 else ""} reported the session did not help their understanding.'})

    # Sentiment Insight
    total_sentiment = sum(sentiment_counts.values())
    if total_sentiment > 0:
        pos_pct = round((sentiment_counts['POSITIVE'] / total_sentiment) * 100)
        neg_pct = round((sentiment_counts['NEGATIVE'] / total_sentiment) * 100)
        if pos_pct >= 70:
            ai_insights.append({'type': 'success', 'icon': '✨', 'text': f'Strong positive reception: {pos_pct}% positive sentiment in written feedback.'})
        elif pos_pct < 40:
            ai_insights.append({'type': 'warning', 'icon': '⚠️', 'text': f'Mixed reception: Only {pos_pct}% positive sentiment — {neg_pct}% negative detected in detailed feedback.'})

    # Top requested future topic
    if sorted_fut_keywords:
        top_topic = sorted_fut_keywords[0][0]
        count = sorted_fut_keywords[0][1]
        if count > 1:
            # Show top 3 if available
            top3 = [k for k, _ in sorted_fut_keywords[:3]]
            top3_str = ', '.join(f'"{t.title()}"' for t in top3)
            ai_insights.append({'type': 'info', 'icon': '💡', 'text': f'Most requested future topics: {top3_str}.'})

    # Actionability Insight
    act_count = actionable_stats['actionable']
    non_act = actionable_stats['non_actionable']
    if act_count > 0:
        act_pct = round(act_count / (act_count + non_act) * 100) if (act_count + non_act) > 0 else 0
        ai_insights.append({'type': 'warning', 'icon': '🛡️', 'text': f'{act_count} actionable suggestions ({act_pct}% of responses) — these contain specific, implementable improvement ideas.'})

    # Speaker insights
    if speaker_list:
        top_speaker = speaker_list[0]
        ts_rating = top_speaker.get('ratings', {}).get('Rating', 0)
        if ts_rating >= 4.5:
            ai_insights.append({'type': 'success', 'icon': '🌟', 'text': f'Top rated speaker: {top_speaker["name"]} — avg rating {ts_rating}/5 from {top_speaker["count"]} responses.'})
        # Most sessions speaker
        if len(speaker_list) > 1:
            ai_insights.append({'type': 'trend', 'icon': '🎤', 'text': f'{len(speaker_list)} unique speakers featured. Most sessions: {top_speaker["name"]} ({top_speaker["count"]} responses).'})

    # Avg rating insight
    if total_rating_count > 0:
        avg_r = round(total_rating_sum / total_rating_count, 2)
        if avg_r >= 4.5:
            ai_insights.append({'type': 'success', 'icon': '⭐', 'text': f'Excellent overall rating: {avg_r}/5 average across {total_rating_count} rated responses.'})
        elif avg_r < 3.5:
            ai_insights.append({'type': 'warning', 'icon': '📊', 'text': f'Below-average rating: {avg_r}/5 — consider reviewing session format and content delivery.'})

    # Dept with best avg rating
    if dept_avg_ratings and len(dept_avg_ratings) > 1:
        best_dept = sorted(dept_avg_ratings.items(), key=lambda x: x[1], reverse=True)[0]
        ai_insights.append({'type': 'info', 'icon': '🏆', 'text': f'Highest rated department: {best_dept[0]} with avg {best_dept[1]}/5.'})

    # Participation Insight (suggestion categories)
    if category_counts:
        top_cat = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[0]
        if top_cat[1] > total_count * 0.2:
            ai_insights.append({'type': 'info', 'icon': '🚀', 'text': f'Dominant feedback theme: "{top_cat[0]}" — mentioned in {top_cat[1]} suggestions.'})

    # Topic Cluster Insight (BERTopic)
    if topic_freq:
        top_topic_cluster = sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)[0]
        ai_insights.append({'type': 'info', 'icon': '🧠', 'text': f'AI Topic Cluster: "{top_topic_cluster[0].title()}" is the dominant theme across {top_topic_cluster[1]} responses.'})

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
        'sub':   'All-time records'
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

    # Session impact KPI
    sig_count = session_understanding_counts.get('Yes, significantly', 0)
    sig_pct = round(sig_count / total_count * 100) if total_count > 0 else 0
    formatted_kpis.append({
        'label': 'High Impact Sessions',
        'value': f"{sig_pct}%",
        'sub':   'Said "Yes, significantly"'
    })

    # Unique speakers KPI
    formatted_kpis.append({
        'label': 'Unique Speakers',
        'value': str(len(speaker_tracker)),
        'sub':   'Alumni featured'
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
