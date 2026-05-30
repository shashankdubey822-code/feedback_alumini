"""
webhook.py — Handle incoming webhooks from Google Forms / Apps Script.
Uses native InsForge PostgreSQL via insforge_db.py.
Table: feedback_responses (was: dashboard_data)
"""

import re
import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from backend.utils.logger import get_section_logger, log_endpoint_access
from backend.utils.insforge_db import get_db

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

# Matches institute roll numbers: 2K25EDUN01013
ROLL_NO_PATTERN = re.compile(r"^2[Kk]\d{2}[A-Za-z]{3,12}\d{5}$")

logger = get_section_logger('webhook')

# Simple in-memory notification queue (single-process dev server)
LATEST_NOTIFICATIONS = []

webhook_bp = Blueprint('webhook', __name__, url_prefix='/api/v1/webhook')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_timestamp(iso_str: str) -> tuple[str, str]:
    """
    Convert ISO timestamp to IST.
    Returns (display: DD-MM-YYYY HH:MM:SS, normalized: YYYY-MM-DD HH:MM:SS).
    """
    raw = (iso_str or '').strip()
    try:
        if raw.endswith('Z'):
            raw = raw[:-1] + '+00:00'
        dt_utc = datetime.fromisoformat(raw)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    except Exception:
        dt_utc = datetime.now(timezone.utc)

    if ZoneInfo:
        try:
            local = dt_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        except Exception:
            local = dt_utc
    else:
        from datetime import timedelta
        local = dt_utc + timedelta(hours=5, minutes=30)

    return local.strftime("%d-%m-%Y %H:%M:%S"), local.strftime("%Y-%m-%d %H:%M:%S")


def _normalize_roll(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return ''
    roll = raw.strip().upper()
    compact = re.sub(r"[\s\-]+", "", roll)
    return compact if ROLL_NO_PATTERN.match(compact) else roll


def _update_sync_status(success: bool, error_message: str = None):
    """Persist webhook health to a JSON file (best-effort)."""
    import os
    try:
        status_file = os.path.join(
            current_app.root_path, 'logs', 'sync_health.json')
        data = {}
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['last_heartbeat'] = now
        if success:
            data.update(status='working', last_sync=now,
                        success_count=data.get('success_count', 0) + 1)
        else:
            data.update(status='error',
                        failure_count=data.get('failure_count', 0) + 1,
                        last_error=error_message)
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Could not update sync_health.json: {e}")


# ---------------------------------------------------------------------------
# Core submission logic
# ---------------------------------------------------------------------------

def store_webhook_submission(payload: dict) -> int:
    """
    Insert a Google Form submission into feedback_responses.
    Also enqueues a certificate_jobs row if the event requires it.
    Returns the new row id.
    """
    raw_ts = payload.get('timestamp') or datetime.now(timezone.utc).isoformat()
    timestamp_display, normalized_ts = _format_timestamp(raw_ts)

    form_id = payload.get('form_id', 'WEBHOOK_FORM')
    responses = payload.get('responses', {})

    from backend.utils.insforge_db import api_select, api_insert, api_update, api_upsert

    # ── Look up event ────────────────────────────────────────────
    event_list = api_select('events', 'form_id', form_id)
    event = event_list[0] if event_list else None

    event_id = None
    send_certs = False
    template_id = None
    speaker_name = responses.get('alumni_speaker_name', '')
    date_of_lec = responses.get('date_of_lecture', '')

    if event:
        event_id = event.get('id')
        template_id = event.get('template_id')
        send_certs = bool(event.get('send_certificates'))

        if event.get('status') == 'closed':
            raise ValueError("Form is closed and no longer accepting responses.")

        # 24-hour expiry check
        created_at = event.get('created_at')
        if created_at and hasattr(created_at, 'utcoffset'):
            age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        else:
            try:
                created_at_dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                age_hours = (datetime.now(timezone.utc) - created_at_dt).total_seconds() / 3600
            except Exception:
                age_hours = 0

        if age_hours > 24:
            api_update('events', 'id', event_id, {'status': 'closed'})
            raise ValueError("Form has expired (24-hour limit exceeded).")

        # Enrich speaker/date from event record
        if event.get('speaker_name'):
            speaker_name = event.get('speaker_name')
        if event.get('venue_date') and not date_of_lec:
            date_of_lec = str(event.get('venue_date'))

    # ── Upsert Student ────────────────────────────────────────────
    student_name = responses.get('name_of_student', '').strip()
    student_email = responses.get('student_email', '').strip()
    if not student_email:
        for v in responses.values():
            if isinstance(v, str) and '@' in v and '.' in v:
                student_email = v.strip()
                break

    roll_no = _normalize_roll(responses.get('roll_no_original', ''))
    
    stu_res = api_upsert('students', {
        'name': student_name,
        'email': student_email,
        'roll_no': roll_no
    }, 'roll_no')
    
    student_id = stu_res[0]['id'] if stu_res else None
    if not student_id:
        raise ValueError("Failed to upsert student.")

    from backend.utils.insforge_db import execute_one
    
    # ── Insert or update feedback_responses ────────────────────────────
    payload_data = {
        'event_id': event_id,
        'student_id': student_id,
        'submitted_at': normalized_ts,
        'session_rating': responses.get('session_rating'),
        'session_help_understanding': responses.get('session_help_understanding', ''),
        'session_technical_clarity': responses.get('session_technical_clarity'),
        'aspect_most_valuable': responses.get('aspect_most_valuable', ''),
        'improvements_suggestions': responses.get('improvements_suggestions', ''),
        'future_topics': responses.get('future_topics', ''),
        'form_source': form_id,
        'record_status': 'active'
    }

    fb_check = execute_one("SELECT id FROM feedback_responses WHERE event_id=%s AND student_id=%s", (event_id, student_id))
    if fb_check:
        api_update('feedback_responses', 'id', fb_check['id'], payload_data)
        response_id = fb_check['id']
    else:
        fb_res = api_insert('feedback_responses', payload_data)
        response_id = fb_res[0]['id'] if fb_res else None

    # ── Enqueue certificate job if enabled ────────────────────────
    if send_certs and template_id and event_id:
        job_status = 'pending'
        job_error  = None
        if not student_email:
            job_status = 'failed'
            job_error  = 'No email address provided in form submission'

        job_check = execute_one("SELECT id FROM certificate_jobs WHERE event_id=%s AND student_id=%s", (event_id, student_id))
        if not job_check:
            api_insert('certificate_jobs', {
                'student_id': student_id,
                'event_id': event_id,
                'status': job_status,
                'error_log': job_error
            })
            logger.info(f"Certificate job enqueued for {student_name} ({student_email or 'no email'})")
        else:
            logger.info(f"Certificate job already exists for {student_name}")

    return response_id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@webhook_bp.route('/forms/submit', methods=['POST'])
@log_endpoint_access
def receive_form_submission():
    """Receive and store a Google Form submission."""
    try:
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        expected   = current_app.config.get('WEBHOOK_SECRET', '')
        if auth_token != expected:
            logger.warning(f"Unauthorized webhook from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized'}), 401

        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'No data provided'}), 400

        if payload.get('action') == 'heartbeat':
            logger.info("Heartbeat received from Apps Script")
            _update_sync_status(True)
            return jsonify({
                'status': 'success',
                'message': 'Heartbeat received',
                'timestamp': datetime.utcnow().isoformat()
            }), 200

        record_id    = store_webhook_submission(payload)
        student_name = (payload.get('responses') or {}).get('name_of_student', 'Anonymous')
        LATEST_NOTIFICATIONS.append(f"New submission from: {student_name}")
        logger.info(f"Webhook submission stored #{record_id}")
        _update_sync_status(True)

        # Real-time WebSocket emission & Analytics Refresh
        try:
            from backend.extensions import socketio
            from backend.services.analytics_engine import analytics_engine
            
            def background_refresh():
                try:
                    analytics_engine.refresh_single_record(record_id)
                    logger.info(f"Background analytics refresh completed for #{record_id}")
                except Exception as e:
                    logger.error(f"Background analytics refresh failed: {e}")

            # Refresh pandas dataframe in background to not block webhook response
            socketio.start_background_task(background_refresh)
            
            # Broadcast the update to all connected clients
            socketio.emit('new_feedback', {
                'message': f"New submission from {student_name}",
                'student_name': student_name,
                'record_id': record_id
            })
            logger.info(f"Emitted real-time new_feedback event for #{record_id}")
        except Exception as ws_err:
            logger.error(f"WebSocket emit error: {ws_err}")

        return jsonify({'status': 'success', 'record_id': record_id, 'message': 'Stored'}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        _update_sync_status(False, str(e))
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/forms/verify', methods=['GET'])
def verify_webhook():
    return jsonify({'status': 'ready', 'message': 'Webhook endpoint operational'}), 200


@webhook_bp.route('/forms/test', methods=['POST'])
@log_endpoint_access
def test_webhook():
    """Test with sample data (requires valid token)."""
    try:
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        expected   = current_app.config.get('WEBHOOK_SECRET', '')
        if auth_token != expected:
            return jsonify({'error': 'Unauthorized'}), 401

        test_payload = {
            'timestamp': datetime.utcnow().isoformat(),
            'form_id': 'TEST_FORM',
            'responses': {
                'name_of_student':    'Test Student',
                'department_original':'Test Department',
                'roll_no_original':   '2K25TESTU01001',
                'session_rating':     4,
                'aspect_most_valuable':       'Great session',
                'improvements_suggestions':   'More examples',
            }
        }
        record_id = store_webhook_submission(test_payload)
        _update_sync_status(True)
        return jsonify({'status': 'success', 'record_id': record_id}), 200

    except Exception as e:
        _update_sync_status(False, str(e))
        return jsonify({'error': str(e)}), 500


@webhook_bp.route('/notifications', methods=['GET'])
def get_notifications():
    global LATEST_NOTIFICATIONS
    notifications = list(LATEST_NOTIFICATIONS)
    LATEST_NOTIFICATIONS.clear()
    return jsonify({'status': 'success', 'notifications': notifications}), 200
