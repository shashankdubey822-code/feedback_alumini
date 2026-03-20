"""
Webhook Routes - Handle incoming webhooks from Google Forms
"""

from flask import Blueprint, request, jsonify
import sqlite3
from datetime import datetime
from ..utils.logger import get_logger, log_endpoint_access

logger = get_logger(__name__)

webhook_bp = Blueprint('webhook', __name__, url_prefix='/api/v1/webhook')


def verify_webhook_secret(token: str, expected: str) -> bool:
    """Verify webhook authorization token"""
    return token == expected


def store_webhook_submission(db_path: str, payload: dict) -> int:
    """Store webhook submission in database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Extract form data from webhook payload
        timestamp = payload.get('timestamp', datetime.utcnow().isoformat())
        form_id = payload.get('form_id', 'WEBHOOK_FORM')
        responses = payload.get('responses', {})

        # Normalize roll_no to uppercase
        roll_no = responses.get('roll_no_original', '')
        if roll_no and isinstance(roll_no, str):
            roll_no = roll_no.upper()

        # Map webhook field names to database columns
        insert_query = '''
            INSERT INTO dashboard_data (
                timestamp_original,
                name_of_student,
                department_original,
                roll_no_original,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        values = (
            timestamp,
            responses.get('name_of_student', ''),
            responses.get('department_original', ''),
            roll_no,  # Already converted to uppercase
            responses.get('date_of_lecture', ''),
            responses.get('alumni_speaker_name', ''),
            responses.get('session_help_understanding', ''),
            responses.get('session_rating', None),
            responses.get('session_technical_clarity', None),
            responses.get('aspect_most_valuable', ''),
            responses.get('improvements_suggestions', ''),
            responses.get('future_topics', ''),
            form_id,
            'WEBHOOK_RECEIVED'
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
        from flask import current_app

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

        # Store submission
        db_path = current_app.config.get('DATABASE_PATH', 'database/dashboard.db')
        record_id = store_webhook_submission(db_path, payload)

        logger.info(f"Successfully received webhook submission #{record_id}")

        return jsonify({
            'status': 'success',
            'record_id': record_id,
            'message': 'Submission received and stored',
        }), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


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
        from flask import current_app

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

        return jsonify({
            'status': 'success',
            'record_id': record_id,
            'message': 'Test submission received and stored',
        }), 200

    except Exception as e:
        logger.error(f"Error in test webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500
