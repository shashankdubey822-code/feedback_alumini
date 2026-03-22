import os
import sys
import json
import sqlite3
import requests
from datetime import datetime

# Add the parent directory to the path so we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_env():
    print("🔍 Step 1: Checking Environment Variables...")
    public_url = os.environ.get('PUBLIC_URL')
    webhook_secret = os.getenv('WEBHOOK_SECRET')
    
    if not public_url:
        print("❌ Error: PUBLIC_URL is not set in Hugging Face Settings.")
    else:
        print(f"✅ PUBLIC_URL is set: {public_url}")
        
    if not webhook_secret:
        print("⚠️ Warning: WEBHOOK_SECRET is not set (using default). Recommend setting to 'datalens2026'.")
    else:
        print(f"✅ WEBHOOK_SECRET is set correctly.")

def check_db():
    print("\n🔍 Step 2: Checking Database Integrity...")
    db_path = 'database/dashboard.db'
    if not os.path.exists(db_path):
        print(f"❌ Error: Database not found at {db_path}")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_data'")
        if not cursor.fetchone():
            print("❌ Error: 'dashboard_data' table is missing.")
        else:
            print("✅ Database table exists.")
        conn.close()
    except Exception as e:
        print(f"❌ Database Error: {e}")

def check_server_live():
    print("\n🔍 Step 3: Checking Live Server Endpoints...")
    local_url = "http://127.0.0.1:7860/api/v1/webhook/notifications"
    try:
        res = requests.get(local_url, timeout=5)
        if res.status_code == 200:
            print("✅ Server is LIVE and updated (Notification route exists).")
        elif res.status_code == 404:
            print("❌ ERROR: Server is running OLD code. Please RESTART your Space in Hugging Face.")
        else:
            print(f"⚠️ Server returned unexpected status: {res.status_code}")
    except Exception as e:
        print(f"❌ Connection Error: Could not reach local server: {e}")

if __name__ == "__main__":
    print("==========================================")
    print("   MONSTER SYNC SETUP - DIAGNOSTIC TOOL   ")
    print("==========================================")
    check_env()
    check_db()
    check_server_live()
    print("==========================================")
