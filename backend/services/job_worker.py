"""
job_worker.py — Background certificate generation worker.
Uses native InsForge PostgreSQL via insforge_db.py.
Table: certificate_jobs (was: job_queue)
"""

import threading
import time
import json
import urllib.request
import urllib.error
import re
from datetime import datetime
from backend.config import get_config
from backend.utils.logger import get_section_logger
from backend.utils.insforge_db import get_db
from backend.utils.insforge_db import api_update

_job_thread = None


def start_job_worker(logger_unused=None):
    """Start the background certificate generation worker thread."""
    global _job_thread
    job_logger = get_section_logger('job_worker')
    config = get_config()()
    apps_script_url = config.APPS_SCRIPT_URL
    apps_script_secret = getattr(config, 'APPS_SCRIPT_SECRET', None) or 'datalens2026'

    def call_apps_script(url, payload):
        if not url:
            return False, "APPS_SCRIPT_URL not configured in .env"
        retry_delays = [2, 5, 10]
        for attempt, delay in enumerate(retry_delays):
            try:
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(
                    url, data=data,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    resp_data = json.loads(resp.read().decode('utf-8'))
                    if resp_data.get('success'):
                        return True, None
                    msg = resp_data.get('message', 'Unknown error')
                    details = resp_data.get('data', '')
                    return False, f"{msg}: {details}" if details else msg
            except urllib.error.HTTPError as e:
                body = e.read().decode('utf-8') if e.fp else ''
                err = f"HTTP {e.code}: {body}"
                if attempt < len(retry_delays) - 1:
                    time.sleep(delay)
                    continue
                return False, err
            except urllib.error.URLError as e:
                err = f"Connection failed: {e.reason}"
                if attempt < len(retry_delays) - 1:
                    time.sleep(delay)
                    continue
                return False, err
            except json.JSONDecodeError:
                return False, "Invalid JSON response from Apps Script"
            except Exception as e:
                return False, f"Unexpected error: {e}"
        return False, "Max retries exceeded"

    def worker_loop():
        job_logger.info("Certificate Job Worker Thread Started.")

        while True:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        # Fetch pending jobs (JOIN feedback_responses, students, events)
                        cur.execute("""
                            SELECT
                                j.id, 
                                s.name AS student_name, 
                                s.email AS student_email,
                                s.roll_no, 
                                e.department, 
                                e.template_id, 
                                e.speaker_name, 
                                e.venue_date
                            FROM certificate_jobs j
                            JOIN students s ON j.student_id = s.id
                            JOIN events e ON j.event_id = e.id
                            WHERE j.status = 'pending'
                            ORDER BY j.created_at ASC
                            LIMIT 5
                        """)
                        jobs = cur.fetchall()

                if not jobs:
                    time.sleep(5)
                    continue

                job_logger.info(f"Processing {len(jobs)} pending certificate job(s)...")

                for job in jobs:
                    job_id = job['id']
                    student_name = job['student_name']
                    student_email = job['student_email']
                    roll_no = job['roll_no'] or ''
                    department = job['department'] or ''
                    template_id = job['template_id']
                    speaker_name = job['speaker_name'] or ''
                    venue_date = str(job['venue_date']) if job['venue_date'] else ''

                    if template_id:
                        match = re.search(r'/d/([a-zA-Z0-9-_]+)', template_id)
                        if match:
                            template_id = match.group(1)

                    # Mark as processing to prevent concurrent pickup
                    api_update('certificate_jobs', 'id', job_id, {'status': 'processing'})

                    if not template_id:
                        api_update('certificate_jobs', 'id', job_id, {
                            'status': 'failed',
                            'error_log': 'No template configured for event'
                        })
                        continue

                    payload = {
                        'secret': apps_script_secret,
                        'action': 'generate_certificate',
                        'template_id': template_id,
                        'student_name': student_name,
                        'student_email': student_email,
                        'roll_no': roll_no,
                        'department': department,
                        'speaker_name': speaker_name,
                        'venue_date': venue_date,
                    }

                    success, error = call_apps_script(apps_script_url, payload)

                    if success:
                        api_update('certificate_jobs', 'id', job_id, {
                            'status': 'completed',
                            'error_log': None,
                            'generated_at': datetime.now().isoformat()
                        })
                        job_logger.info(
                            f"Certificate sent: {student_name} ({student_email})"
                        )
                    else:
                        api_update('certificate_jobs', 'id', job_id, {
                            'status': 'failed',
                            'error_log': str(error)
                        })
                        job_logger.error(
                            f"Certificate generation failed for {student_name}: {error}"
                        )

                time.sleep(5)

            except Exception as e:
                job_logger.error(f"Job Worker Loop Error: {e}")
                time.sleep(10)

    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    _job_thread = worker_thread
    return worker_thread
