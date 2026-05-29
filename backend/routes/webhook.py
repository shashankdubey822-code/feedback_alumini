"""
webhook.py — Handle incoming webhooks from Google Forms / Apps Script.
Uses native Supabase PostgreSQL via supabase_db.py.
Table: feedback_responses (was: dashboard_data)
"""

import re
import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from backend.utils.logger import get_section_logger, log_endpoint_access
from backend.utils.supabase_db import get_db

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
        status_file = os.path.join(current_app.root_path, 'logs', 'sync_health.json')
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
    timestamp_display, _ = _format_timestamp(raw_ts)

    form_id   = payload.get('form_id', 'WEBHOOK_FORM')
    responses = payload.get('responses', {})

    with get_db() as conn:
        with conn.cursor() as cur:

            # ── Look up event ────────────────────────────────────────────
            cur.execute("""
                SELECT id, status, template_id, send_certificates,
                       speaker_name, venue_date, created_at
                FROM events WHERE form_id = %s
            """, (form_id,))
            event = cur.fetchone()

            event_id      = None
            send_certs    = False
            template_id   = None
            speaker_name  = responses.get('alumni_speaker_name', '')
            date_of_lec   = responses.get('date_of_lecture', '')

            if event:
                event_id    = event['id']
                template_id = event['template_id']
                send_certs  = bool(event['send_certificates'])

                if event['status'] == 'closed':
                    raise ValueError("Form is closed and no longer accepting responses.")

                # 24-hour expiry check
                created_at = event['created_at']
                if created_at and hasattr(created_at, 'utcoffset'):
                    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                else:
                    try:
                        created_at_dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                        age_hours = (datetime.now(timezone.utc) - created_at_dt).total_seconds() / 3600
                    except Exception:
                        age_hours = 0

                if age_hours > 24:
                    cur.execute("UPDATE events SET status = 'closed' WHERE id = %s", (event_id,))
                    conn.commit()
                    raise ValueError("Form has expired (24-hour limit exceeded).")

                # Enrich speaker/date from event record
                if event['speaker_name']:
                    speaker_name = event['speaker_name']
                if event['venue_date'] and not date_of_lec:
                    date_of_lec = str(event['venue_date'])

            # ── Roll number normalization ─────────────────────────────────
            roll_no = _normalize_roll(responses.get('roll_no_original', ''))

            # ── Insert into feedback_responses ────────────────────────────
            cur.execute("""
                INSERT INTO feedback_responses (
                    event_id,
                    submitted_at,
                    timestamp_display,
                    name_of_student,
                    roll_no,
                    department,
                    student_email,
                    date_of_lecture,
                    alumni_speaker_name,
                    session_help_understanding,
                    session_rating,
                    session_technical_clarity,
                    aspect_most_valuable,
                    improvements_suggestions,
                    future_topics,
                    form_source,
                    record_status
                ) VALUES (
                    %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                event_id,
                timestamp_display,
                responses.get('name_of_student', ''),
                roll_no,
                responses.get('department_original', ''),
                responses.get('student_email', ''),
                date_of_lec,
                speaker_name,
                responses.get('session_help_understanding', ''),
                responses.get('session_rating'),
                responses.get('session_technical_clarity'),
                responses.get('aspect_most_valuable', ''),
                responses.get('improvements_suggestions', ''),
                responses.get('future_topics', ''),
                form_id,
                'active',
            ))
            row = cur.fetchone()
            response_id = row['id']

            # ── Enqueue certificate job if enabled ────────────────────────
            if send_certs and template_id and event_id:
                student_name  = responses.get('name_of_student', '').strip()
                student_email = responses.get('student_email', '').strip()

                # Fallback email scan
                if not student_email:
                    for v in responses.values():
                        if isinstance(v, str) and '@' in v and '.' in v:
                            student_email = v.strip()
                            break

                job_status = 'pending'
                job_error  = None
                if not student_email:
                    job_status = 'failed'
                    job_error  = 'No email address provided in form submission'

                cur.execute("""
                    INSERT INTO certificate_jobs
                        (event_id, response_id, student_name, student_email,
                         roll_no, department, status, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    event_id, response_id, student_name, student_email,
                    roll_no, responses.get('department_original', ''),
                    job_status, job_error,
                ))
                logger.info(f"Certificate job enqueued for {student_name} ({student_email or 'no email'})")

        # commit happens via context manager
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
