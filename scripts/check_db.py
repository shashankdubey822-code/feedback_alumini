import sqlite3
import os

db_path = 'database/dashboard.db'
if not os.path.exists(db_path):
    # Try current dir
    db_path = 'dashboard.db'

print(f"Checking DB: {db_path}")
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check dashboard_data
        print("\n--- dashboard_data ---")
        cursor.execute("PRAGMA table_info(dashboard_data);")
        for col in cursor.fetchall():
            print(col)
            
        # Check events
        print("\n--- events ---")
        cursor.execute("PRAGMA table_info(events);")
        for col in cursor.fetchall():
            print(col)
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Database file NOT found!")
