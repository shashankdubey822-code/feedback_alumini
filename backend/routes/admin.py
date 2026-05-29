"""
admin.py — Admin Routes. Native Supabase PostgreSQL via supabase_db.py.
Tables: events, feedback_responses, feedback_analysis, certificate_jobs
"""

import os
import io
import re
import json
import urllib.request
import urllib.error
import time
import requests
import pandas as pd
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from backend.utils.logger import get_logger, log_endpoint_access
from backend.utils.supabase_db import get_db, execute_all, execute_one, execute_returning

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GRequest
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

logger = get_logger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

_transformer_model = None

def get_transformer_model():
    global _transformer_model
    if _transformer_model is None:
        from sentence_transformers import SentenceTransformer
        _transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _transformer_model


def _canonicalize(name):
    return re.sub(r'[^a-z0-9]+', '', str(name).strip().lower())


# ---------------------------------------------------------------------------
# CSV / Google Sheets normalization → feedback_responses
# ---------------------------------------------------------------------------
_COL_MAP = {
    'timestamp': 'timestamp_display',
    'timestamporiginal': 'timestamp_display',
    'emailaddress': 'student_email',
    'email': 'student_email',
    'studentemail': 'student_email',
    'nameofstudent': 'name_of_student',
    'department': 'department',
    'departmentoriginal': 'department',
    'departmentcleaned': 'department',
    'rollno': 'roll_no',
    'rollnooriginal': 'roll_no',
    'rollnocleaned': 'roll_no',
    'dateofthelecture': 'date_of_lecture',
    'dateoflecture': 'date_of_lecture',
    'alumnispeakername': 'alumni_speaker_name',
    'speakername': 'alumni_speaker_name',
    'nameofthespeaker': 'alumni_speaker_name',
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
    'isduplicateflag': 'is_duplicate',
    'recordstatus': 'record_status',
}

RESPONSE_COLS = [
    'timestamp_display', 'name_of_student', 'roll_no', 'department',
    'student_email', 'date_of_lecture', 'alumni_speaker_name',
    'session_help_understanding', 'session_rating', 'session_technical_clarity',
    'aspect_most_valuable', 'improvements_suggestions', 'future_topics',
    'form_source', 'data_quality_score', 'is_duplicate', 'record_status',
]


def _normalize_df(df, source='csv_upload') -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        target = _COL_MAP.get(_canonicalize(col))
        if target:
            rename[col] = target
    df = df.rename(columns=rename).copy()

    if 'session_rating' in df.columns:
        df['session_rating'] = pd.to_numeric(df['session_rating'], errors='coerce')
    if 'session_technical_clarity' in df.columns:
        df['session_technical_clarity'] = pd.to_numeric(df['session_technical_clarity'], errors='coerce')
    if 'data_quality_score' in df.columns:
        df['data_quality_score'] = pd.to_numeric(df['data_quality_score'], errors='coerce')
    if 'is_duplicate' in df.columns:
        df['is_duplicate'] = pd.to_numeric(df['is_duplicate'], errors='coerce').fillna(0).astype(bool)
    if 'roll_no' in df.columns:
        df['roll_no'] = df['roll_no'].astype(str).str.upper().str.strip()
    if 'form_source' not in df.columns:
        df['form_source'] = source
    else:
        df['form_source'] = df['form_source'].fillna(source).replace('', source)
    if 'record_status' not in df.columns:
        df['record_status'] = 'active'
    else:
        df['record_status'] = df['record_status'].fillna('active').replace('', 'active')
        
    # Attempt to parse submitted_at from timestamp_display
    if 'timestamp_display' in df.columns:
        df['submitted_at'] = pd.to_datetime(df['timestamp_display'], errors='coerce')
        # Fill NaT with current UTC time
        df['submitted_at'] = df['submitted_at'].fillna(pd.Timestamp.utcnow())
    else:
        df['submitted_at'] = pd.Timestamp.utcnow()

    return df


def _insert_df_rows(df: pd.DataFrame, source: str = 'csv_upload') -> int:
    df = _normalize_df(df, source)
    # ── Orchestrator Injection ──
    from backend.agents.data_orchestrator import DataOrchestratorSupervisor
    orchestrator = DataOrchestratorSupervisor()
    
    # Convert DataFrame to list of dicts for the agent payload
    rows_payload = df.to_dict('records')
    
    # Execute the Data Orchestrator pipeline
    result = orchestrator.execute({'rows': rows_payload})
    processed = result.get('processed_rows', [])
    
    # Count successful syncs (no error key present in the row state)
    inserted = sum(1 for row_state in processed if 'response_id' in row_state and 'error' not in row_state)
    
    # Update in-memory dataframe cache
    from backend.services.analytics_engine import analytics_engine
    analytics_engine.refresh_data()
    
    return inserted


def _safe_int(val):
    try:
        v = int(float(val))
        return v if 1 <= v <= 5 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Google Apps Script helpers
# ---------------------------------------------------------------------------
def _validate_gas_url(url):
    if not url:
        return False, "APPS_SCRIPT_URL not configured"
    if not url.startswith('https://script.google.com/macros/s/'):
        return False, "APPS_SCRIPT_URL must be a valid Google Apps Script URL"
    if not url.endswith('/exec'):
        return False, "APPS_SCRIPT_URL must end with /exec"
    return True, None


def _call_gas(url, payload, timeout=90):
    for attempt, delay in enumerate([2, 5, 10]):
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data,
                                         headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if result.get('success'):
                    return True, result.get('data', {}), None
                msg = result.get('message', 'Unknown error')
                details = result.get('data', '')
                return False, None, f"{msg}: {details}" if details else msg
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            err = f"HTTP {e.code}: {body}"
        except urllib.error.URLError as e:
            err = f"Connection failed: {e.reason}"
        except json.JSONDecodeError:
            return False, None, "Invalid JSON from Apps Script"
        except Exception as e:
            return False, None, str(e)
        if attempt < 2:
            time.sleep(delay)
    return False, None, "Max retries exceeded"


# ===========================================================================
# ROUTES
# ===========================================================================

@admin_bp.route('/login', methods=['POST'])
@log_endpoint_access
def login():
    data = request.get_json() or {}
    if data.get('password') == ADMIN_PASSWORD:
        return jsonify({'success': True, 'token': 'mock-admin-token'}), 200
    return jsonify({'success': False, 'message': 'Invalid password'}), 401


@admin_bp.route('/upload_csv', methods=['POST'])
@log_endpoint_access
def upload_csv():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        f = request.files['file']
        if not f.filename.endswith('.csv'):
            return jsonify({'error': 'File must be CSV'}), 400
        df = pd.read_csv(f)
        if len(df) == 0:
            return jsonify({'error': 'CSV is empty'}), 400
        n = _insert_df_rows(df, source='file_upload')
        logger.info(f"CSV upload: {n} rows inserted")
        return jsonify({'success': True, 'message': f'Uploaded {n} rows'}), 200
    except Exception as e:
        logger.error(f"CSV upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/fetch_google_link', methods=['POST'])
@log_endpoint_access
def fetch_google_link():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        if 'docs.google.com/spreadsheets' in url and '/export' not in url:
            url = url.split('/edit')[0] + '/export?format=csv' if '/edit' in url \
                  else url.rstrip('/') + '/export?format=csv'

        creds_env = os.getenv('GOOGLE_CREDENTIALS')
        creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')

        if GOOGLE_AUTH_AVAILABLE and (creds_env or os.path.exists(creds_path)):
            creds_dict = json.loads(creds_env) if creds_env else None
            creds = (service_account.Credentials.from_service_account_info(creds_dict,
                         scopes=['https://www.googleapis.com/auth/drive.readonly'])
                     if creds_dict else
                     service_account.Credentials.from_service_account_file(creds_path,
                         scopes=['https://www.googleapis.com/auth/drive.readonly']))
            creds.refresh(GRequest())
            res = requests.get(url, headers={'Authorization': f'Bearer {creds.token}'})
            res.raise_for_status()
            df = pd.read_csv(io.StringIO(res.text))
        else:
            df = pd.read_csv(url)

        if len(df) == 0:
            return jsonify({'error': 'Sheet is empty'}), 400
        n = _insert_df_rows(df, source='google_sheet')
        return jsonify({'success': True, 'message': f'Fetched {n} rows from Google Sheets'}), 200
    except Exception as e:
        logger.error(f"Google fetch error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/create-event-and-form', methods=['POST'])
@log_endpoint_access
def create_event_and_form():
    """ATOMIC: Insert event (not committed) → call GAS → commit with form details."""
    try:
        data = request.get_json() or {}
        speaker_name      = data.get('speaker_name', '').strip()
        venue_date        = data.get('venue_date', '').strip()
        template_id_raw   = data.get('template_id', '').strip() or None
        send_certificates = bool(data.get('send_certificates', False))

        template_id = None
        if template_id_raw:
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', template_id_raw)
            template_id = match.group(1) if match else template_id_raw

        if not speaker_name or not venue_date:
            return jsonify({'success': False, 'error': 'speaker_name and venue_date required'}), 400

        apps_script_url = current_app.config.get('APPS_SCRIPT_URL') or os.getenv('APPS_SCRIPT_URL')
        ok, err = _validate_gas_url(apps_script_url)
        if not ok:
            return jsonify({'success': False, 'error': err}), 400

        with get_db() as conn:
            with conn.cursor() as cur:
                # Step 1: Insert event (holding connection/transaction open)
                cur.execute("""
                    INSERT INTO events (speaker_name, venue_date, status, template_id, send_certificates)
                    VALUES (%s, %s, 'creating_form', %s, %s) RETURNING id
                """, (speaker_name, venue_date, template_id, send_certificates))
                event_id = cur.fetchone()['id']
                logger.info(f"Event #{event_id} inserted (pending commit)")

                # Step 2: Call Google Apps Script
                secret      = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
                base_url    = os.environ.get('PUBLIC_URL') or request.host_url
                webhook_url = base_url.rstrip('/') + '/api/v1/webhook/forms/submit'

                success, result, error = _call_gas(apps_script_url, {
                    'secret': secret, 'action': 'create_form',
                    'speaker_name': speaker_name, 'venue_date': venue_date,
                    'webhook_url': webhook_url, 'event_id': event_id,
                    'send_certificates': send_certificates,
                })

                if not success:
                    conn.rollback()
                    logger.error(f"GAS form creation failed: {error}")
                    return jsonify({'success': False, 'error': f'Google Form creation failed: {error}'}), 500

                form_url      = result.get('form_url')
                form_id       = result.get('form_id')
                form_edit_url = result.get('form_edit_url')

                if not form_url or not form_id:
                    conn.rollback()
                    return jsonify({'success': False, 'error': 'Apps Script returned incomplete form data'}), 500

                # Step 3: Update event and commit
                cur.execute("""
                    UPDATE events SET form_url=%s, form_id=%s, form_edit_url=%s, status='active'
                    WHERE id=%s
                """, (form_url, form_id, form_edit_url, event_id))

        logger.info(f"Event #{event_id} committed with form {form_id}")
        return jsonify({'success': True, 'event_id': event_id, 'form_url': form_url,
                        'form_id': form_id, 'form_edit_url': form_edit_url,
                        'speaker_name': speaker_name, 'venue_date': venue_date}), 200

    except Exception as e:
        logger.error(f"Atomic event creation error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/create-event', methods=['POST'])
@log_endpoint_access
def create_event():
    """Legacy endpoint — creates event without form generation."""
    try:
        data = request.get_json() or {}
        speaker_name = data.get('speaker_name', '').strip()
        venue_date   = data.get('venue_date', '').strip()
        if not speaker_name or not venue_date:
            return jsonify({'success': False, 'error': 'speaker_name and venue_date required'}), 400
        event_id = execute_returning(
            "INSERT INTO events (speaker_name, venue_date, status) VALUES (%s,%s,'pending') RETURNING id",
            (speaker_name, venue_date)
        )
        return jsonify({'success': True, 'event_id': event_id}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/events', methods=['GET'])
def get_events():
    try:
        rows = execute_all("""
            SELECT e.*,
                   (SELECT COUNT(*) FROM feedback_responses r WHERE r.event_id = e.id) AS responses
            FROM events e
            ORDER BY e.created_at DESC
        """)
        events = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            events.append(d)
        return jsonify({'success': True, 'events': events}), 200
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/certificate-jobs', methods=['GET'])
def get_certificate_jobs():
    try:
        rows = execute_all("""
            SELECT j.*, e.speaker_name, s.name as student_name, s.email as student_email, s.roll_no, e.department
            FROM certificate_jobs j
            LEFT JOIN feedback_responses r ON j.response_id = r.id
            LEFT JOIN students s ON r.student_id = s.id
            LEFT JOIN events e ON r.event_id = e.id
            ORDER BY j.created_at DESC
            LIMIT 50
        """)
        jobs = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            jobs.append(d)
        return jsonify({'success': True, 'jobs': jobs}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/speaker-names', methods=['GET'])
@log_endpoint_access
def get_speaker_names():
    try:
        q = request.args.get('q', '').strip()
        rows = execute_all("""
            SELECT DISTINCT TRIM(speaker_name) AS n
            FROM events
            WHERE speaker_name IS NOT NULL AND TRIM(speaker_name) <> ''
            ORDER BY n
        """)
        names = [r['n'] for r in rows if r['n']]
        if q and names:
            model = get_transformer_model()
            from sentence_transformers import util
            q_emb = model.encode(q, convert_to_tensor=True)
            n_emb = model.encode(names, convert_to_tensor=True)
            scores = util.cos_sim(q_emb, n_emb)[0]
            names = [n for n, _ in sorted(zip(names, scores), key=lambda x: x[1], reverse=True)[:10]]
        return jsonify({'success': True, 'names': names}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'names': []}), 500


@admin_bp.route('/close-form', methods=['POST'])
@log_endpoint_access
def close_form():
    try:
        data = request.json or {}
        form_id  = data.get('form_id')
        event_id = data.get('event_id')
        if not form_id and not event_id:
            return jsonify({'error': 'form_id or event_id required'}), 400

        with get_db() as conn:
            with conn.cursor() as cur:
                if not form_id and event_id:
                    cur.execute("SELECT form_id FROM events WHERE id=%s", (event_id,))
                    row = cur.fetchone()
                    if row:
                        form_id = row['form_id']
                if form_id:
                    cur.execute("UPDATE events SET status='closed' WHERE form_id=%s", (form_id,))
                else:
                    cur.execute("UPDATE events SET status='closed' WHERE id=%s", (event_id,))
                if cur.rowcount == 0:
                    return jsonify({'error': 'Form not found'}), 404

        # Also close in Google (best-effort)
        if form_id:
            gas_url = os.getenv('APPS_SCRIPT_URL')
            if gas_url:
                _call_gas(gas_url, {'secret': os.getenv('APPS_SCRIPT_SECRET', 'datalens2026'),
                                    'action': 'close_form', 'form_id': form_id})

        return jsonify({'message': 'Form closed', 'status': 'closed'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/sync-responses', methods=['POST'])
@log_endpoint_access
def sync_responses():
    """Pull responses from Google Forms via Apps Script into feedback_responses."""
    try:
        data = request.get_json() or {}
        event_id = data.get('event_id')
        if not event_id:
            return jsonify({'success': False, 'error': 'event_id required'}), 400

        event = execute_one("SELECT * FROM events WHERE id=%s", (event_id,))
        if not event or not event.get('form_id'):
            return jsonify({'success': False, 'error': 'Event not found or form not generated'}), 400

        gas_url = current_app.config.get('APPS_SCRIPT_URL') or os.getenv('APPS_SCRIPT_URL')
        ok, err = _validate_gas_url(gas_url)
        if not ok:
            return jsonify({'success': False, 'error': err}), 400

        secret = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
        success, responses, error = _call_gas(gas_url, {
            'secret': secret, 'action': 'get_responses', 'form_id': event['form_id']
        }, timeout=120)

        if not success:
            return jsonify({'success': False, 'error': error}), 500

        count = skipped = 0
        with get_db() as conn:
            with conn.cursor() as cur:
                for resp in (responses or []):
                    roll_no = str(resp.get('roll_no_original', '')).strip().upper()
                    student_name = resp.get('name_of_student', '')
                    student_email = resp.get('student_email', '').strip()
                    department = resp.get('department_original', '')

                    # Upsert student
                    cur.execute("""
                        INSERT INTO students (roll_no, name, email, department)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (roll_no) DO UPDATE SET
                            name = COALESCE(EXCLUDED.name, students.name),
                            email = COALESCE(EXCLUDED.email, students.email),
                            department = COALESCE(EXCLUDED.department, students.department)
                        RETURNING id
                    """, (roll_no, student_name, student_email, department))
                    student_row = cur.fetchone()
                    if not student_row:
                        continue
                    student_id = student_row['id']

                    # Check for duplicate submission
                    cur.execute("""
                        SELECT id FROM feedback_responses
                        WHERE event_id=%s AND student_id=%s LIMIT 1
                    """, (event_id, student_id))

                    if cur.fetchone():
                        skipped += 1
                        continue

                    # Insert feedback response
                    submitted_at = resp.get('timestamp')
                    try:
                        submitted_at = pd.to_datetime(submitted_at).strftime('%Y-%m-%d %H:%M:%S%z') if pd.notna(submitted_at) else datetime.now().isoformat()
                    except:
                        submitted_at = datetime.now().isoformat()

                    cur.execute("""
                        INSERT INTO feedback_responses (
                            event_id, student_id, submitted_at,
                            session_help_understanding, session_rating, session_technical_clarity,
                            aspect_most_valuable, improvements_suggestions, future_topics,
                            is_duplicate
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING id
                    """, (
                        event_id, student_id, submitted_at,
                        resp.get('session_help_understanding', ''),
                        _safe_int(resp.get('session_rating')),
                        _safe_int(resp.get('session_technical_clarity')),
                        resp.get('aspect_most_valuable', ''),
                        resp.get('improvements_suggestions', ''),
                        resp.get('future_topics', ''),
                        False
                    ))
                    response_id = cur.fetchone()['id']

                    if event.get('send_certificates') and event.get('template_id'):
                        job_status = 'pending' if student_email else 'failed'
                        job_error = None if student_email else 'No email address provided in form submission'

                        # Check if a certificate job already exists for this response
                        cur.execute("SELECT id FROM certificate_jobs WHERE response_id=%s LIMIT 1",
                                    (response_id,))
                        if not cur.fetchone():
                            cur.execute("""
                                INSERT INTO certificate_jobs
                                    (response_id, status, error_message)
                                VALUES (%s, %s, %s)
                            """, (response_id, job_status, job_error))
                    count += 1

        return jsonify({'success': True, 'synced': count, 'skipped': skipped, 'total': len(responses or [])}), 200
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/config/validate', methods=['GET'])
@log_endpoint_access
def validate_config():
    try:
        gas_url = os.getenv('APPS_SCRIPT_URL')
        is_valid, err = _validate_gas_url(gas_url)
        checks = {
            'apps_script_url': {
                'configured': bool(gas_url), 'valid': is_valid,
                'value': (gas_url[:50] + '...') if gas_url and len(gas_url) > 50 else gas_url,
                'error': err,
            },
            'apps_script_secret': {
                'configured': bool(os.getenv('APPS_SCRIPT_SECRET')),
                'is_default': os.getenv('APPS_SCRIPT_SECRET') == 'datalens2026',
            },
            'webhook_secret': {
                'configured': bool(current_app.config.get('WEBHOOK_SECRET')),
            },
            'database': {'type': 'supabase_postgresql', 'status': 'connected'},
        }
        all_valid = is_valid and checks['apps_script_secret']['configured'] and checks['webhook_secret']['configured']
        return jsonify({'success': True, 'all_valid': all_valid, 'checks': checks}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Legacy alias kept for backward compat
@admin_bp.route('/generate-form', methods=['POST'])
@log_endpoint_access
def generate_form():
    """DEPRECATED — use /create-event-and-form instead."""
    try:
        data = request.get_json() or {}
        event_id = data.get('event_id')
        if not event_id:
            return jsonify({'success': False, 'error': 'event_id required'}), 400

        event = execute_one("SELECT * FROM events WHERE id=%s", (event_id,))
        if not event:
            return jsonify({'success': False, 'error': 'Event not found'}), 404

        gas_url = current_app.config.get('APPS_SCRIPT_URL') or os.getenv('APPS_SCRIPT_URL')
        ok, err = _validate_gas_url(gas_url)
        if not ok:
            return jsonify({'success': False, 'error': err}), 400

        base_url    = os.environ.get('PUBLIC_URL') or request.host_url
        webhook_url = base_url.rstrip('/') + '/api/v1/webhook/forms/submit'
        success, result, error = _call_gas(gas_url, {
            'secret': os.getenv('APPS_SCRIPT_SECRET', 'datalens2026'),
            'action': 'create_form',
            'speaker_name': event['speaker_name'],
            'venue_date': str(event['venue_date']),
            'webhook_url': webhook_url,
            'event_id': event_id,
        })
        if not success:
            return jsonify({'success': False, 'error': error}), 500

        form_url, form_id = result.get('form_url'), result.get('form_id')
        if not form_url:
            return jsonify({'success': False, 'error': 'No form URL returned'}), 500

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE events SET form_url=%s, form_id=%s, form_edit_url=%s, status='active'
                    WHERE id=%s
                """, (form_url, form_id, result.get('form_edit_url'), event_id))

        return jsonify({'success': True, 'form_url': form_url, 'form_id': form_id}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
