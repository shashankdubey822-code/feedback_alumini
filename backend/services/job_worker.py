import threading
import time
import sqlite3
import json
import urllib.request
import urllib.error
from backend.config import get_config
from backend.utils.logger import get_section_logger
from backend.utils.db_helper import get_db_connection

_job_thread = None

def start_job_worker(logger_unused):
    """Start the background certificate generation worker thread"""
    global _job_thread
    job_logger = get_section_logger('job_worker')
    config = get_config()()
    db_path = config.DATABASE_PATH
    
    # We retrieve Apps Script settings directly from environment or config
    apps_script_url = config.APPS_SCRIPT_URL
    apps_script_secret = config.APPS_SCRIPT_SECRET or 'datalens2026'

    def call_apps_script(url, payload):
        if not url:
            return False, "Google Apps Script URL is not configured in .env (APPS_SCRIPT_URL)"
        
        max_retries = 3
        retry_delay = [2, 5, 10]
        
        for attempt in range(max_retries):
            try:
                payload_bytes = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(
                    url,
                    data=payload_bytes,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    response_text = response.read().decode('utf-8')
                    response_data = json.loads(response_text)
                    if response_data.get('success'):
                        return True, None
                    else:
                        msg = response_data.get('message', 'Unknown error from Google Script')
                        details = response_data.get('data', '')
                        error_msg = f"{msg}: {details}" if details else msg
                        return False, error_msg
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else 'No response body'
                err_msg = f"HTTP {e.code}: {error_body}"
                if attempt < max_retries - 1:
                    time.sleep(retry_delay[attempt])
                    continue
                return False, err_msg
            except urllib.error.URLError as e:
                err_msg = f"Connection failed: {str(e.reason)}"
                if attempt < max_retries - 1:
                    time.sleep(retry_delay[attempt])
                    continue
                return False, err_msg
            except json.JSONDecodeError:
                return False, "Invalid response format from Google Script"
            except Exception as e:
                return False, f"Unexpected error: {str(e)}"
        return False, "Max retries exceeded"

    def worker_loop():
        job_logger.info("Certificate Job Worker Thread Started.")
        
        while True:
            try:
                conn = get_db_connection(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check if the table exists (startup safety)
                cursor.execute("PRAGMA table_info(job_queue)")
                if not cursor.fetchall():
                    conn.close()
                    time.sleep(5)
                    continue

                # Query pending jobs
                cursor.execute('''
                    SELECT j.id, j.student_name, j.student_email, j.roll_no, j.department, j.event_id, j.attempts,
                           e.template_id, e.speaker_name, e.venue_date
                    FROM job_queue j
                    JOIN events e ON j.event_id = e.id
                    WHERE j.status = 'pending' AND j.attempts < 3
                    LIMIT 5
                ''')
                jobs = cursor.fetchall()
                
                if jobs:
                    job_logger.info(f"Job Worker processing {len(jobs)} pending certificate jobs...")
                    for job in jobs:
                        job_id = job['id']
                        student_name = job['student_name']
                        student_email = job['student_email']
                        roll_no = job['roll_no'] or ""
                        department = job['department'] or ""
                        template_id = job['template_id']
                        speaker_name = job['speaker_name'] or ""
                        venue_date = job['venue_date'] or ""
                        attempts = job['attempts']
                        
                        if not template_id:
                            # Cannot generate without template_id
                            cursor.execute('''
                                UPDATE job_queue 
                                SET status = 'failed', attempts = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (attempts + 1, 'No Google Slides Template ID configured for this event.', job_id))
                            conn.commit()
                            continue

                        # 1. Update status to 'processing' to prevent concurrent pickup
                        cursor.execute('''
                            UPDATE job_queue 
                            SET status = 'processing', updated_at = CURRENT_TIMESTAMP 
                            WHERE id = ?
                        ''', (job_id,))
                        conn.commit()
                        
                        # 2. Call Google Apps Script
                        payload = {
                            'secret': apps_script_secret,
                            'action': 'generate_certificate',
                            'template_id': template_id,
                            'student_name': student_name,
                            'student_email': student_email,
                            'roll_no': roll_no,
                            'department': department,
                            'speaker_name': speaker_name,
                            'venue_date': venue_date
                        }
                        
                        success, error_msg = call_apps_script(apps_script_url, payload)
                        
                        # 3. Update database with final result
                        if success:
                            cursor.execute('''
                                UPDATE job_queue 
                                SET status = 'completed', attempts = ?, error_message = NULL, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (attempts + 1, job_id))
                            job_logger.info(f"Certificate successfully generated & sent for student: {student_name} ({student_email})")
                        else:
                            new_attempts = attempts + 1
                            new_status = 'failed' if new_attempts >= 3 else 'pending'
                            cursor.execute('''
                                UPDATE job_queue 
                                SET status = ?, attempts = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (new_status, new_attempts, error_msg, job_id))
                            job_logger.warning(f"Failed attempt {new_attempts}/3 for job {job_id}: {error_msg}")
                            
                        conn.commit()
                        
                conn.close()
                time.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                job_logger.error(f"Job Worker Loop Error: {e}")
                time.sleep(10)

    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    _job_thread = worker_thread
    return worker_thread
