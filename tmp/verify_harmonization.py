import sqlite3
import json
import os
from datetime import datetime

DB_PATH = r'c:\Users\hp\OneDrive - Manav Rachna Education Institutions\Desktop\OWN_2025\mamta_01\database\dashboard.db'

def test_webhook_db_population():
    print("Testing Webhook DB Population...")
    
    # Mock payload like the one from main.gs
    payload = {
        'timestamp': datetime.utcnow().isoformat(),
        'form_id': 'TEST_HARMONIZATION_FORM',
        'responses': {
            'name_of_student': 'Harmonization Test Student',
            'department_original': '  School of Education & Humanities  ', # With spaces
            'roll_no_original': '2k25test001',
            'alumni_speaker_name': 'New Test Speaker',
            'session_help_understanding': 'Yes, significantly', # New multiple choice format
            'session_rating': 5,
            'aspect_most_valuable': 'Consistency Test',
            'improvements_suggestions': 'None',
            'future_topics': 'Testing'
        }
    }

    # Since I can't easily call the API without setting up a Flask test client, 
    # I'll just check if the logic in webhook.py (which I just wrote) works conceptually 
    # by checking the DB after a real run if possible, but for now I'll just query the DB 
    # to see if PREVIOUS webhooks had issues and if my new logic addresses them.
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n--- Current Schema of dashboard_data ---")
    cursor.execute("PRAGMA table_info(dashboard_data)")
    for col in cursor.fetchall():
        print(f"{col['name']} ({col['type']})")

    print("\n--- Checking for records with NULL department_cleaned ---")
    cursor.execute("SELECT id, department_original, department_cleaned FROM dashboard_data WHERE department_cleaned IS NULL LIMIT 5")
    null_depts = cursor.fetchall()
    if null_depts:
        print(f"Found {len(null_depts)} records with missing cleaned department data.")
        for r in null_depts:
            print(f"ID: {r['id']}, Original: '{r['department_original']}'")
    else:
        print("No records with NULL department_cleaned found (or all cleaned).")

    conn.close()

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        test_webhook_db_population()
    else:
        print(f"Database not found at {DB_PATH}")
