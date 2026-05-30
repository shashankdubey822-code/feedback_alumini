"""
Webhook Error Detector — token config, sync health, duplicate detection.
"""
from __future__ import annotations
import os
import json
from typing import List
from ..base import ErrorDetector, DetectionResult

SYNC_HEALTH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '..', '..', 'logs', 'sync_health.json')


class WebhookErrorDetector(ErrorDetector):
    page = "webhook"

    def run(self) -> List[DetectionResult]:
        results = []

        # 1. Webhook secret configured
        secret = os.getenv("WEBHOOK_SECRET", "")
        if not secret or secret in ("changeme", "your-secret", ""):
            results.append(self._warn("webhook_secret",
                "WEBHOOK_SECRET is default or unset",
                "Webhook endpoint is insecure"))
        else:
            results.append(self._ok("webhook_secret", "WEBHOOK_SECRET is configured"))

        # 2. PUBLIC_URL set (needed for Google Form webhook URL generation)
        public_url = os.getenv("PUBLIC_URL", "")
        space_id = os.getenv("SPACE_ID", "")
        if space_id and not public_url:
            results.append(self._warn("public_url",
                "Running on Hugging Face but PUBLIC_URL is not set",
                "Generated webhook URLs may be unreachable"))
        elif public_url:
            results.append(self._ok("public_url", f"PUBLIC_URL configured: {public_url}"))
        else:
            results.append(self._ok("public_url", "Not on HF Spaces — PUBLIC_URL not required"))

        # 3. Sync health file
        try:
            health_path = os.path.normpath(SYNC_HEALTH_PATH)
            if os.path.exists(health_path):
                with open(health_path) as f:
                    health = json.load(f)
                last_error = health.get("last_error")
                if last_error:
                    results.append(self._warn("sync_health",
                        f"Last sync error: {last_error}",
                        "Check logs/sync_health.json for details"))
                else:
                    results.append(self._ok("sync_health", "Sync health file shows no errors"))
            else:
                results.append(self._ok("sync_health", "No sync_health.json yet (normal on first run)"))
        except Exception as e:
            results.append(self._warn("sync_health", "Could not read sync_health.json", str(e)))

        # 4. Admin secret configured
        admin_secret = os.getenv("ADMIN_SECRET", "")
        if not admin_secret or admin_secret in ("admin", "password", "changeme", ""):
            results.append(self._warn("admin_secret",
                "ADMIN_SECRET is weak or unset",
                "Admin panel is insecure"))
        else:
            results.append(self._ok("admin_secret", "ADMIN_SECRET is configured"))

        return results
