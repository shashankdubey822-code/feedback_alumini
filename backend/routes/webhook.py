"""
Webhook Routes - Handle incoming webhooks from Google Forms
"""

from flask import Blueprint, request, jsonify, current_app
import sqlite3
import os
import json
from datetime import datetime
from ..utils.logger import get_section_logger, log_endpoint_access
from ..utils.db_helper import get_db_connection

logger = get_section_logger('webhook')

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

        # Extract form data from webhook payload
        timestamp = payload.get('timestamp', datetime.utcnow().isoformat())
        form_id = payload.get('form_id', 'WEBHOOK_FORM')
        responses = payload.get('responses', {})

        # Enforce 24-Hour Expiry & Closed Status
        cursor.execute("SELECT created_at, status FROM events WHERE form_id = ?", (form_id,))
        event = cursor.fetchone()
        
        if event:
            created_at_str, status = event
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

        # Normalize roll_no to uppercase
        roll_no = responses.get('roll_no_original', '')
        if roll_no and isinstance(roll_no, str):
            roll_no = roll_no.upper()

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
        
        # Timestamp normalization
        try:
            timestamp_normalized = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        except:
            timestamp_normalized = timestamp

        values = (
            timestamp,
            timestamp_normalized,
            responses.get('name_of_student', ''),
            raw_dept,
            dept_cleaned,
            roll_no,  # Original (uppercased)
            roll_no,  # Cleaned (same as original for now)
            responses.get('date_of_lecture', ''),
            responses.get('alumni_speaker_name', ''),
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
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        record_id = store_webhook_submission(db_path, payload)

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
                'roll_no_original': '12345',
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
