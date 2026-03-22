"""
Comprehensive Diagnostics Service for Alumni Feedback System
Handles connectivity checks, schema validation, and health reporting.
"""

import os
import sqlite3
import json
import urllib.request
import time
from datetime import datetime
from backend.utils.logger import get_logger

logger = get_logger(__name__)

class DiagnosticsService:
    def __init__(self, config):
        self.config = config
        self.db_path = config.get('DATABASE_PATH', 'database/dashboard.db')
        self.apps_script_url = os.getenv('APPS_SCRIPT_URL')
        self.apps_script_secret = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')
        self.webhook_secret = config.get('WEBHOOK_SECRET', 'webhook-secret-key')

    def check_database(self):
        """Validate database existence and schema."""
        try:
            if not os.path.exists(self.db_path):
                return {'status': 'error', 'message': f'Database file not found at {self.db_path}'}

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check main tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_data'")
            if not cursor.fetchone():
                return {'status': 'error', 'message': 'Table dashboard_data is missing.'}
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            if not cursor.fetchone():
                return {'status': 'error', 'message': 'Table events is missing.'}
            
            # Check for NLP columns
            cursor.execute("PRAGMA table_info(dashboard_data)")
            cols = [row[1] for row in cursor.fetchall()]
            has_nlp = "dl_processed" in cols
            
            cursor.execute("SELECT COUNT(*) FROM dashboard_data")
            total_rows = cursor.fetchone()[0]
            
            conn.close()
            return {
                'status': 'ok',
                'rows': total_rows,
                'nlp_ready': has_nlp,
                'path': self.db_path
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def check_apps_script(self):
        """Validate communication with Google Apps Script."""
        if not self.apps_script_url:
            return {'status': 'error', 'message': 'APPS_SCRIPT_URL not configured.'}
        
        try:
            payload = {
                'secret': self.apps_script_secret,
                'action': 'ping'
            }
            
            start_time = time.time()
            req = urllib.request.Request(
                self.apps_script_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=15) as response:
                response_text = response.read().decode('utf-8')
                result = json.loads(response_text)
                latency = round((time.time() - start_time) * 1000, 2)
                
                if result.get('success'):
                    return {
                        'status': 'ok',
                        'version': result.get('v', 'unknown'),
                        'latency_ms': latency,
                        'message': result.get('message', 'Active')
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f"Script Error: {result.get('message', 'Unknown error')}"
                    }
        except Exception as e:
            return {'status': 'error', 'message': f"Connection Failed: {str(e)}"}

    def check_webhook_connectivity(self, request_host_url):
        """Verify if the webhook URL is correctly formed and reachable."""
        try:
            base_url = os.environ.get('PUBLIC_URL') or request_host_url
            webhook_url = base_url.rstrip('/') + '/api/v1/webhook/forms/submit'
            
            # Check if using localhost on a public environment
            if '127.0.0.1' in webhook_url or 'localhost' in webhook_url:
                if os.getenv('HF_SPACE_ID'):
                    return {'status': 'warning', 'message': 'Webhook uses localhost in a cloud env. Sync will fail.', 'url': webhook_url}
            
            return {
                'status': 'ok',
                'url': webhook_url,
                'secret_configured': self.webhook_secret != 'webhook-secret-key'
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_webhook_history(self):
        """Read recent webhook hits from sync_health and logs."""
        history = {
            'last_sync': None,
            'last_heartbeat': None,
            'success_count': 0,
            'error_count': 0,
            'recent_events': []
        }
        
        # Read sync_health.json
        health_path = 'logs/sync_health.json'
        if os.path.exists(health_path):
            try:
                with open(health_path, 'r') as f:
                    data = json.load(f)
                    history['last_sync'] = data.get('last_sync')
                    history['last_heartbeat'] = data.get('last_heartbeat')
                    history['success_count'] = data.get('success_count', 0)
                    history['error_count'] = data.get('error_count', 0)
            except: pass

        # Read latest webhook errors/hits
        webhook_log = 'logs/webhook_errors.log'
        if os.path.exists(webhook_log):
            try:
                with open(webhook_log, 'r') as f:
                    # Get last 5 lines
                    lines = f.readlines()[-5:]
                    history['recent_events'] = [l.strip() for l in lines]
            except: pass
            
        return history

    def check_endpoints(self, request_host_url):
        """Check if all key API endpoints are responsive. Tries public URL and localhost fallback."""
        endpoints = [
            '/api/data',
            '/api/v1/admin/events',
            '/api/v1/diagnostics/health'
        ]
        results = {}
        for ep in endpoints:
            status = 'error'
            msg = 'Connection failed'
            
            # Try 1: request_host_url (provided by frontend)
            try:
                url = request_host_url.rstrip('/') + ep
                req = urllib.request.Request(url, method='GET')
                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200:
                        results[ep] = {'status': 'ok', 'code': 200}
                        continue
            except Exception as e:
                msg = f"Host URL failed: {str(e)}"

            # Try 2: localhost (for internal container checks)
            try:
                port = os.getenv('PORT', '7860')
                url = f"http://127.0.0.1:{port}" + ep
                req = urllib.request.Request(url, method='GET')
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        results[ep] = {'status': 'ok', 'code': 200, 'via': 'localhost'}
                        continue
            except Exception as e:
                msg += f" | Localhost fallback failed: {str(e)}"
            
            results[ep] = {'status': 'error', 'message': msg}
            
        return results

    def perform_full_checkup(self, request_host_url):
        """Run all diagnostic checks."""
        start_time = datetime.now()
        
        db_check = self.check_database()
        apps_script_check = self.check_apps_script()
        webhook_check = self.check_webhook_connectivity(request_host_url)
        webhook_history = self.get_webhook_history()
        endpoints_check = self.check_endpoints(request_host_url)
        
        # Check logs for recent errors
        logs_dir = 'logs'
        error_logs = []
        if os.path.exists(logs_dir):
            for f in os.listdir(logs_dir):
                if f.endswith('_errors.log'):
                    path = os.path.join(logs_dir, f)
                    if os.path.getsize(path) > 0:
                        error_logs.append(f)

        is_healthy = (
            db_check['status'] == 'ok' and 
            apps_script_check['status'] == 'ok' and 
            webhook_check['status'] == 'ok'
        )

        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'execution_time_ms': round((datetime.now() - start_time).total_seconds() * 1000),
            'healthy': is_healthy,
            'checks': {
                'database': db_check,
                'apps_script': apps_script_check,
                'webhook': webhook_check,
                'webhook_history': webhook_history,
                'endpoints': endpoints_check,
                'logs': {'active_errors': error_logs}
            }
        }
