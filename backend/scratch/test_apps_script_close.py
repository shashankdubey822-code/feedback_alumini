import sqlite3, os, json, urllib.request
from dotenv import load_dotenv
load_dotenv('.env')

conn = sqlite3.connect('dashboard.db')
cursor = conn.cursor()
cursor.execute('SELECT form_id FROM events WHERE form_id IS NOT NULL ORDER BY id DESC LIMIT 1;')
row = cursor.fetchone()
if not row:
    print('No forms found in DB')
    exit()

form_id = row[0]
print(f'Found Form ID: {form_id}')

APPS_SCRIPT_URL = os.getenv('APPS_SCRIPT_URL')
APPS_SCRIPT_SECRET = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')

payload = {'secret': APPS_SCRIPT_SECRET, 'action': 'close_form', 'form_id': form_id}

req = urllib.request.Request(
    APPS_SCRIPT_URL,
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        print(f'Status: {response.status}')
        resp_text = response.read().decode('utf-8')
        print(f'Response: {resp_text}')
except Exception as e:
    print(e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
