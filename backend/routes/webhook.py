"""
Webhook Routes - Handle incoming webhooks from Google Forms
"""

from flask import Blueprint, request, jsonify, current_app
import sqlite3
import os
import json
import re
from datetime import datetime, timezone
from ..utils.logger import get_section_logger, log_endpoint_access
from ..utils.db_helper import get_db_connection

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

# Matches Student_Feedback_Trimmed.csv roll style: 2K + YY + programme letters + 5 digits (e.g. 2K25EDUN01013, 2K24ECUN03021)
ROLL_NO_PATTERN = re.compile(r"^2[Kk]\d{2}[A-Za-z]{3,12}\d{5}$")


def format_submission_timestamp_like_csv(iso_str: str) -> tuple:
    """
    Store timestamps as DD-MM-YYYY HH:MM:SS in Asia/Kolkata local time.
    Returns (display_timestamp, normalized_sql_timestamp).
    display_timestamp  →  e.g. "26-05-2026 17:39:40"   (DD-MM-YYYY HH:MM:SS)
    normalized_sql    →  e.g. "2026-05-26 17:39:40"   (SQL-sortable YYYY-MM-DD)
    """
    dt_utc = None
    raw = (iso_str or "").strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt_utc = datetime.fromisoformat(raw)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    except Exception:
        dt_utc = datetime.now(timezone.utc)

    if ZoneInfo:
        try:
            local = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        except Exception:
            local = dt_utc.astimezone(timezone.utc)
    else:
        from datetime import timedelta
        local = dt_utc + timedelta(hours=5, minutes=30)

    # Format: DD-MM-YYYY HH:MM:SS  (day-month-year, 24-hour clock, zero-padded)
    display = local.strftime("%d-%m-%Y %H:%M:%S")
    normalized = local.strftime("%Y-%m-%d %H:%M:%S")
    return display, normalized

logger = get_section_logger('webhook')

# Simple in-memory queue for dashboard notifications
# (Using global as we're in a single-process Flask dev server)
LATEST_NOTIFICATIONS = []

webhook_bp = Blueprint('webhook', __name__, url_prefix='/api/v1/webhook')


def verify_webhook_secret(token: str, expected: str) -> bool:
    """Verify webhook authorization token"""
    return token == expected


def update_sync_status(success: bool, error_message=None):
    """Update the sync_health.json file with the latest status"""
    try:
        # Use a safe path relative to the app root
        status_file = os.path.join(current_app.root_path, 'logs', 'sync_health.json')
        
        status_data = {
            "status": "active",
            "last_sync": None,
            "success_count": 0,
            "failure_count": 0,
            "last_error": None
        }
        
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
            except:
                pass
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_data["last_heartbeat"] = now_str
        
        if success:
            status_data["status"] = "working"
            status_data["last_sync"] = now_str
            try:
                curr_count = status_data.get("success_count", 0)
                status_data["success_count"] = int(curr_count) + 1 if curr_count is not None else 1
            except (ValueError, TypeError):
                status_data["success_count"] = 1
        else:
            status_data["status"] = "error"
            try:
                curr_count = status_data.get("failure_count", 0)
                status_data["failure_count"] = int(curr_count) + 1 if curr_count is not None else 1
            except (ValueError, TypeError):
                status_data["failure_count"] = 1
            status_data["last_error"] = error_message
            
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        logger.error(f"Critical error updating sync status JSON: {str(e)}")


def store_webhook_submission(db_path: str, payload: dict) -> int:
    """Store webhook submission in database"""
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        # Extract form data from webhook payload (timestamp aligned to CSV + Asia/Kolkata)
        raw_ts = payload.get('timestamp') or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        timestamp, timestamp_normalized = format_submission_timestamp_like_csv(raw_ts)
        form_id = payload.get('form_id', 'WEBHOOK_FORM')
        responses = payload.get('responses', {})

        # Enforce 24-Hour Expiry & Closed Status
        cursor.execute("SELECT id, created_at, status, template_id, send_certificates FROM events WHERE form_id = ?", (form_id,))
        event = cursor.fetchone()
        
        event_id = None
        send_certs = 0
        template_id = None
        
        if event:
            event_id, created_at_str, status, template_id, send_certs = event
            if status == 'closed':
                logger.warning(f"Rejected webhook for closed form: {form_id}")
                raise ValueError("Form is closed and no longer accepting responses.")
            
            try:
                # Handle standard SQLite CURRENT_TIMESTAMP format
                if "T" in created_at_str:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                
                age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
                if age_hours > 24:
                    logger.warning(f"Rejected webhook for expired form: {form_id} (Age: {age_hours:.1f}h)")
                    
                    # Auto-close it in the database since we caught it expired
                    cursor.execute("UPDATE events SET status = 'closed' WHERE form_id = ?", (form_id,))
                    conn.commit()
                    
                    raise ValueError("Form has expired (24-hour limit exceeded).")
            except Exception as e:
                if isinstance(e, ValueError) and "Form has expired" in str(e):
                    raise
                logger.warning(f"Could not parse created_at for expiry check: {created_at_str}. Error: {e}")

        # Normalize roll_no; prefer compact form when it matches institute pattern (e.g. 2K25EDUN01013)
        roll_raw = responses.get('roll_no_original', '')
        roll_no = ''
        if roll_raw and isinstance(roll_raw, str):
            roll_no = roll_raw.strip().upper()
            compact = re.sub(r"[\s\-]+", "", roll_no)
            if compact and ROLL_NO_PATTERN.match(compact):
                roll_no = compact
            elif compact:
                logger.warning(f"Roll number format unexpected (storing as entered): {roll_raw!r}")

        # Map webhook field names to database columns
        insert_query = '''
            INSERT INTO dashboard_data (
                timestamp_original,
                timestamp_normalized,
                name_of_student,
                department_original,
                department_cleaned,
                roll_no_original,
                roll_no_cleaned,
                date_of_lecture,
                alumni_speaker_name,
                session_help_understanding,
                session_rating,
                session_technical_clarity,
                aspect_most_valuable,
                improvements_suggestions,
                future_topics,
                form_source,
                record_status,
                cleaned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        # Normalize data for "Cleaned" columns
        raw_dept = responses.get('department_original', '')
        dept_cleaned = str(raw_dept).strip()
        
        # Roll Number normalization (already done for roll_no variable above)
        
        # ── Auto-enrich speaker & date from events table ──────────────────────
        # The student form has no "speaker name" question — it's stored in the
        # events table. Look it up by form_id so the Compilation tab shows it.
        event_speaker_name = responses.get('alumni_speaker_name', '')
        event_date_of_lecture = responses.get('date_of_lecture', '')

        if form_id and form_id != 'WEBHOOK_FORM':
            try:
                cursor.execute(
                    "SELECT speaker_name, venue_date FROM events WHERE form_id = ?",
                    (form_id,)
                )
                ev_row = cursor.fetchone()
                if ev_row:
                    if ev_row[0]:
                        event_speaker_name = ev_row[0]
                    if ev_row[1] and not event_date_of_lecture:
                        event_date_of_lecture = ev_row[1]
            except Exception as lookup_err:
                logger.warning(f"Could not enrich speaker from events: {lookup_err}")

        values = (
            timestamp,
            timestamp_normalized,
            responses.get('name_of_student', ''),
            raw_dept,
            dept_cleaned,
            roll_no,  # Original (uppercased)
            roll_no,  # Cleaned (same as original for now)
            event_date_of_lecture,
            event_speaker_name,
            responses.get('session_help_understanding', ''),
            responses.get('session_rating', None),
            responses.get('session_technical_clarity', None),
            responses.get('aspect_most_valuable', ''),
            responses.get('improvements_suggestions', ''),
            responses.get('future_topics', ''),
            form_id,
            'WEBHOOK_RECEIVED',
            datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        )

        cursor.execute(insert_query, values)

        # Enqueue certificate job if send_certificates is enabled
        if send_certs == 1 and template_id:
            student_name = responses.get('name_of_student', '').strip()
            student_email = responses.get('student_email', '').strip()
            
            # Check if we got an email, otherwise check if there's any other field containing email/at-sign
            if not student_email:
                for k, v in responses.items():
                    if isinstance(v, str) and '@' in v and '.' in v:
                        student_email = v.strip()
                        break
            
            job_status = 'pending'
            job_error = None
            if not student_email:
                job_status = 'failed'
                job_error = 'No email address provided in form submission'
                logger.warning(f"Certificate job created as failed: {job_error} for student {student_name}")

            cursor.execute("""
                INSERT INTO job_queue (student_name, student_email, roll_no, department, event_id, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_name, student_email, roll_no, dept_cleaned, event_id, job_status, job_error))
            logger.info(f"Enqueued certificate job for {student_name} ({student_email or 'No Email'})")

        conn.commit()

        record_id = cursor.lastrowid
        conn.close()

        return record_id
    except Exception as e:
        logger.error(f"Error storing webhook submission: {str(e)}")
        raise


@webhook_bp.route('/forms/submit', methods=['POST'])
@log_endpoint_access
def receive_form_submission():
    """Receive and store form submission from Google Apps Script"""
    try:

        # Verify authorization token
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        expected_token = current_app.config.get('WEBHOOK_SECRET', '')

        if not verify_webhook_secret(auth_token, expected_token):
            logger.warning(f"Unauthorized webhook attempt from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized'}), 401

        # Parse JSON payload
        payload = request.get_json()

        if not payload:
            return jsonify({'error': 'No data provided'}), 400

        # Handle heartbeat ping from Google Apps Script
        if payload.get('action') == 'heartbeat':
            logger.info("Received heartbeat ping from Google Apps Script")
            update_sync_status(True)
            return jsonify({
                'status': 'success',
                'message': 'Heartbeat received',
                'timestamp': datetime.utcnow().isoformat()
            }), 200

        # Store submission
        db_path = current_app.config.get('DATABASE_PATH')
        record_id = store_webhook_submission(db_path, payload)

        # Add to notification queue
        student_name = (payload.get('responses') or {}).get('name_of_student') or payload.get('name_of_student') or 'Anonymous'
        LATEST_NOTIFICATIONS.append(f"New submission from: {student_name}")

        logger.info(f"Successfully received webhook submission #{record_id}")
        update_sync_status(True)

        return jsonify({
            'status': 'success',
            'record_id': record_id,
            'message': 'Submission received and stored',
        }), 200

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing webhook: {error_msg}")
        update_sync_status(False, error_msg)
        return jsonify({'error': error_msg}), 500


@webhook_bp.route('/forms/verify', methods=['GET'])
def verify_webhook():
    """Verify webhook endpoint is accessible"""
    return jsonify({
        'status': 'ready',
        'message': 'Webhook endpoint is operational',
    }), 200


@webhook_bp.route('/forms/test', methods=['POST'])
@log_endpoint_access
def test_webhook():
    """Test webhook with sample data (requires valid token)"""
    try:

        # Verify authorization token
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        expected_token = current_app.config.get('WEBHOOK_SECRET', '')

        if not verify_webhook_secret(auth_token, expected_token):
            return jsonify({'error': 'Unauthorized'}), 401

        # Create test payload
        test_payload = {
            'timestamp': datetime.utcnow().isoformat(),
            'form_id': 'TEST_FORM',
            'responses': {
                'name_of_student': 'Test Student',
                'department_original': 'Test Department',
                'roll_no_original': '2K25TESTU01001',
                'session_rating': 4,
                'aspect_most_valuable': 'Great session',
                'improvements_suggestions': 'More examples would help',
            }
        }

        # Store test submission
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        record_id = store_webhook_submission(db_path, test_payload)

        logger.info(f"Test webhook submission stored with ID #{record_id}")
        update_sync_status(True)

        return jsonify({
            'status': 'success',
            'record_id': record_id,
            'message': 'Test submission received and stored',
        }), 200

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in test webhook: {error_msg}")
        update_sync_status(False, error_msg)
        return jsonify({'error': error_msg}), 500


@webhook_bp.route('/notifications', methods=['GET'])
def get_notifications():
    """Fetch and clear the latest notifications for the dashboard"""
    global LATEST_NOTIFICATIONS
    notifications = list(LATEST_NOTIFICATIONS)
    LATEST_NOTIFICATIONS.clear()
    return jsonify({
        'status': 'success',
        'notifications': notifications
    }), 200
