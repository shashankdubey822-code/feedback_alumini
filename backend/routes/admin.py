"""
Admin Routes - Handle authentication and data management
"""

from flask import Blueprint, request, jsonify, current_app
import os
import sqlite3
import pandas as pd
import re
from datetime import datetime
from ..utils.logger import get_logger, log_endpoint_access

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Simple hardcoded password for now (could be an environment variable)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')


def _canonicalize_column(name):
    """Convert an input column to a canonical key for flexible matching."""
    return re.sub(r'[^a-z0-9]+', '', str(name).strip().lower())


def _normalize_dataframe_for_dashboard(df, source='csv_upload'):
    """Map raw CSV columns into dashboard_data schema columns."""
    column_map = {
        'timestamp': 'timestamp_original',
        'timestamporiginal': 'timestamp_original',
        'timestampnormalized': 'timestamp_normalized',
        'nameofstudent': 'name_of_student',
        'namenormalized': 'name_normalized',
        'department': 'department_original',
        'departmentoriginal': 'department_original',
        'departmentcleaned': 'department_cleaned',
        'rollno': 'roll_no_original',
        'rollnooriginal': 'roll_no_original',
        'rollnocleaned': 'roll_no_cleaned',
        'dateofthelecture': 'date_of_lecture',
        'alumnispeakername': 'alumni_speaker_name',
        'didthesessionhelpyougainabetterunderstandingofindustrytrendsorcareerpaths': 'session_help_understanding',
        'sessionhelpunderstanding': 'session_help_understanding',
        'whataspectofthesessiondidyoufindmostvaluable': 'aspect_most_valuable',
        'aspectmostvaluable': 'aspect_most_valuable',
        'howwouldyouratethesessionoverall1poor2fair3good4verygood5excellent': 'session_rating',
        'sessionrating': 'session_rating',
        'sessiontechnicalclarity': 'session_technical_clarity',
        'whatimprovementsorsuggestionswouldyourecommendforfuturealumnisessions': 'improvements_suggestions',
        'improvementssuggestions': 'improvements_suggestions',
        'anyspecifictopicsorareasyoudlikefuturealumnispeakerstocover': 'future_topics',
        'futuretopics': 'future_topics',
        'formsource': 'form_source',
        'dataqualityscore': 'data_quality_score',
        'isduplicateflag': 'is_duplicate_flag',
        'recordstatus': 'record_status',
        'cleanedat': 'cleaned_at',
    }

    rename_map = {}
    for col in df.columns:
        canonical_key = _canonicalize_column(col)
        target_col = column_map.get(canonical_key)
        if target_col:
            rename_map[col] = target_col

    normalized_df = df.rename(columns=rename_map).copy()

    if 'timestamp_original' in normalized_df.columns and 'timestamp_normalized' not in normalized_df.columns:
        parsed = pd.to_datetime(normalized_df['timestamp_original'], errors='coerce')
        normalized_df['timestamp_normalized'] = parsed.dt.strftime('%Y-%m-%d %H:%M:%S')

    if 'name_of_student' in normalized_df.columns and 'name_normalized' not in normalized_df.columns:
        normalized_df['name_normalized'] = normalized_df['name_of_student'].astype(str).str.strip()

    if 'department_original' in normalized_df.columns and 'department_cleaned' not in normalized_df.columns:
        normalized_df['department_cleaned'] = normalized_df['department_original'].astype(str).str.strip()

    if 'roll_no_original' in normalized_df.columns:
        normalized_df['roll_no_original'] = normalized_df['roll_no_original'].astype(str).str.upper().str.strip()
        if 'roll_no_cleaned' not in normalized_df.columns:
            normalized_df['roll_no_cleaned'] = normalized_df['roll_no_original']

    if 'session_rating' in normalized_df.columns:
        normalized_df['session_rating'] = pd.to_numeric(normalized_df['session_rating'], errors='coerce')

    if 'session_technical_clarity' in normalized_df.columns:
        normalized_df['session_technical_clarity'] = pd.to_numeric(normalized_df['session_technical_clarity'], errors='coerce')

    if 'data_quality_score' in normalized_df.columns:
        normalized_df['data_quality_score'] = pd.to_numeric(normalized_df['data_quality_score'], errors='coerce')

    if 'is_duplicate_flag' in normalized_df.columns:
        normalized_df['is_duplicate_flag'] = pd.to_numeric(normalized_df['is_duplicate_flag'], errors='coerce').fillna(0).astype(int)

    if 'form_source' not in normalized_df.columns:
        normalized_df['form_source'] = source

    if 'record_status' not in normalized_df.columns:
        normalized_df['record_status'] = 'active'

    if 'cleaned_at' not in normalized_df.columns:
        normalized_df['cleaned_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    return normalized_df


def _append_dashboard_rows(df, db_path, source='csv_upload'):
    """Normalize and append rows with strict dashboard_data schema alignment."""
    normalized_df = _normalize_dataframe_for_dashboard(df, source=source)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(dashboard_data)')
        table_columns = [row[1] for row in cursor.fetchall()]
        insert_columns = [col for col in table_columns if col != 'id']

        for col in insert_columns:
            if col not in normalized_df.columns:
                normalized_df[col] = None

        aligned_df = normalized_df[insert_columns]
        aligned_df.to_sql('dashboard_data', conn, if_exists='append', index=False)
    finally:
        conn.close()

@admin_bp.route('/login', methods=['POST'])
@log_endpoint_access
def login():
    """Admin login endpoint"""
    data = request.get_json()
    password = data.get('password')
    
    if password == ADMIN_PASSWORD:
        # In a real app, generate a proper JWT
        return jsonify({'success': True, 'token': 'mock-admin-token'}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid password'}), 401

@admin_bp.route('/upload_csv', methods=['POST'])
@log_endpoint_access
def upload_csv():
    """Handle CSV file upload and database insertion"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
            df = pd.read_csv(file)

            _append_dashboard_rows(df, db_path, source='file_upload')

            return jsonify({'success': True, 'message': f'Uploaded {len(df)} rows'}), 200
        except Exception as e:
            logger.error(f"Upload error: {str(e)}")
            return jsonify({'error': str(e)}), 500

@admin_bp.route('/fetch_google_link', methods=['POST'])
@log_endpoint_access
def fetch_google_link():
    """Fetch data from a public Google Sheets CSV export link"""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        # Convert Google Sheets URL to CSV export URL if needed
        if 'docs.google.com/spreadsheets' in url and '/export' not in url:
            if '/edit' in url:
                url = url.split('/edit')[0] + '/export?format=csv'
            else:
                url = url.rstrip('/') + '/export?format=csv'

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        df = pd.read_csv(url)

        _append_dashboard_rows(df, db_path, source='google_sheet')

        return jsonify({'success': True, 'message': f'Fetched {len(df)} rows from Google Sheets'}), 200
    except Exception as e:
        logger.error(f"Google fetch error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/create-event', methods=['POST'])
@log_endpoint_access
def create_event():
    """Create a new feedback event in the database"""
    try:
        data = request.get_json() or {}
        speaker_name = data.get('speaker_name')
        venue_date = data.get('venue_date')
        
        if not speaker_name or not venue_date:
            return jsonify({'success': False, 'error': 'Speaker name and venue date are required'}), 400
            
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO events (speaker_name, venue_date, status) VALUES (?, ?, ?)",
            (speaker_name, venue_date, 'pending')
        )
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'event_id': event_id,
            'speaker_name': speaker_name,
            'venue_date': venue_date
        }), 200
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/events', methods=['GET'])
def get_events():
    """Get list of real feedback events from the database"""
    try:
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT e.*, 
                   (SELECT COUNT(*) FROM dashboard_data d WHERE d.alumni_speaker_name = e.speaker_name) as responses
            FROM events e 
            ORDER BY e.created_at DESC
        """)
        rows = cursor.fetchall()
        
        events = []
        for row in rows:
            events.append(dict(row))
            
        conn.close()
        return jsonify({'success': True, 'events': events}), 200
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/generate-form', methods=['POST'])
def generate_form():
    """Call Google Apps Script to generate a form and save it to the database"""
    try:
        import urllib.request
        import json
        data = request.get_json() or {}
        event_id = data.get('event_id')
        
        if not event_id:
            return jsonify({'success': False, 'error': 'event_id is required'}), 400
            
        # Get event details from DB
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        
        if not event:
            conn.close()
            return jsonify({'success': False, 'error': 'Event not found'}), 404
            
        apps_script_url = os.getenv('APPS_SCRIPT_URL')
        if not apps_script_url:
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'APPS_SCRIPT_URL is not configured'
            }), 400
            
        secret = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
        webhook_url = request.host_url.rstrip('/') + '/api/v1/webhook/forms/submit'
        
        payload = {
            'secret': secret,
            'action': 'create_form',
            'speaker_name': event['speaker_name'],
            'venue_date': event['venue_date'],
            'webhook_url': webhook_url,
            'event_id': event_id
        }
        
        payload_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            apps_script_url, 
            data=payload_bytes, 
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                
                if response_data.get('success'):
                    # The Google Apps Script nests the result inside a 'data' key
                    result = response_data.get('data', {})
                    form_url = result.get('form_url')
                    form_id = result.get('form_id')
                    form_edit_url = result.get('form_edit_url')
                    
                    if not form_url:
                        logger.error(f"Google Script succeeded but returned no URL. Full response: {response_data}")
                        return jsonify({'success': False, 'error': 'Google Script did not return a Form URL'}), 500

                    cursor.execute(
                        "UPDATE events SET form_url = ?, form_id = ?, form_edit_url = ?, status = ? WHERE id = ?",
                        (form_url, form_id, form_edit_url, 'active', event_id)
                    )
                    conn.commit()
                    conn.close()
                    
                    # Also return the nested data directly to the frontend
                    return jsonify({'success': True, 'form_url': form_url, 'form_id': form_id}), 200
                else:
                    conn.close()
                    err_msg = response_data.get('error', 'Google Script error')
                    return jsonify({'success': False, 'error': err_msg}), 400
        except Exception as api_err:
            conn.close()
            return jsonify({'success': False, 'error': f"Connection error: {str(api_err)}"}), 500
            
    except Exception as e:
        logger.error(f"Error generating form: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
