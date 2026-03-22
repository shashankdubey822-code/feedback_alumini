"""
POST a test payload to /api/v1/webhook/forms/submit to verify Bearer auth and DB insert.

Usage (local):
  python scripts/test_sync.py

Hugging Face Space:
  set BASE_URL and WEBHOOK_SECRET, then:
  python scripts/test_sync.py --url https://your-space.hf.space --secret your-webhook-secret

Exit code 0 on HTTP 200, 1 otherwise.
"""
import argparse
import os
import sys
from datetime import datetime

import requests

WEBHOOK_PATH = "/api/v1/webhook/forms/submit"


def build_parser():
    p = argparse.ArgumentParser(description="Test webhook autosync endpoint (Bearer + JSON).")
    p.add_argument(
        "--url",
        default=os.getenv("BASE_URL") or os.getenv("PUBLIC_URL") or "http://127.0.0.1:7860",
        help="Base URL of the app (no path). Env: BASE_URL or PUBLIC_URL",
    )
    p.add_argument(
        "--secret",
        default=os.getenv("WEBHOOK_SECRET", "webhook-secret-key"),
        help="Must match backend WEBHOOK_SECRET and Apps Script WEBHOOK_SECRET. Env: WEBHOOK_SECRET",
    )
    p.add_argument("--name", default="AutosyncTest", help="Test student name in payload")
    return p


def simulate_submission(base_url: str, secret: str, name: str) -> bool:
    url = f"{base_url.rstrip('/')}{WEBHOOK_PATH}"
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
    }

    payload = {
        "timestamp": datetime.now().isoformat(),
        "form_id": "TEST_AUTO_SYNC",
        "responses": {
            "name_of_student": name,
            "department_original": "Computer Science",
            "roll_no_original": "CS101",
            "alumni_speaker_name": "Dr. Mamta",
            "date_of_lecture": "2026-03-22",
            "session_rating": 5,
            "aspect_most_valuable": "Sync logic test",
            "future_topics": "AI Automation",
        },
    }

    print(f"POST {url}")
    print(f"Authorization: Bearer <len={len(secret)}>")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text[:800]}")
        if response.status_code == 401:
            print("Hint: 401 = WEBHOOK_SECRET mismatch between this script and the server.")
        elif response.status_code != 200:
            print("Hint: Check server logs and database; see env.example for PUBLIC_URL on HF.")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def check_notifications(base_url: str):
    url = f"{base_url.rstrip('/')}/api/v1/webhook/notifications"
    print(f"\nGET {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Data: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    args = build_parser().parse_args()
    ok = simulate_submission(args.url, args.secret, args.name)
    if ok:
        check_notifications(args.url)
        print("\nOK: Webhook accepted the request (200).")
        sys.exit(0)
    print("\nFAIL: Webhook did not return 200. See logs/sync_health.json on the server if available.")
    sys.exit(1)


if __name__ == "__main__":
    main()
