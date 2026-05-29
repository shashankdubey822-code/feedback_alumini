"""
job_worker.py — Background certificate generation worker.
Uses native Supabase PostgreSQL via supabase_db.py.
Table: certificate_jobs (was: job_queue)
"""

import threading
import time
import json
import urllib.request
import urllib.error
from backend.config import get_config
from backend.utils.logger import get_section_logger
from backend.utils.supabase_db import get_db

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
                        # Fetch pending jobs (JOIN events to get template/speaker info)
                        cur.execute("""
                            SELECT
                                j.id, j.student_name, j.student_email,
                                j.roll_no, j.department, j.event_id, j.attempts,
                                e.template_id, e.speaker_name, e.venue_date
                            FROM certificate_jobs j
                            JOIN events e ON j.event_id = e.id
                            WHERE j.status = 'pending' AND j.attempts < 3
                            ORDER BY j.created_at ASC
                            LIMIT 5
                        """)
                        jobs = cur.fetchall()

                        if not jobs:
                            time.sleep(5)
                            continue

                        job_logger.info(f"Processing {len(jobs)} pending certificate job(s)...")

                        for job in jobs:
                            job_id        = job['id']
                            student_name  = job['student_name']
                            student_email = job['student_email']
                            roll_no       = job['roll_no'] or ''
                            department    = job['department'] or ''
                            template_id   = job['template_id']
                            speaker_name  = job['speaker_name'] or ''
                            venue_date    = str(job['venue_date']) if job['venue_date'] else ''
                            attempts      = job['attempts']

                            # Mark as processing to prevent concurrent pickup
                            cur.execute("""
                                UPDATE certificate_jobs
                                SET status = 'processing', updated_at = NOW()
                                WHERE id = %s
                            """, (job_id,))
                            conn.commit()

                            if not template_id:
                                cur.execute("""
                                    UPDATE certificate_jobs
                                    SET status = 'failed', attempts = %s,
                                        error_message = %s, updated_at = NOW()
                                    WHERE id = %s
                                """, (attempts + 1,
                                      'No Google Slides template configured for this event.',
                                      job_id))
                                conn.commit()
                                continue

                            payload = {
                                'secret':         apps_script_secret,
                                'action':         'generate_certificate',
                                'template_id':    template_id,
                                'student_name':   student_name,
                                'student_email':  student_email,
                                'roll_no':        roll_no,
                                'department':     department,
                                'speaker_name':   speaker_name,
                                'venue_date':     venue_date,
                            }

                            success, error_msg = call_apps_script(apps_script_url, payload)

                            if success:
                                cur.execute("""
                                    UPDATE certificate_jobs
                                    SET status = 'completed', attempts = %s,
                                        error_message = NULL, updated_at = NOW()
                                    WHERE id = %s
                                """, (attempts + 1, job_id))
                                job_logger.info(
                                    f"Certificate sent: {student_name} ({student_email})"
                                )
                            else:
                                new_attempts = attempts + 1
                                new_status   = 'failed' if new_attempts >= 3 else 'pending'
                                cur.execute("""
                                    UPDATE certificate_jobs
                                    SET status = %s, attempts = %s,
                                        error_message = %s, updated_at = NOW()
                                    WHERE id = %s
                                """, (new_status, new_attempts, error_msg, job_id))
                                job_logger.warning(
                                    f"Job {job_id} attempt {new_attempts}/3 failed: {error_msg}"
                                )
                            conn.commit()

                time.sleep(5)

            except Exception as e:
                job_logger.error(f"Job Worker Loop Error: {e}")
                time.sleep(10)

    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    _job_thread = worker_thread
    return worker_thread
