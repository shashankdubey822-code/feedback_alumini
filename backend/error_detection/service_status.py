"""
Service Status Monitor - Checks all service connections and availability
"""

import os
from typing import Dict, Tuple

class ServiceStatusMonitor:
    """Monitor status of all backend services"""

    def check_database_connection(self, db_path: str) -> Tuple[bool, str]:
        """Check database connectivity"""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True, "Database connected"
        except Exception as e:
            return False, f"Database error: {str(e)}"

    def check_google_apps_script_config(self) -> Tuple[bool, str]:
        """Check Google Apps Script configuration"""
        apps_script_url = os.getenv('APPS_SCRIPT_URL')
        apps_script_secret = os.getenv('APPS_SCRIPT_SECRET')

        issues = []
        if not apps_script_url:
            issues.append("APPS_SCRIPT_URL not configured")
        elif not apps_script_url.startswith('https://script.google.com'):
            issues.append("APPS_SCRIPT_URL format invalid")
        elif not apps_script_url.endswith('/exec'):
            issues.append("APPS_SCRIPT_URL must end with /exec")

        if not apps_script_secret:
            issues.append("APPS_SCRIPT_SECRET not configured")
        elif apps_script_secret == 'datalens2026':
            issues.append("Using default APPS_SCRIPT_SECRET (security risk)")

        if issues:
            return False, "; ".join(issues)
        return True, "Google Apps Script configured correctly"

    def check_environment_variables(self) -> Dict[str, dict]:
        """Check required environment variables"""
        required_vars = [
            'DATABASE_PATH',
            'ADMIN_PASSWORD',
            'APPS_SCRIPT_URL',
            'APPS_SCRIPT_SECRET',
            'WEBHOOK_SECRET'
        ]

        results = {}
        for var in required_vars:
            value = os.getenv(var)
            if value:
                # Don't show full value for security-sensitive vars
                display_value = f"***{value[-4:]}" if var.endswith('SECRET') else f"***{value[-10:]}"
                results[var] = {"status": "configured", "value": display_value}
            else:
                results[var] = {"status": "missing"}

        return results

    def check_file_permissions(self, db_path: str) -> Dict[str, dict]:
        """Check critical file permissions"""
        files_to_check = [
            db_path,
            "logs",
            "backend",
            "frontend"
        ]

        results = {}
        for file_path in files_to_check:
            try:
                if not os.path.exists(file_path):
                    results[file_path] = {"status": "not_found"}
                elif os.path.isfile(file_path):
                    readable = os.access(file_path, os.R_OK)
                    writable = os.access(file_path, os.W_OK)
                    results[file_path] = {
                        "status": "file",
                        "readable": readable,
                        "writable": writable
                    }
                else:  # directory
                    readable = os.access(file_path, os.R_OK)
                    writable = os.access(file_path, os.W_OK)
                    results[file_path] = {
                        "status": "directory",
                        "readable": readable,
                        "writable": writable
                    }
            except Exception as e:
                results[file_path] = {"status": "error", "message": str(e)}

        return results

    def full_status_check(self, db_path: str) -> Dict:
        """Run comprehensive service status check"""
        db_ok, db_msg = self.check_database_connection(db_path)
        gas_ok, gas_msg = self.check_google_apps_script_config()
        env_vars = self.check_environment_variables()
        file_perms = self.check_file_permissions(db_path)

        issues = []
        if not db_ok:
            issues.append(f"Database: {db_msg}")
        if not gas_ok:
            issues.append(f"Google Apps Script: {gas_msg}")

        return {
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "database": {
                "status": "OK" if db_ok else "ERROR",
                "message": db_msg
            },
            "google_apps_script": {
                "status": "OK" if gas_ok else "ERROR",
                "message": gas_msg
            },
            "environment_variables": env_vars,
            "file_permissions": file_perms,
            "overall_status": "OK" if not issues else "ISSUES",
            "critical_issues": issues
        }
