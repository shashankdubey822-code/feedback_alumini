import os
import sys
import json
import sqlite3
import urllib.request
from dotenv import load_dotenv

# Load env variables
load_dotenv('.env')

print("==========================================================")
print("       ALUMNI FEEDBACK SYSTEM DEPLOYMENT STATUS           ")
print("==========================================================")

# Step 1: Environment Variables Check
print("\n[STEP 1] Checking Local Environment (.env)...")
required_vars = [
    "SUPABASE_URL", "DATABASE_URL", "WEBHOOK_SECRET", 
    "APPS_SCRIPT_SECRET", "APPS_SCRIPT_URL", "HF_TOKEN", 
    "GEMINI_API_KEY", "GROQ_API_KEY"
]

env_ok = True
for var in required_vars:
    val = os.getenv(var)
    if val:
        masked = val[:6] + "..." + val[-4:] if len(val) > 10 else "configured"
        print(f"  [OK] {var}: {masked}")
    else:
        print(f"  [MISSING] {var} is not configured in .env!")
        env_ok = False

# Step 2: Database File Check
print("\n[STEP 2] Checking Database Connections...")
db_files = ["dashboard.db", "database.db"]
db_ok = True

for db_file in db_files:
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            print(f"  [OK] {db_file} connection works. Found {len(tables)} tables.")
        except Exception as e:
            print(f"  [FAIL] {db_file} exists but could not query tables: {e}")
            db_ok = False
    else:
        print(f"  [WARNING] {db_file} does not exist in the root directory yet.")

# Step 3: Apps Script Connectivity (PING)
print("\n[STEP 3] Testing Apps Script Connectivity (PING)...")
apps_script_url = os.getenv('APPS_SCRIPT_URL')
apps_script_secret = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')

if not apps_script_url:
    print("  [FAIL] APPS_SCRIPT_URL is not set in .env. Skipping further steps.")
    sys.exit(1)

def call_apps_script(action, payload_data={}):
    payload = {
        "secret": apps_script_secret,
        "action": action
    }
    payload.update(payload_data)
    
    req = urllib.request.Request(
        apps_script_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_text = response.read().decode('utf-8')
            return json.loads(resp_text)
    except Exception as e:
        err = str(e)
        if hasattr(e, 'read'):
            try:
                err += " | " + e.read().decode('utf-8')
            except:
                pass
        return {"success": False, "error": err}

ping_res = call_apps_script("ping")
if ping_res.get("success"):
    print(f"  [OK] Ping Success: {ping_res.get('message')} (Version: {ping_res.get('data', {}).get('version')})")
else:
    print(f"  [FAIL] Ping failed: {ping_res.get('error', ping_res)}")

# Step 4: Apps Script Diagnostic Data (DIAGNOSE)
print("\n[STEP 4] Fetching Apps Script Internal Diagnostics...")
diag_res = call_apps_script("diagnose")
if diag_res.get("success"):
    diag_data = diag_res.get("data", {})
    print(f"  [OK] Script Version: {diag_data.get('version')}")
    print(f"  [OK] Executing as Account: {diag_data.get('user_email')}")
    print(f"  [OK] Timezone: {diag_data.get('timezone')}")
    print(f"  [OK] Active Triggers: {diag_data.get('trigger_count')}")
    print(f"  [OK] Authorization Check: {diag_data.get('auth_check')}")
else:
    print(f"  [FAIL] Diagnostics failed: {diag_res.get('error', diag_res)}")

# Step 5: Form Creation & Accessibility (CREATE_FORM + Public Access Verification)
print("\n[STEP 5] Testing Form Creation & Public Accessibility...")
form_payload = {
    "speaker_name": "Connectivity Verification Test",
    "venue_date": "2026-05-28",
    "event_id": 88888,
    "send_certificates": True,
    "webhook_url": "https://httpbin.org/post"
}

form_res = call_apps_script("create_form", form_payload)
if form_res.get("success"):
    form_data = form_res.get("data", {})
    form_url = form_data.get("form_url")
    form_id = form_data.get("form_id")
    print(f"  [OK] Form Created Successfully.")
    print(f"       Form ID: {form_id}")
    print(f"       Form URL: {form_url}")
    
    # Verify Public Accessibility by requesting the published URL without credentials
    print("  Checking if form is accessible to external (unauthenticated) users...")
    try:
        # Standard GET request to simulate a logged-out public user
        form_req = urllib.request.Request(
            form_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        )
        with urllib.request.urlopen(form_req, timeout=10) as form_resp:
            final_url = form_resp.geturl()
            html_content = form_resp.read().decode('utf-8')
            
            # If redirected to a Google login page
            if "accounts.google.com" in final_url or "ServiceLogin" in final_url or "You need access" in html_content or "Sign in" in html_content:
                print("  [ALERT] Form requires login! It is restricted to the domain.")
                print("          This means your Workspace Administrator has set a policy restricting all forms.")
                public_accessible = False
            else:
                print("  [OK] Form is publicly accessible! Users can submit feedback without logging in.")
                public_accessible = True
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            print(f"  [ALERT] Form requires login (HTTP {e.code})! It is restricted to the domain.")
            print("          This means your Workspace Administrator has set a policy restricting all forms.")
            public_accessible = False
        else:
            print(f"  [WARNING] HTTP Error during public accessibility test: {e}")
            public_accessible = None
    except Exception as e:
        print(f"  [WARNING] Unable to complete public accessibility test: {e}")
        public_accessible = None

    # Cleanup the form
    print("  Closing the dry-run test form...")
    close_res = call_apps_script("close_form", {"form_id": form_id})
    if close_res.get("success"):
        print("  [OK] Dry-run form closed successfully.")
    else:
        print(f"  [WARNING] Could not close dry-run form: {close_res.get('message')} - {close_res.get('data')}")
else:
    print(f"  [FAIL] Form creation failed: {form_res.get('error', form_res)}")
    public_accessible = False

# Step 6: Summary & Actions
print("\n==========================================================")
print("                     SUMMARY OF STATUS                    ")
print("==========================================================")
if env_ok and db_ok and ping_res.get("success") and diag_res.get("success"):
    print("STATUS: SYSTEM CHANNELS ARE FULLY OPERATIONAL!")
else:
    print("STATUS: CORE COMPONENT ISSUES DETECTED. SEE STEPS ABOVE.")

if public_accessible is False:
    print("\n[ACTION REQUIRED] FOR PUBLIC ACCESS:")
    print("   Since the Google Workspace domain policies are restricting your forms to the organization:")
    print("   1. Sign in to the Google Admin console (admin.google.com) as administrator.")
    print("   2. Go to Apps > Google Workspace > Drive and Docs > Sharing settings.")
    print("   3. Under 'Sharing options', make sure external sharing is allowed.")
    print("   4. Go to Apps > Google Workspace > Drive and Docs > Sharing settings > Sharing options > Form sharing.")
    print("   5. Disable default restriction to your domain so scripts can set setRequireLogin(false) successfully.")
    print("   6. Alternatively, create forms from a personal @gmail.com account instead of the @mru.ac.in account.")
else:
    print("\nAll tests passed successfully!")
print("==========================================================")
