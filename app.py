"""
DataLens — Advanced Python Analytics Backend
Flask API with AI-powered garbage detection, smart sentiment analysis,
bigram keyword extraction, and auto-generated insights.
"""

import os
import re
import json
import math
import numpy as np
from collections import Counter
from datetime import datetime
from io import StringIO
import sqlite3
import requests

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from rapidfuzz import fuzz, process
import nltk
from textblob import TextBlob

# ── NLTK Setup ──────────────────────────────────────────────────────
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

from nltk.corpus import stopwords

STOP_WORDS = set(stopwords.words('english'))
STOP_WORDS.update([
    'na', 'n/a', 'nil', 'none', 'nothing', 'no', 'nope', 'ok', 'yes',
    '-', '.', 'the', 'and', 'was', 'for', 'all', 'more', 'would',
    'about', 'also', 'make', 'like', 'good', 'really', 'everything',
    'every', 'lot', 'much', 'get', 'got', 'well', 'can', 'one',
])

# ── AI: Non-Answer Detection Patterns ───────────────────────────────
# These regex patterns catch ALL variants of "no feedback" responses
NON_ANSWER_PATTERNS = [
    r'^n[/\\]?a\.?$',                          # NA, N/A, N\A
    r'^na\.?$',                                 # na
    r'^no\.?$',                                 # No, No.
    r'^nil\.?$',                                # Nil
    r'^none\.?$',                               # None
    r'^nope\.?$',                               # Nope
    r'^ok\.?$',                                 # Ok
    r'^okay\.?$',                               # Okay
    r'^-+$',                                    # -, --, ---
    r'^\.$',                                    # .
    r'^nothing\.?$',                            # Nothing
    r'^nothing\s+(all\s+)?perfect\.?$',         # Nothing all perfect
    r'^all\s+perfect\.?$',                      # All perfect
    r'^no\s+suggestion[s]?\.?$',               # No suggestions
    r'^no\s+comment[s]?\.?$',                  # No comments
    r'^not\s+any\.?$',                         # Not any
    r'^good\.?$',                               # Good (not real feedback)
    r'^all\s+good\.?$',                        # All good
    r'^fine\.?$',                               # Fine
    r'^no\s+improvement[s]?\.?$',              # No improvements
]

NON_ANSWER_COMPILED = [re.compile(p, re.IGNORECASE) for p in NON_ANSWER_PATTERNS]

# ── AI: Column Intent Detection ─────────────────────────────────────
# Keywords that indicate a column contains subjective feedback/opinions
OPINION_KEYWORDS = [
    'suggest', 'improve', 'recommend', 'feedback', 'comment', 'opinion',
    'valuable', 'help', 'gain', 'topic', 'aspect', 'rate', 'rating',
    'experience', 'thought', 'review', 'what',
]

# Keywords that indicate a column is just an identifier (NOT opinion)
IDENTIFIER_KEYWORDS = [
    'name', 'roll', 'id', 'number', 'date', 'time', 'timestamp',
    'department', 'dept', 'school', 'speaker', 'alumni', 'instructor',
]


def is_non_answer(text):
    """AI-powered non-answer detection using pattern matching + heuristics."""
    if not text or not isinstance(text, str):
        return True
    text = text.strip()
    if len(text) == 0:
        return True

    # Pattern matching
    for pattern in NON_ANSWER_COMPILED:
        if pattern.match(text):
            return True

    # Heuristic: very short + neutral sentiment = likely non-answer
    if len(text.split()) <= 2 and len(text) <= 10:
        try:
            polarity = TextBlob(text).sentiment.polarity
            # If it's very short and emotionally flat, it's a non-answer
            if abs(polarity) < 0.05 and text.lower() not in ('bad', 'poor', 'great', 'excellent', 'worst', 'best'):
                return True
        except Exception:
            pass

    return False


def is_opinion_column(col_name):
    """Detect if a column contains subjective opinions vs just identifiers."""
    name_lower = col_name.lower()

    # Check if it's an identifier column (NOT opinion)
    for kw in IDENTIFIER_KEYWORDS:
        if kw in name_lower:
            # Exception: "did the session help" contains 'name' but IS opinion
            if any(ok in name_lower for ok in OPINION_KEYWORDS):
                return True
            return False

    # Check if it's an opinion column
    for kw in OPINION_KEYWORDS:
        if kw in name_lower:
            return True

    # Default: if column name is long (question-like), it's likely opinion
    if len(col_name) > 30:
        return True

    return False


def classify_axis_labels(col_name, col_type, chart_context='distribution'):
    """AI-powered axis label generation based on column name and type."""
    name_lower = col_name.lower()

    # Y-axis (count axis)
    if chart_context == 'distribution':
        y_label = 'Number of Responses'
        if 'student' in name_lower or 'name' in name_lower:
            y_label = 'Number of Students'
        elif 'speaker' in name_lower or 'alumni' in name_lower:
            y_label = 'Number of Sessions'
    elif chart_context == 'average':
        y_label = 'Average Rating'
    elif chart_context == 'trend':
        y_label = 'Count'
    elif chart_context == 'sentiment':
        y_label = 'Sentiment Score'
    else:
        y_label = 'Count'

    # X-axis (category axis)
    x_label = col_name
    if len(col_name) > 35:
        # Shorten long question-style column names
        if 'rate' in name_lower:
            x_label = 'Rating'
        elif 'suggest' in name_lower or 'improve' in name_lower:
            x_label = 'Suggestion'
        elif 'department' in name_lower:
            x_label = 'Department'
        elif 'speaker' in name_lower:
            x_label = 'Speaker Name'
        elif 'topic' in name_lower:
            x_label = 'Topic'
        elif 'valuable' in name_lower or 'aspect' in name_lower:
            x_label = 'Valuable Aspect'
        elif 'help' in name_lower or 'understanding' in name_lower:
            x_label = 'Helpfulness'
        else:
            x_label = col_name[:35]

    return x_label, y_label


# ── Flask App ───────────────────────────────────────────────────────
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_PATH = 'dashboard.db'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

current_data = {
    'df': None,
    'original_df': None,
    'columns': [],
    'column_types': {},
    'filename': '',
    'department_map': {},
}


@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)


# ════════════════════════════════════════════════════════════════════
#  DATABASE HELPERS
# ════════════════════════════════════════════════════════════════════

def load_data_from_db():
    try:
        if not os.path.exists(DB_PATH):
            return False
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql('SELECT * FROM dashboard_data', conn)
        conn.close()
        
        if df.empty:
            return False
            
        # Optional: any necessary string cleanup
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].astype(str).str.strip()
            
        current_data['original_df'] = df.copy()
        current_data['df'] = df.copy()
        current_data['columns'] = list(df.columns)
        current_data['filename'] = 'Database Record'
        current_data['column_types'] = detect_column_types(df)

        current_data['department_map'] = {}
        for col in df.columns:
            if current_data['column_types'].get(col) == 'categorical':
                if is_department_like(col, df[col]):
                    mapping = fuzzy_normalize(df[col].tolist())
                    current_data['department_map'][col] = mapping
                    df[col + ' (Normalized)'] = df[col].map(mapping).fillna(df[col])

        current_data['df'] = df
        return True
    except Exception as e:
        print("DB Load Error:", e)
        return False


def save_data_to_db(df):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('dashboard_data', conn, if_exists='replace', index=False)
    conn.close()


# ════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════

@app.route('/api/data', methods=['GET'])
def get_data():
    if current_data['df'] is None:
        loaded = load_data_from_db()
        if not loaded:
            return jsonify({'error': 'No data available. Admin needs to upload data.'}), 404
            
    analytics = build_analytics(current_data['df'], current_data['column_types'],
                                 current_data['department_map'],
                                 current_data['columns'])
    return jsonify(analytics)

# ════════════════════════════════════════════════════════════════════
#  ADMIN API
# ════════════════════════════════════════════════════════════════════

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json or {}
    pwd = data.get('password', '')
    if pwd == ADMIN_PASSWORD:
        return jsonify({'success': True, 'token': 'admin_stateless_token'})
    return jsonify({'error': 'Invalid password', 'success': False}), 401


@app.route('/api/admin/upload_csv', methods=['POST'])
def upload_csv():
    token = request.headers.get('Authorization', '')
    if token != 'Bearer admin_stateless_token':
        return jsonify({'error': 'Unauthorized'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    try:
        content = file.read().decode('utf-8')
        df = pd.read_csv(StringIO(content))
        df.columns = [c.strip() for c in df.columns]
        df = df.dropna(how='all')
        df = df.fillna('')
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].astype(str).str.strip()

        save_data_to_db(df)
        load_data_from_db()

        return jsonify({'success': True, 'message': 'Data successfully uploaded to db'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/fetch_google_link', methods=['POST'])
def fetch_google_link():
    token = request.headers.get('Authorization', '')
    if token != 'Bearer admin_stateless_token':
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json or {}
    url = data.get('url', '')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
        
    # Convert standard Google Sheets URL to export CSV URL
    if '/edit' in url:
        url = url.split('/edit')[0] + '/export?format=csv'
        
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        content = resp.content.decode('utf-8')
        
        df = pd.read_csv(StringIO(content))
        df.columns = [c.strip() for c in df.columns]
        df = df.dropna(how='all')
        df = df.fillna('')
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].astype(str).str.strip()
            
        save_data_to_db(df)
        load_data_from_db()
        
        return jsonify({'success': True, 'message': 'Data loaded from Google Sheets'})
    except Exception as e:
        return jsonify({'error': f'Failed to fetch or parse from Google link: {str(e)}'}), 500


# ════════════════════════════════════════════════════════════════════
#  FILTER
# ════════════════════════════════════════════════════════════════════
@app.route('/api/filter', methods=['POST'])
def filter_data():
    if current_data['df'] is None:
        return jsonify({'error': 'No data loaded'}), 400

    try:
        filters = request.json.get('filters', {})
        search = request.json.get('search', '').lower().strip()

        df = current_data['original_df'].copy()

        for col, mapping in current_data['department_map'].items():
            df[col + ' (Normalized)'] = df[col].map(mapping).fillna(df[col])

        if search:
            mask = df.apply(
                lambda row: any(search in str(v).lower() for v in row), axis=1
            )
            df = df[mask]

        for col, filter_val in filters.items():
            if not filter_val or col not in df.columns:
                continue
            ftype = current_data['column_types'].get(col, 'text')

            if ftype == 'categorical':
                df = df[df[col] == filter_val]
            elif ftype == 'text':
                df = df[df[col].str.lower().str.contains(filter_val.lower(), na=False)]
            elif ftype == 'numeric':
                df = apply_numeric_filter(df, col, filter_val)
            elif ftype == 'date':
                df = apply_date_filter(df, col, filter_val)

        current_data['df'] = df

        analytics = build_analytics(df, current_data['column_types'],
                                     current_data['department_map'],
                                     current_data['columns'])
        return jsonify(analytics)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════════════════════════════
#  COLUMN TYPE DETECTION
# ════════════════════════════════════════════════════════════════════
def detect_column_types(df):
    types = {}
    for col in df.columns:
        values = df[col].astype(str).str.strip()
        values = values[values.ne('') & values.ne('NA') & values.ne('N/A')
                        & values.ne('na') & values.ne('-') & values.ne('.')]

        if len(values) == 0:
            types[col] = 'text'
            continue

        date_count = values.apply(is_date_value).sum()
        if date_count / len(values) > 0.5:
            types[col] = 'date'
            continue

        numeric_count = values.apply(lambda v: is_numeric(v)).sum()
        if numeric_count / len(values) > 0.5:
            types[col] = 'numeric'
            continue

        unique_vals = values.str.lower().nunique()
        if unique_vals <= 30 or unique_vals / len(values) < 0.4:
            types[col] = 'categorical'
            continue

        types[col] = 'text'

    return types


def is_date_value(val):
    if not val or len(str(val)) < 5:
        return False
    patterns = [
        r'^\d{1,2}/\d{1,2}/\d{2,4}',
        r'^\d{4}-\d{1,2}-\d{1,2}',
        r'^\d{1,2}-\d{1,2}-\d{2,4}',
        r'^\d{1,2}\.\d{1,2}\.\d{2,4}',
    ]
    return any(re.match(p, str(val).strip()) for p in patterns)


def is_numeric(val):
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def is_department_like(col_name, series):
    name_lower = col_name.lower()
    dept_keywords = ['department', 'dept', 'school', 'faculty', 'program', 'course', 'branch']
    if any(kw in name_lower for kw in dept_keywords):
        return True
    unique = series[series.ne('')].str.lower().nunique()
    total = len(series[series.ne('')])
    if total > 0 and 5 < unique < total * 0.8:
        return True
    return False


# ════════════════════════════════════════════════════════════════════
#  FUZZY NORMALIZATION
# ════════════════════════════════════════════════════════════════════
def fuzzy_normalize(values, threshold=65):
    clean = [v.strip() for v in values if v and v.strip() and
             v.strip() not in ('', 'NA', 'N/A', '-', '.')]
    if not clean:
        return {}

    freq = Counter(clean)
    sorted_vals = sorted(freq.keys(), key=lambda x: (-freq[x], x))
    mapping = {}
    canonical_groups = []

    for val in sorted_vals:
        if val in mapping:
            continue
        matched = False
        for canonical, members in canonical_groups:
            score = fuzz.token_sort_ratio(val.lower(), canonical.lower())
            if score >= threshold:
                mapping[val] = canonical
                members.append(val)
                matched = True
                break
        if not matched:
            mapping[val] = val
            canonical_groups.append((val, [val]))

    final_mapping = {}
    for canonical, members in canonical_groups:
        best = max(members, key=lambda m: (freq.get(m, 0), len(m)))
        for m in members:
            final_mapping[m] = best

    return final_mapping


# ════════════════════════════════════════════════════════════════════
#  ANALYTICS BUILDER
# ════════════════════════════════════════════════════════════════════
def sanitize_for_json(obj):
    """Recursively convert numpy types to Python native for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def build_analytics(df, column_types, dept_map, original_columns):
    total_rows = len(df)
    total_original = len(current_data['original_df'])

    result = {
        'meta': {
            'totalRows': total_rows,
            'totalOriginal': total_original,
            'totalColumns': len(original_columns),
            'columns': original_columns,
            'columnTypes': column_types,
            'filename': current_data['filename'],
        },
        'kpis': build_kpis(df, column_types, original_columns),
        'charts': build_chart_data(df, column_types, dept_map, original_columns),
        'sentiment': build_sentiment(df, column_types, original_columns),
        'keywords': build_keywords(df, column_types, original_columns),
        'timeTrends': build_time_trends(df, column_types, original_columns),
        'speakerStats': build_speaker_stats(df, column_types, original_columns),
        'tableData': build_table_data(df, original_columns),
        'filters': build_filter_options(column_types, original_columns),
        'aiInsights': build_ai_insights(df, column_types, dept_map, original_columns),
    }

    return sanitize_for_json(result)


# ── KPIs ────────────────────────────────────────────────────────────
def build_kpis(df, column_types, columns):
    kpis = []

    kpis.append({
        'label': 'Total Records',
        'value': len(df),
        'sub': f'out of {len(current_data["original_df"])} total',
        'icon': 'records',
    })

    num_cols = sum(1 for t in column_types.values() if t == 'numeric')
    kpis.append({
        'label': 'Columns',
        'value': len(columns),
        'sub': f'{num_cols} numeric',
        'icon': 'columns',
    })

    for col in columns:
        ctype = column_types.get(col, 'text')
        values = df[col].astype(str).str.strip()
        values = values[values.ne('') & values.ne('NA') & values.ne('N/A')
                        & values.ne('-') & values.ne('.') & values.ne('na')]

        if ctype == 'numeric':
            nums = pd.to_numeric(values, errors='coerce').dropna()
            if len(nums) > 0:
                avg = round(nums.mean(), 2)
                kpis.append({
                    'label': f'Avg {col[:25]}',
                    'value': avg,
                    'sub': f'Min: {nums.min()} | Max: {nums.max()} | Median: {round(nums.median(), 1)}',
                    'icon': 'numeric',
                })
        elif ctype == 'date':
            dates = values.apply(parse_date_safe).dropna()
            if len(dates) > 0:
                earliest = dates.min().strftime('%Y-%m-%d')
                latest = dates.max().strftime('%Y-%m-%d')
                kpis.append({
                    'label': col[:25],
                    'value': f'{len(dates)} dates',
                    'sub': f'{earliest} → {latest}',
                    'icon': 'date',
                })
        elif ctype == 'categorical':
            unique_count = values.nunique()
            top_val = values.mode().iloc[0] if len(values) > 0 else ''
            kpis.append({
                'label': col[:25],
                'value': f'{unique_count} unique',
                'sub': f'Top: {top_val[:22]}',
                'icon': 'category',
            })

    return kpis


# ── Charts (with AI garbage filtering + axis labels) ────────────────
def build_chart_data(df, column_types, dept_map, columns):
    charts = []
    chart_count = 0
    max_charts = 8

    for col in columns:
        if chart_count >= max_charts:
            break
        ctype = column_types.get(col, 'text')

        if ctype == 'date' or ctype == 'text':
            continue

        if ctype == 'categorical':
            use_col = col + ' (Normalized)' if col in dept_map and col + ' (Normalized)' in df.columns else col
            values = df[use_col].astype(str).str.strip()

            # ★ AI GARBAGE FILTER: Remove non-answers before charting
            values = values[values.apply(lambda v: not is_non_answer(v))]

            freq = values.value_counts().head(15)
            if len(freq) < 2:
                continue

            total_unique = values.nunique()
            unique_ratio = total_unique / len(values) if len(values) > 0 else 1
            avg_freq = len(values) / total_unique if total_unique > 0 else 0
            if unique_ratio > 0.6 and avg_freq < 1.5:
                continue

            chart_type = 'doughnut' if len(freq) <= 5 else 'bar'

            # ★ SMART AXIS LABELS
            x_label, y_label = classify_axis_labels(col, ctype, 'distribution')

            charts.append({
                'title': f'{col[:40]} — Distribution',
                'type': chart_type,
                'column': col,
                'columnType': 'categorical',
                'labels': freq.index.tolist(),
                'data': freq.values.tolist(),
                'normalized': col in dept_map,
                'xLabel': x_label,
                'yLabel': y_label,
            })
            chart_count += 1

        elif ctype == 'numeric':
            nums = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce').dropna()
            if len(nums) < 2:
                continue

            min_val = nums.min()
            max_val = nums.max()
            if min_val == max_val:
                continue

            all_int = (nums == nums.astype(int)).all()
            rng = max_val - min_val

            if all_int and rng <= 10:
                bin_labels = [str(i) for i in range(int(min_val), int(max_val) + 1)]
                bins_data = [int((nums == i).sum()) for i in range(int(min_val), int(max_val) + 1)]
            else:
                bin_count = min(int(rng + 1), 10)
                bin_size = rng / bin_count
                bin_labels = [f'{(min_val + i*bin_size):.1f}–{(min_val + (i+1)*bin_size):.1f}'
                              for i in range(bin_count)]
                bins_data = [0] * bin_count
                for n in nums:
                    idx = min(int((n - min_val) / bin_size), bin_count - 1)
                    bins_data[idx] += 1

            x_label, y_label = classify_axis_labels(col, ctype, 'distribution')

            # For numeric bins, also store bin boundaries for exact click filtering
            if all_int and rng <= 10:
                bin_boundaries = [{'exact': i} for i in range(int(min_val), int(max_val) + 1)]
            else:
                bin_boundaries = [
                    {'min': min_val + i * bin_size, 'max': min_val + (i + 1) * bin_size, 'isLast': i == bin_count - 1}
                    for i in range(bin_count)
                ]

            charts.append({
                'title': f'{col[:40]} — Distribution',
                'type': 'bar',
                'column': col,
                'columnType': 'numeric',
                'binBoundaries': bin_boundaries,
                'labels': bin_labels,
                'data': bins_data,
                'normalized': False,
                'xLabel': x_label,
                'yLabel': y_label,
            })
            chart_count += 1

    return charts


# ── Sentiment (AI-filtered: ONLY opinion columns) ──────────────────
def build_sentiment(df, column_types, columns):
    results = []

    for col in columns:
        ctype = column_types.get(col, 'text')
        if ctype not in ('text', 'categorical'):
            continue

        # ★ AI: SKIP non-opinion columns (names, departments, roll numbers, dates)
        if not is_opinion_column(col):
            continue

        values = df[col].astype(str).str.strip()
        # ★ AI: Filter out non-answers BEFORE sentiment analysis
        values = values[values.apply(lambda v: not is_non_answer(v))]
        values = values[values.str.len() > 3]

        if len(values) < 3:
            continue

        sentiments = []
        for text in values:
            try:
                blob = TextBlob(str(text))
                sentiments.append({
                    'polarity': round(blob.sentiment.polarity, 3),
                    'subjectivity': round(blob.sentiment.subjectivity, 3),
                })
            except Exception:
                continue

        if not sentiments:
            continue

        polarities = [s['polarity'] for s in sentiments]
        subjectivities = [s['subjectivity'] for s in sentiments]

        positive = sum(1 for p in polarities if p > 0.1)
        neutral = sum(1 for p in polarities if -0.1 <= p <= 0.1)
        negative = sum(1 for p in polarities if p < -0.1)

        # Count how many non-answers were filtered
        original_count = len(df[col].astype(str).str.strip())
        non_answer_count = original_count - len(values) - df[col].astype(str).str.strip().eq('').sum()

        results.append({
            'column': col,
            'avgPolarity': round(sum(polarities) / len(polarities), 3),
            'avgSubjectivity': round(sum(subjectivities) / len(subjectivities), 3),
            'positive': positive,
            'neutral': neutral,
            'negative': negative,
            'total': len(sentiments),
            'nonAnswers': max(0, non_answer_count),
            'distribution': {
                'labels': ['Positive', 'Neutral', 'Negative'],
                'data': [positive, neutral, negative],
            },
        })

    return results


# ── Keywords (bigram/trigram extraction) ────────────────────────────
def build_keywords(df, column_types, columns):
    results = []

    for col in columns:
        ctype = column_types.get(col, 'text')
        if ctype not in ('text', 'categorical'):
            continue

        # ★ Only extract keywords from opinion/feedback columns
        if not is_opinion_column(col):
            continue

        values = df[col].astype(str).str.strip()
        # ★ AI: Filter out non-answers
        values = values[values.apply(lambda v: not is_non_answer(v))]
        values = values[values.str.len() > 3]

        if len(values) < 3:
            continue

        # Single words
        all_words = []
        # ★ Bigrams (2-word phrases)
        all_bigrams = []

        for text in values:
            words = re.findall(r'[a-zA-Z]{3,}', text.lower())
            words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
            all_words.extend(words)

            # Generate bigrams
            if len(words) >= 2:
                for i in range(len(words) - 1):
                    bigram = f'{words[i]} {words[i+1]}'
                    all_bigrams.append(bigram)

        if not all_words:
            continue

        word_freq = Counter(all_words)
        bigram_freq = Counter(all_bigrams)

        # Combine: top single words + top bigrams that appear ≥2 times
        top_words = [{'text': w, 'count': c, 'type': 'word'}
                     for w, c in word_freq.most_common(20)]

        top_bigrams = [{'text': b, 'count': c, 'type': 'bigram'}
                       for b, c in bigram_freq.most_common(10) if c >= 2]

        combined = sorted(top_bigrams + top_words,
                         key=lambda x: x['count'], reverse=True)[:25]

        if len(combined) < 2:
            continue

        results.append({
            'column': col,
            'words': combined,
        })

    return results





# ── Time Trends (with axis labels) ──────────────────────────────────
def build_time_trends(df, column_types, columns):
    results = []
    date_cols = [c for c in columns if column_types.get(c) == 'date']
    numeric_cols = [c for c in columns if column_types.get(c) == 'numeric']

    for date_col in date_cols:
        dates = df[date_col].astype(str).apply(parse_date_safe)
        valid = dates.dropna()

        if len(valid) < 3:
            continue

        temp_df = pd.DataFrame({'date': valid})
        temp_df['month'] = temp_df['date'].dt.to_period('M')
        monthly = temp_df.groupby('month').size().reset_index(name='count')
        monthly['month_str'] = monthly['month'].astype(str)

        trend = {
            'dateColumn': date_col,
            'responseCount': {
                'labels': monthly['month_str'].tolist(),
                'data': monthly['count'].tolist(),
                'xLabel': 'Month',
                'yLabel': 'Number of Responses',
            },
            'ratingTrends': [],
        }

        for num_col in numeric_cols:
            nums = pd.to_numeric(df[num_col].astype(str).str.strip(), errors='coerce')
            temp2 = pd.DataFrame({'date': dates, 'value': nums}).dropna()
            temp2['month'] = temp2['date'].dt.to_period('M')
            monthly_avg = temp2.groupby('month')['value'].mean().reset_index()
            monthly_avg['month_str'] = monthly_avg['month'].astype(str)

            if len(monthly_avg) >= 2:
                trend['ratingTrends'].append({
                    'column': num_col,
                    'labels': monthly_avg['month_str'].tolist(),
                    'data': [round(v, 2) for v in monthly_avg['value'].tolist()],
                    'xLabel': 'Month',
                    'yLabel': f'Average {num_col[:25]}',
                })

        results.append(trend)

    return results


# ── Speaker Stats ───────────────────────────────────────────────────
def build_speaker_stats(df, column_types, columns):
    results = []

    speaker_cols = [c for c in columns if column_types.get(c) == 'categorical'
                    and any(kw in c.lower() for kw in ['speaker', 'alumni', 'instructor',
                                                         'teacher', 'presenter', 'mentor'])]

    numeric_cols = [c for c in columns if column_types.get(c) == 'numeric']

    # Only use opinion columns for sentiment
    text_cols = [c for c in columns if column_types.get(c) in ('text', 'categorical')
                 and is_opinion_column(c) and c not in speaker_cols]

    for speaker_col in speaker_cols:
        speakers = df[speaker_col].astype(str).str.strip()
        unique_speakers = speakers[speakers.ne('') & speakers.ne('NA')].unique()

        speaker_data = []
        for speaker in unique_speakers:
            mask = speakers == speaker
            speaker_rows = df[mask]
            entry = {
                'name': speaker,
                'count': int(mask.sum()),
                'ratings': {},
                'sentiment': 0,
            }

            for num_col in numeric_cols:
                nums = pd.to_numeric(speaker_rows[num_col].astype(str).str.strip(),
                                     errors='coerce').dropna()
                if len(nums) > 0:
                    entry['ratings'][num_col] = round(nums.mean(), 2)

            all_text = []
            for text_col in text_cols:
                texts = speaker_rows[text_col].astype(str).str.strip()
                # ★ AI: Filter non-answers from speaker sentiment
                texts = texts[texts.apply(lambda v: not is_non_answer(v))]
                texts = texts[texts.str.len() > 3]
                all_text.extend(texts.tolist())

            if all_text:
                polarities = []
                for t in all_text:
                    try:
                        polarities.append(TextBlob(t).sentiment.polarity)
                    except Exception:
                        pass
                if polarities:
                    entry['sentiment'] = round(sum(polarities) / len(polarities), 3)

            speaker_data.append(entry)

        speaker_data.sort(key=lambda x: x['count'], reverse=True)

        results.append({
            'column': speaker_col,
            'speakers': speaker_data,
        })

    return results


# ── AI Insights (auto-generated summary) ───────────────────────────
def build_ai_insights(df, column_types, dept_map, columns):
    """Generate AI-powered text insights from the data."""
    insights = []
    total = len(df)

    if total == 0:
        return insights

    # 1. Response overview
    insights.append({
        'type': 'overview',
        'icon': '📊',
        'text': f'Analyzed {total} responses across {len(columns)} data columns.',
    })

    # 2. Rating insight
    numeric_cols = [c for c in columns if column_types.get(c) == 'numeric']
    for num_col in numeric_cols:
        nums = pd.to_numeric(df[num_col].astype(str).str.strip(), errors='coerce').dropna()
        if len(nums) > 0:
            avg = round(nums.mean(), 2)
            median = round(nums.median(), 1)
            max_val = nums.max()
            min_val = nums.min()

            # Count ratings
            if nums.max() <= 5:  # Rating scale
                high = (nums >= 4).sum()
                low = (nums <= 2).sum()
                pct_high = round(high / len(nums) * 100, 0)
                sentiment_text = 'overwhelmingly positive' if pct_high >= 80 else 'mostly positive' if pct_high >= 60 else 'mixed' if pct_high >= 40 else 'concerning'

                insights.append({
                    'type': 'rating',
                    'icon': '⭐',
                    'text': f'Average rating is {avg}/5 (median {median}). {int(pct_high)}% gave 4+ stars — feedback is {sentiment_text}. {int(low)} response(s) rated ≤2.',
                })

    # 3. Top department
    for col in columns:
        if column_types.get(col) == 'categorical' and is_department_like(col, df[col]):
            use_col = col + ' (Normalized)' if col in dept_map else col
            if use_col in df.columns:
                top_dept = df[use_col][df[use_col].ne('')].value_counts()
                if len(top_dept) >= 2:
                    insights.append({
                        'type': 'department',
                        'icon': '🏫',
                        'text': f'{top_dept.index[0]} had the most responses ({top_dept.iloc[0]}), followed by {top_dept.index[1]} ({top_dept.iloc[1]}). {len(top_dept)} departments participated.',
                    })
                break

    # 4. Speaker insights
    speaker_cols = [c for c in columns if column_types.get(c) == 'categorical'
                    and any(kw in c.lower() for kw in ['speaker', 'alumni'])]
    for speaker_col in speaker_cols:
        speakers = df[speaker_col].astype(str).str.strip()
        speakers = speakers[speakers.ne('') & speakers.ne('NA')]
        top_speakers = speakers.value_counts()

        if len(top_speakers) >= 2 and len(numeric_cols) > 0:
            # Find highest rated speaker
            num_col = numeric_cols[0]
            nums = pd.to_numeric(df[num_col].astype(str).str.strip(), errors='coerce')
            temp = pd.DataFrame({'speaker': df[speaker_col], 'rating': nums}).dropna()
            temp = temp[temp['speaker'].ne('') & temp['speaker'].ne('NA')]
            speaker_avg = temp.groupby('speaker')['rating'].mean().sort_values(ascending=False)

            if len(speaker_avg) >= 1:
                best = speaker_avg.index[0]
                best_rating = round(speaker_avg.iloc[0], 2)
                worst = speaker_avg.index[-1]
                worst_rating = round(speaker_avg.iloc[-1], 2)

                insights.append({
                    'type': 'speaker',
                    'icon': '🎤',
                    'text': f'{best} received the highest avg rating ({best_rating}). {worst} received the lowest ({worst_rating}). {len(top_speakers)} speakers participated.',
                })
        break

    # 5. Feedback quality (non-answer detection)
    for col in columns:
        if is_opinion_column(col) and column_types.get(col) in ('text', 'categorical'):
            vals = df[col].astype(str).str.strip()
            vals = vals[vals.ne('')]
            total_responses = len(vals)
            non_answers = vals.apply(is_non_answer).sum()
            real_feedback = total_responses - non_answers

            if total_responses > 5 and non_answers > 0:
                pct_real = round(real_feedback / total_responses * 100, 0)
                insights.append({
                    'type': 'feedback_quality',
                    'icon': '🧹',
                    'text': f'For "{col[:40]}": {int(non_answers)} of {total_responses} responses were non-answers (No, NA, Nil, etc.). {int(pct_real)}% gave real feedback.',
                })

    # 6. Time span
    for col in columns:
        if column_types.get(col) == 'date':
            dates = df[col].astype(str).apply(parse_date_safe).dropna()
            if len(dates) >= 2:
                earliest = dates.min()
                latest = dates.max()
                span = (latest - earliest).days
                months = span // 30
                insights.append({
                    'type': 'timespan',
                    'icon': '📅',
                    'text': f'Data spans {span} days (~{months} months), from {earliest.strftime("%b %d, %Y")} to {latest.strftime("%b %d, %Y")}.',
                })
            break

    return insights


# ── Filter Options ──────────────────────────────────────────────────
def build_filter_options(column_types, columns):
    df = current_data['original_df']
    filters = []

    for col in columns:
        ctype = column_types.get(col, 'text')
        f = {'column': col, 'type': ctype}

        if ctype == 'categorical':
            values = df[col].astype(str).str.strip()
            values = values[values.ne('') & values.ne('NA')]
            freq = values.value_counts().head(50)
            f['options'] = [{'value': v, 'count': int(c)} for v, c in freq.items()]
        elif ctype == 'date':
            dates = df[col].astype(str).apply(parse_date_safe).dropna()
            if len(dates) > 0:
                unique_dates = sorted(dates.dt.strftime('%Y-%m-%d').unique())
                f['options'] = unique_dates

        filters.append(f)

    return filters


# ── Table Data ──────────────────────────────────────────────────────
def build_table_data(df, columns):
    rows = []
    for _, row in df.head(500).iterrows():
        r = {}
        for col in columns:
            r[col] = str(row.get(col, ''))
        rows.append(r)
    return rows


# ── Date Parsing ────────────────────────────────────────────────────
def parse_date_safe(val):
    if not val or not isinstance(val, str) or len(val.strip()) < 5:
        return None
    val = val.strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})', val)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', val)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ── Numeric Filter ──────────────────────────────────────────────────
def apply_numeric_filter(df, col, filter_val):
    nums = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce')
    m = re.match(r'^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$', filter_val)
    if m:
        return df[(nums >= float(m.group(1))) & (nums <= float(m.group(2)))]
    m = re.match(r'^([><=!]+)\s*(\d+(?:\.\d+)?)$', filter_val)
    if m:
        op, val = m.group(1), float(m.group(2))
        ops = {'>': nums > val, '>=': nums >= val, '<': nums < val,
               '<=': nums <= val, '=': nums == val, '==': nums == val, '!=': nums != val}
        if op in ops:
            return df[ops[op]]
    try:
        return df[nums == float(filter_val)]
    except ValueError:
        return df


def apply_date_filter(df, col, filter_val):
    if isinstance(filter_val, dict):
        dates = df[col].astype(str).apply(parse_date_safe)
        if filter_val.get('from'):
            from_date = parse_date_safe(filter_val['from'])
            if from_date:
                df = df[dates >= from_date]
        if filter_val.get('to'):
            to_date = parse_date_safe(filter_val['to'])
            if to_date:
                dates = df[col].astype(str).apply(parse_date_safe)
                df = df[dates <= to_date]
    return df


# ════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('\n  ✦ DataLens Server running at http://0.0.0.0:7860\n')
    app.run(debug=False, host='0.0.0.0', port=7860)
