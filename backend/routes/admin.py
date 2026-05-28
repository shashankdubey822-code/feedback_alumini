"""
Enhanced Admin Routes with Comprehensive Error Handling & Atomic Transactions
Fixed all critical issues: orphaned events, webhook validation, duplicate detection
"""

from flask import Blueprint, request, jsonify, current_app
import os
import sqlite3
import pandas as pd
import re
import urllib.request
import json
import io
import requests
from datetime import datetime

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

from ..utils.logger import get_logger, log_endpoint_access

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Admin password from environment
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
    from backend.utils.db_helper import get_db_connection
    normalized_df = _normalize_dataframe_for_dashboard(df, source=source)

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(dashboard_data)')
        table_columns = [row[1] for row in cursor.fetchall()]
        insert_columns = [col for col in table_columns if col != 'id']

        for col in insert_columns:
            if col not in normalized_df.columns:
                if col == 'dl_processed':
                    normalized_df[col] = 0
                else:
                    normalized_df[col] = None

        aligned_df = normalized_df[insert_columns]
        aligned_df.to_sql('dashboard_data', conn, if_exists='append', index=False)
    finally:
        conn.close()


def _validate_google_apps_script_url(url):
    """Validate that the Google Apps Script URL is properly formatted"""
    if not url:
        return False, "APPS_SCRIPT_URL is not configured"
    
    if not url.startswith('https://script.google.com/macros/s/'):
        return False, "APPS_SCRIPT_URL must be a valid Google Apps Script web app URL"
    
    if not url.endswith('/exec'):
        return False, "APPS_SCRIPT_URL must end with /exec"
    
    return True, None


def _call_google_apps_script(url, payload, timeout=90):
    """
    Centralized function to call Google Apps Script with retry logic and comprehensive logging
    
    Args:
        url: Google Apps Script URL
        payload: Request payload dict
        timeout: Request timeout in seconds (default 90)
    
    Returns:
        tuple: (success: bool, data: dict, error_message: str)
    """
    max_retries = 3
    retry_delay = [2, 5, 10]  # Progressive retry delays
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling Google Apps Script (attempt {attempt + 1}/{max_retries}): {payload.get('action', 'unknown')}")
            logger.debug(f"Full payload: {json.dumps(payload, indent=2)}")
            
            payload_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_text = response.read().decode('utf-8')
                logger.debug(f"Google Apps Script raw response: {response_text}")
                
                response_data = json.loads(response_text)
                
                if response_data.get('success'):
                    logger.info(f"Google Apps Script call successful: {response_data.get('message', 'OK')}")
                    return True, response_data.get('data', {}), None
                else:
                    # Capture both 'message' and more detailed 'data' (if provided by script)
                    message = response_data.get('message', 'Unknown error from Google Script')
                    details = response_data.get('data', '')
                    error_msg = f"{message}: {details}" if details else message
                    
                    logger.warning(f"Google Apps Script returned success=false: {error_msg}")
                    return False, None, error_msg
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else 'No response body'
            logger.error(f"HTTP error calling Google Script (attempt {attempt + 1}): {e.code} - {error_body}")
            
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay[attempt])
                continue
            else:
                return False, None, f"HTTP {e.code}: {error_body}"
                
        except urllib.error.URLError as e:
            logger.error(f"URL error calling Google Script (attempt {attempt + 1}): {str(e.reason)}")
            
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay[attempt])
                continue
            else:
                return False, None, f"Connection failed: {str(e.reason)}"
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Google Script: {str(e)}")
            return False, None, "Invalid response format from Google Script"
            
        except Exception as e:
            logger.error(f"Unexpected error calling Google Script: {str(e)}", exc_info=True)
            return False, None, f"Unexpected error: {str(e)}"
    
    return False, None, "Max retries exceeded"


@admin_bp.route('/login', methods=['POST'])
@log_endpoint_access
def login():
    """Admin login endpoint with enhanced validation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        password = data.get('password')
        if not password:
            return jsonify({'success': False, 'message': 'Password required'}), 400
        
        if password == ADMIN_PASSWORD:
            logger.info(f"Successful admin login from {request.remote_addr}")
            return jsonify({'success': True, 'token': 'mock-admin-token'}), 200
        else:
            logger.warning(f"Failed admin login attempt from {request.remote_addr}")
            return jsonify({'success': False, 'message': 'Invalid password'}), 401
    except Exception as e:
        logger.error(f"Error in admin login: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Server error'}), 500

@admin_bp.route('/upload_csv', methods=['POST'])
@log_endpoint_access
def upload_csv():
    """Handle CSV file upload with comprehensive validation"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        df = pd.read_csv(file)
        
        if len(df) == 0:
            return jsonify({'error': 'CSV file is empty'}), 400

        _append_dashboard_rows(df, db_path, source='file_upload')
        
        logger.info(f"Successfully uploaded {len(df)} rows from CSV")
        return jsonify({'success': True, 'message': f'Uploaded {len(df)} rows'}), 200
        
    except pd.errors.EmptyDataError:
        return jsonify({'error': 'CSV file is empty or invalid'}), 400
    except pd.errors.ParserError as e:
        logger.error(f"CSV parse error: {str(e)}")
        return jsonify({'error': f'Invalid CSV format: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/fetch_google_link', methods=['POST'])
@log_endpoint_access
def fetch_google_link():
    """Fetch data from a public Google Sheets CSV export link with validation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        url = data.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Convert Google Sheets URL to CSV export URL if needed
        if 'docs.google.com/spreadsheets' in url and '/export' not in url:
            if '/edit' in url:
                url = url.split('/edit')[0] + '/export?format=csv'
            else:
                url = url.rstrip('/') + '/export?format=csv'

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        
        # Authenticated fetch using credentials.json or Environment Variable if available
        creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
        creds_env = os.getenv('GOOGLE_CREDENTIALS')
        
        if GOOGLE_AUTH_AVAILABLE and (os.path.exists(creds_path) or creds_env):
            logger.info("Using Service Account credentials for Google Sheet fetch.")
            
            # Use Environment Variable (Hugging Face Secret) if available, otherwise use local file
            if creds_env:
                import json
                creds_dict = json.loads(creds_env)
                creds = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
            else:
                creds = service_account.Credentials.from_service_account_file(
                    creds_path, scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
                
            auth_req = Request()
            creds.refresh(auth_req)
            headers = {'Authorization': f'Bearer {creds.token}'}
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            df = pd.read_csv(io.StringIO(res.text))
        else:
            logger.info("No credentials.json found. Attempting unauthenticated fetch.")
            df = pd.read_csv(url)
        
        if len(df) == 0:
            return jsonify({'error': 'Google Sheet is empty'}), 400

        _append_dashboard_rows(df, db_path, source='google_sheet')
        
        logger.info(f"Successfully fetched {len(df)} rows from Google Sheets")
        return jsonify({'success': True, 'message': f'Fetched {len(df)} rows from Google Sheets'}), 200
        
    except pd.errors.EmptyDataError:
        return jsonify({'error': 'Google Sheet is empty'}), 400
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error fetching Google Sheet: {e.code}")
        return jsonify({'error': f'Could not access Google Sheet (HTTP {e.code})'}), 400
    except requests.exceptions.RequestException as e:
        logger.error(f"Requests error fetching Google Sheet: {str(e)}")
        status_code = e.response.status_code if e.response is not None else 400
        return jsonify({'error': f'Could not access Google Sheet (HTTP {status_code}). Please verify your service account access.'}), 400
    except Exception as e:
        logger.error(f"Google fetch error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/verify-template', methods=['POST'])
@log_endpoint_access
def verify_template():
    """
    Verify if a Google Slide Template ID exists and is accessible
    via the Google Apps Script.
    """
    try:
        data = request.get_json() or {}
        template_id = data.get('template_id', '').strip()
        
        if not template_id:
            return jsonify({'success': False, 'error': 'No template_id provided'}), 400
            
        script_url = current_app.config.get('APPS_SCRIPT_URL')
        secret_key = current_app.config.get('APPS_SCRIPT_SECRET', 'datalens2026')
        
        if not script_url:
            return jsonify({'success': False, 'error': 'Apps Script URL not configured'}), 500
            
        # Send verification payload to GAS
        payload = {
            "action": "verify_template",
            "secret": secret_key,
            "template_id": template_id
        }
        
        logger.info(f"Verifying template ID: {template_id}")
        response = requests.post(script_url, json=payload, timeout=10)
        response_data = response.json()
        
        # If response is successful, the template exists and is accessible
        if response.status_code == 200 and response_data.get('success'):
            return jsonify({
                'success': True,
                'data': response_data.get('data', {})
            })
        else:
            # Pass along the specific error from GAS
            error_msg = response_data.get('error') or response_data.get('message') or "Template verification failed"
            return jsonify({
                'success': False,
                'error': error_msg
            }), 403
            
    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to Apps Script for verification")
        return jsonify({'success': False, 'error': 'Google Apps Script timeout'}), 504
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/create-event-and-form', methods=['POST'])
@log_endpoint_access
def create_event_and_form():
    """
    ATOMIC OPERATION: Create event and generate Google Form in a single transaction
    This fixes the orphaned event problem where event is created but form generation fails
    """
    conn = None
    event_id = None
    
    try:
        data = request.get_json() or {}
        speaker_name = data.get('speaker_name', '').strip()
        venue_date = data.get('venue_date', '').strip()
        template_id = data.get('template_id', '').strip() or None
        send_certificates = int(data.get('send_certificates', 0))
        
        # Validation
        if not speaker_name or not venue_date:
            return jsonify({
                'success': False,
                'error': 'Speaker name and venue date are required'
            }), 400
        
        # Validate Google Apps Script configuration
        apps_script_url = current_app.config.get('APPS_SCRIPT_URL') or os.getenv('APPS_SCRIPT_URL')
        is_valid, error_msg = _validate_google_apps_script_url(apps_script_url)
        if not is_valid:
            logger.error(f"Google Apps Script validation failed: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Step 1: Create event in database (but don't commit yet)
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        from backend.utils.db_helper import get_db_connection
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO events (speaker_name, venue_date, status, template_id, send_certificates) VALUES (?, ?, ?, ?, ?)",
            (speaker_name, venue_date, 'creating_form', template_id, send_certificates)
        )
        event_id = cursor.lastrowid
        
        logger.info(f"Created event #{event_id} (not committed yet)")
        
        # Step 2: Call Google Apps Script to create form
        secret = current_app.config.get('APPS_SCRIPT_SECRET') or os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
        base_url = os.environ.get('PUBLIC_URL') or request.host_url
        webhook_url = base_url.rstrip('/') + '/api/v1/webhook/forms/submit'
        
        payload = {
            'secret': secret,
            'action': 'create_form',
            'speaker_name': speaker_name,
            'venue_date': venue_date,
            'webhook_url': webhook_url,
            'event_id': event_id,
            'send_certificates': send_certificates
        }
        
        success, result, error = _call_google_apps_script(apps_script_url, payload, timeout=90)
        
        if not success:
            # Form creation failed - rollback the database transaction
            logger.error(f"Google Form creation failed for event #{event_id}: {error}")
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Failed to create Google Form: {error}'
            }), 500
        
        # Step 3: Validate response data
        form_url = result.get('form_url')
        form_id = result.get('form_id')
        form_edit_url = result.get('form_edit_url')
        
        if not form_url or not form_id:
            logger.error(f"Google Script succeeded but returned incomplete data. Full response: {result}")
            conn.rollback()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Google Script returned incomplete form data'
            }), 500
        
        # Step 4: Update event with form details and commit everything atomically
        cursor.execute(
            "UPDATE events SET form_url = ?, form_id = ?, form_edit_url = ?, status = ? WHERE id = ?",
            (form_url, form_id, form_edit_url, 'active', event_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully created event #{event_id} with Google Form {form_id}")
        
        return jsonify({
            'success': True,
            'event_id': event_id,
            'form_url': form_url,
            'form_id': form_id,
            'form_edit_url': form_edit_url,
            'speaker_name': speaker_name,
            'venue_date': venue_date
        }), 200
        
    except Exception as e:
        # Any error - rollback and cleanup
        logger.error(f"Error in atomic event creation: {str(e)}", exc_info=True)
        
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        
        return jsonify({'success': False, 'error': str(e)}), 500


# Legacy endpoint (kept for backward compatibility but marked as deprecated)
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


@admin_bp.route('/certificate-jobs', methods=['GET'])
def get_certificate_jobs():
    """Retrieve list of certificate generation jobs from the queue with event details"""
    try:
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT j.*, e.speaker_name 
            FROM job_queue j
            LEFT JOIN events e ON j.event_id = e.id
            ORDER BY j.created_at DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        
        jobs = [dict(row) for row in rows]
        conn.close()
        return jsonify({'success': True, 'jobs': jobs}), 200
    except Exception as e:
        logger.error(f"Error fetching certificate jobs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/speaker-names', methods=['GET'])
@log_endpoint_access
def get_speaker_names():
    """Distinct alumni speaker names from dashboard_data for form autocomplete."""
    try:
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT TRIM(alumni_speaker_name) AS n
            FROM dashboard_data
            WHERE alumni_speaker_name IS NOT NULL AND TRIM(alumni_speaker_name) != ''
            ORDER BY n COLLATE NOCASE
            """
        )
        names = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return jsonify({'success': True, 'names': names}), 200
    except Exception as e:
        logger.error(f"Error fetching speaker names: {str(e)}")
        return jsonify({'success': False, 'error': str(e), 'names': []}), 500


@admin_bp.route('/close-form', methods=['POST'])
@log_endpoint_access
def close_form():
    """Explicitly close a form and mark it as expired."""
    try:
        data = request.json
        form_id = data.get('form_id')
        event_id = data.get('event_id')

        if not form_id and not event_id:
            return jsonify({'error': 'form_id or event_id is required'}), 400

        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        from backend.utils.db_helper import get_db_connection
        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        # If only event_id given, look up the real form_id from DB
        if not form_id and event_id:
            cursor.execute("SELECT form_id FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                form_id = row[0]

        # Update status — match by form_id if available, else fallback to event id
        if form_id:
            cursor.execute("UPDATE events SET status = 'closed' WHERE form_id = ?", (form_id,))
        else:
            cursor.execute("UPDATE events SET status = 'closed' WHERE id = ?", (event_id,))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Form not found'}), 404

        conn.commit()
        conn.close()

        # Call Google Apps Script to strictly lock the Google Form
        if form_id:
            apps_script_url = os.getenv('APPS_SCRIPT_URL')
            if apps_script_url:
                secret = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
                payload = {
                    'secret': secret,
                    'action': 'close_form',
                    'form_id': form_id
                }
                success, _, err = _call_google_apps_script(apps_script_url, payload)
                if not success:
                    logger.warning(f"Google Script Form Closure failed for {form_id}: {err}")

        logger.info(f"Form '{form_id or event_id}' successfully closed by admin.")
        return jsonify({'message': 'Form closed successfully (Google Form locked)', 'status': 'closed'})

    except Exception as e:
        logger.error(f"Error closing form: {str(e)}")
        return jsonify({'error': str(e)}), 500


def get_form_status(form_id, db_path):
    """Helper function to get the status of a form."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM events WHERE form_id = ?", (form_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        return None
    except Exception as e:
        logger.error(f"Error getting form status: {str(e)}")
        if conn:
            conn.close()
        return None

@admin_bp.route('/generate-form', methods=['POST'])
@log_endpoint_access
def generate_form():
    """
    DEPRECATED: Use /create-event-and-form instead
    Legacy endpoint - generates form for existing event with enhanced error handling
    """
    conn = None
    
    try:
        data = request.get_json() or {}
        event_id = data.get('event_id')
        
        if not event_id:
            return jsonify({'success': False, 'error': 'event_id is required'}), 400
        
        # Validate Google Apps Script URL
        apps_script_url = current_app.config.get('APPS_SCRIPT_URL') or os.getenv('APPS_SCRIPT_URL')
        is_valid, error_msg = _validate_google_apps_script_url(apps_script_url)
        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Get event details from DB
        from backend.utils.db_helper import get_db_connection
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = get_db_connection(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        
        if not event:
            conn.close()
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        
        # Call Google Apps Script
        secret = current_app.config.get('APPS_SCRIPT_SECRET') or os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
        base_url = os.environ.get('PUBLIC_URL') or request.host_url
        webhook_url = base_url.rstrip('/') + '/api/v1/webhook/forms/submit'
        
        payload = {
            'secret': secret,
            'action': 'create_form',
            'speaker_name': event['speaker_name'],
            'venue_date': event['venue_date'],
            'webhook_url': webhook_url,
            'event_id': event_id
        }
        
        success, result, error = _call_google_apps_script(apps_script_url, payload, timeout=90)
        
        if not success:
            conn.close()
            return jsonify({'success': False, 'error': error}), 500
        
        form_url = result.get('form_url')
        form_id = result.get('form_id')
        form_edit_url = result.get('form_edit_url')
        
        if not form_url:
            logger.error(f"Google Script succeeded but returned no URL. Full response: {result}")
            conn.close()
            return jsonify({'success': False, 'error': 'Google Script did not return a Form URL'}), 500
        
        cursor.execute(
            "UPDATE events SET form_url = ?, form_id = ?, form_edit_url = ?, status = ? WHERE id = ?",
            (form_url, form_id, form_edit_url, 'active', event_id)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Generated form for event #{event_id}")
        return jsonify({'success': True, 'form_url': form_url, 'form_id': form_id}), 200
        
    except Exception as e:
        logger.error(f"Error generating form: {str(e)}", exc_info=True)
        
        if conn:
            try:
                conn.close()
            except:
                pass
        
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/sync-responses', methods=['POST'])
@log_endpoint_access
def sync_responses():
    """
    Manually trigger a sync for a specific event's responses from Google Forms
    Enhanced with better duplicate detection and error handling
    """
    conn = None
    
    try:
        data = request.get_json() or {}
        event_id = data.get('event_id')
        
        if not event_id:
            return jsonify({'success': False, 'error': 'event_id is required'}), 400
        
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get event details
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        
        if not event or not event['form_id']:
            conn.close()
            return jsonify({'success': False, 'error': 'Form not yet generated for this event'}), 400
        
        # Validate Google Apps Script URL
        apps_script_url = current_app.config.get('APPS_SCRIPT_URL') or os.getenv('APPS_SCRIPT_URL')
        is_valid, error_msg = _validate_google_apps_script_url(apps_script_url)
        if not is_valid:
            conn.close()
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Call Google Apps Script to get responses
        secret = current_app.config.get('APPS_SCRIPT_SECRET') or os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
        payload = {
            'secret': secret,
            'action': 'get_responses',
            'form_id': event['form_id']
        }
        
        success, responses, error = _call_google_apps_script(apps_script_url, payload, timeout=120)
        
        if not success:
            conn.close()
            return jsonify({'success': False, 'error': error}), 500
        
        # Process responses with improved duplicate detection
        count = 0
        skipped = 0
        
        for resp in responses:
            timestamp = resp.get('timestamp', '')
            name = (resp.get('name_of_student') or '').strip().lower()
            roll_no = (resp.get('roll_no_original') or '').strip().upper()
            
            # Enhanced duplicate check: form_id + roll_no + venue_date
            # This prevents issues with name variations and timezone issues
            cursor.execute("""
                SELECT id FROM dashboard_data 
                WHERE form_source = ? 
                AND roll_no_original = ? 
                AND date_of_lecture = ?
                LIMIT 1
            """, (event['form_id'], roll_no, event['venue_date']))
            
            if cursor.fetchone():
                skipped += 1
                continue
            
            # Timestamp normalization for sync
            try:
                # Handle ISO format or other standard formats from Google Script
                ts_norm = pd.to_datetime(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            except:
                ts_norm = timestamp

            # Department cleaning
            raw_dept = resp.get('department_original', '')
            dept_cleaned = str(raw_dept).strip()

            try:
                cursor.execute('''
                    INSERT INTO dashboard_data (
                        timestamp_original, timestamp_normalized, name_of_student, 
                        department_original, department_cleaned, roll_no_original, roll_no_cleaned,
                        date_of_lecture, alumni_speaker_name, session_help_understanding,
                        session_rating, session_technical_clarity, aspect_most_valuable,
                        improvements_suggestions, future_topics, form_source, record_status,
                        cleaned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    ts_norm,
                    resp.get('name_of_student', ''),
                    raw_dept,
                    dept_cleaned,
                    roll_no,  # Original (uppercased)
                    roll_no,  # Cleaned (same as original)
                    event['venue_date'],
                    event['speaker_name'],
                    resp.get('session_help_understanding', ''),
                    resp.get('session_rating'),
                    resp.get('session_technical_clarity'),
                    resp.get('aspect_most_valuable', ''),
                    resp.get('improvements_suggestions', ''),
                    resp.get('future_topics', ''),
                    event['form_id'],
                    'SYNCED',
                    datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                ))
                
                # Check if certificates should be generated
                if event['send_certificates'] == 1 and event['template_id']:
                    student_name = resp.get('name_of_student', 'Unknown').strip()
                    student_email = resp.get('student_email', '').strip()
                    
                    # Avoid duplicate jobs for same student & event
                    cursor.execute("""
                        SELECT id FROM job_queue 
                        WHERE event_id = ? AND roll_no = ?
                        LIMIT 1
                    """, (event_id, roll_no))
                    
                    if not cursor.fetchone():
                        job_status = 'pending'
                        job_error = None
                        if not student_email:
                            job_status = 'failed'
                            job_error = 'No email address provided in form submission'
                            
                        cursor.execute("""
                            INSERT INTO job_queue (student_name, student_email, roll_no, department, event_id, status, error_message)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (student_name, student_email, roll_no, raw_dept, event_id, job_status, job_error))
                        
                count += 1
            except sqlite3.IntegrityError as e:
                logger.warning(f"Integrity error inserting response: {str(e)}")
                skipped += 1
                continue
        
        conn.commit()
        conn.close()
        
        logger.info(f"Synced {count} new responses for event #{event_id}, skipped {skipped} duplicates")
        
        return jsonify({
            'success': True,
            'synced': count,
            'total': len(responses),
            'skipped': skipped
        }), 200
        
    except Exception as e:
        logger.error(f"Error syncing responses: {str(e)}", exc_info=True)
        
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/config/validate', methods=['GET'])
@log_endpoint_access
def validate_config():
    """
    Validate that all required configuration is present and correct
    This helps debug configuration issues
    """
    try:
        checks = {}
        
        # Check APPS_SCRIPT_URL
        apps_script_url = os.getenv('APPS_SCRIPT_URL')
        is_valid, error_msg = _validate_google_apps_script_url(apps_script_url)
        checks['apps_script_url'] = {
            'configured': bool(apps_script_url),
            'valid': is_valid,
            'value': apps_script_url[:50] + '...' if apps_script_url and len(apps_script_url) > 50 else apps_script_url,
            'error': error_msg
        }
        
        # Check APPS_SCRIPT_SECRET
        secret = os.getenv('APPS_SCRIPT_SECRET')
        checks['apps_script_secret'] = {
            'configured': bool(secret),
            'is_default': secret == 'datalens2026',
            'length': len(secret) if secret else 0
        }
        
        # Check WEBHOOK_SECRET
        webhook_secret = current_app.config.get('WEBHOOK_SECRET')
        checks['webhook_secret'] = {
            'configured': bool(webhook_secret),
            'length': len(webhook_secret) if webhook_secret else 0
        }
        
        # Check database
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        checks['database'] = {
            'path': db_path,
            'exists': os.path.exists(db_path)
        }
        
        # Overall status
        all_valid = (
            checks['apps_script_url']['valid'] and
            checks['apps_script_secret']['configured'] and
            checks['webhook_secret']['configured'] and
            checks['database']['exists']
        )
        
        return jsonify({
            'success': True,
            'all_valid': all_valid,
            'checks': checks
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating config: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
