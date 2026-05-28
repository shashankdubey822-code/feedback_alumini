import os
import sqlite3
from typing import List
from datetime import datetime
from backend.error_detection.base import ErrorDetector, DetectionResult
from backend.utils.db_helper import get_db_connection

class CertificationErrorDetector(ErrorDetector):
    """
    Ultra-deep analysis for the certification pipeline.
    Checks for:
    1. Active events with missing template IDs.
    2. Jobs stuck in processing.
    3. Failed jobs.
    4. Jobs with missing emails.
    5. Missing Apps Script configuration.
    """
    page = "certification"

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self) -> List[DetectionResult]:
        results = []
        try:
            conn = get_db_connection(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            results.extend(self._analyze_template_configuration(cursor))
            
            # Ensure job_queue exists before querying
            cursor.execute("PRAGMA table_info(job_queue)")
            if cursor.fetchall():
                results.extend(self._analyze_failed_jobs(cursor))
                results.extend(self._analyze_stuck_jobs(cursor))
                results.extend(self._analyze_missing_emails(cursor))
            
            conn.close()
        except Exception as e:
            results.append(self._critical("db_connection", f"Certification DB Error: {str(e)}"))

        results.extend(self._analyze_apps_script_connectivity())
        
        # If no critical or warning errors were added for a category, add OK results
        if not any(r for r in results if r.check == "template_config" and not r.ok):
            results.append(self._ok("template_config", "All active events have valid templates."))
            
        if not any(r for r in results if r.check == "failed_jobs" and not r.ok):
            results.append(self._ok("failed_jobs", "No failed certificate jobs found."))
            
        if not any(r for r in results if r.check == "stuck_jobs" and not r.ok):
            results.append(self._ok("stuck_jobs", "No stuck certificate jobs found."))

        return results

    def _analyze_template_configuration(self, cursor) -> List[DetectionResult]:
        results = []
        cursor.execute('''
            SELECT id, speaker_name, template_id 
            FROM events 
            WHERE send_certificates = 1 
            AND (template_id IS NULL OR template_id = '')
        ''')
        events = cursor.fetchall()
        for ev in events:
            results.append(self._critical(
                "template_config", 
                f"Event #{ev['id']} ({ev['speaker_name']}) has certificates active but NO template ID.",
                "Please edit the event and paste a valid Google Slides Template ID."
            ))
        return results

    def _analyze_failed_jobs(self, cursor) -> List[DetectionResult]:
        results = []
        cursor.execute('''
            SELECT j.id, j.student_name, j.student_email, j.error_message, e.speaker_name
            FROM job_queue j
            LEFT JOIN events e ON j.event_id = e.id
            WHERE j.status = 'failed'
        ''')
        jobs = cursor.fetchall()
        for job in jobs:
            msg = job['error_message'] or 'Unknown error'
            results.append(self._critical(
                "failed_jobs",
                f"Certificate generation failed for {job['student_name']} ({job['student_email']}).",
                f"Event: {job['speaker_name']}. Error: {msg}"
            ))
        return results

    def _analyze_stuck_jobs(self, cursor) -> List[DetectionResult]:
        results = []
        cursor.execute('''
            SELECT j.id, j.student_name, j.updated_at
            FROM job_queue j
            WHERE j.status = 'processing'
        ''')
        jobs = cursor.fetchall()
        now = datetime.utcnow()
        for job in jobs:
            try:
                updated_at_str = job['updated_at']
                if "T" in updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")
                    
                age_minutes = (now - updated_at).total_seconds() / 60
                if age_minutes > 15:
                    results.append(self._warn(
                        "stuck_jobs",
                        f"Job #{job['id']} for {job['student_name']} is stuck in 'processing' state.",
                        f"Stuck for {age_minutes:.1f} minutes. Consider resetting the status to 'pending'."
                    ))
            except Exception as e:
                pass # Ignore parsing errors for individual jobs
        return results

    def _analyze_missing_emails(self, cursor) -> List[DetectionResult]:
        results = []
        cursor.execute('''
            SELECT id, student_name, status
            FROM job_queue 
            WHERE (student_email IS NULL OR student_email = '') AND status != 'completed'
        ''')
        jobs = cursor.fetchall()
        for job in jobs:
            results.append(self._warn(
                "missing_email",
                f"Job #{job['id']} ({job['student_name']}) has no email address.",
                "The certificate cannot be delivered without an email."
            ))
        return results

    def _analyze_apps_script_connectivity(self) -> List[DetectionResult]:
        results = []
        url = os.getenv('APPS_SCRIPT_URL')
        if not url:
            results.append(self._critical(
                "apps_script_config",
                "APPS_SCRIPT_URL is missing from environment/config.",
                "Certificate generation cannot proceed without the Apps Script webhook."
            ))
        else:
            results.append(self._ok("apps_script_config", "APPS_SCRIPT_URL is configured."))
        return results
