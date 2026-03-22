import requests
import json
import os
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:7860"  # Assuming local Flask port
WEBHOOK_PATH = "/api/v1/webhook/forms/submit"
SECRET = "webhook-secret-key"  # Default secret from backend/config.py

def simulate_submission(name):
    url = f"{BASE_URL}{WEBHOOK_PATH}"
    headers = {
        "Authorization": f"Bearer {SECRET}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "action": "form_submit",
        "timestamp": datetime.now().isoformat(),
        "form_id": "TEST_AUTO_SYNC",
        "name_of_student": name,
        "department_original": "Computer Science",
        "roll_no_original": "CS101",
        "responses": {
            "name_of_student": name,
            "alumni_speaker_name": "Dr. Mamta",
            "session_rating": 5,
            "aspect_most_valuable": "Sync logic test",
            "future_topics": "AI Automation"
        }
    }
    
    print(f"--- Simulating submission for: {name} ---")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def check_notifications():
    url = f"{BASE_URL}/api/v1/webhook/notifications"
    print(f"--- Checking for notifications ---")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Data: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if simulate_submission("Shashank"):
        print("\n✅ Webhook Backend accepted the data.")
        check_notifications()
        print("\n✅ Notification queue cleared. Now check the dashboard for the toast!")
    else:
        print("\n❌ Webhook Backend REJECTED the data. Check logs/sync_health.json.")
