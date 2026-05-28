import os
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv

# Load env variables
load_dotenv('.env')

APPS_SCRIPT_URL = os.getenv('APPS_SCRIPT_URL')
APPS_SCRIPT_SECRET = os.getenv('APPS_SCRIPT_SECRET', 'datalens2026')

print("==================================================")
print("GOOGLE APPS SCRIPT CONNECTIVITY & DIAGNOSTIC TEST")
print("==================================================")
print(f"Target URL: {APPS_SCRIPT_URL}")
print(f"Secret Key: {APPS_SCRIPT_SECRET}")
print("--------------------------------------------------")

def send_request(action, additional_payload={}):
    payload = {
        "secret": APPS_SCRIPT_SECRET,
        "action": action
    }
    payload.update(additional_payload)
    
    req = urllib.request.Request(
        APPS_SCRIPT_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        # Apps script responds with a redirect, urllib.request follows it automatically
        with urllib.request.urlopen(req, timeout=20) as response:
            status = response.status
            resp_text = response.read().decode('utf-8')
            return {
                "success": True,
                "status_code": status,
                "body": json.loads(resp_text) if resp_text else None,
                "raw_body": resp_text
            }
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, 'read'):
            try:
                err_msg += " | Response: " + e.read().decode('utf-8')
            except:
                pass
        return {
            "success": False,
            "error": err_msg
        }

# Test 1: Ping Action
print("\n[TEST 1] Sending Action: PING...")
ping_res = send_request("ping")
if ping_res["success"]:
    print(f"[OK] Success! Response: {json.dumps(ping_res['body'], indent=2)}")
else:
    print(f"[FAIL] Failed to Ping: {ping_res['error']}")

# Test 2: Diagnose Action
print("\n[TEST 2] Sending Action: DIAGNOSE...")
diag_res = send_request("diagnose")
if diag_res["success"]:
    print(f"[OK] Success! Diagnostic Data:\n{json.dumps(diag_res['body'], indent=2)}")
else:
    print(f"[FAIL] Failed to Diagnose: {diag_res['error']}")

# Test 3: Create Form (Dry-Run / Test Form)
print("\n[TEST 3] Testing Action: CREATE_FORM (Dry-Run Form)...")
form_payload = {
    "speaker_name": "Test Speaker Connectivity Check",
    "venue_date": "2026-05-28",
    "event_id": 99999,
    "send_certificates": True,
    "webhook_url": "https://httpbin.org/post"  # Dummy webhook
}
form_res = send_request("create_form", form_payload)
if form_res["success"]:
    body = form_res['body']
    print(f"[OK] Success! Form Response:\n{json.dumps(body, indent=2)}")
    if body.get("success") and "data" in body:
        form_url = body["data"].get("form_url")
        form_id = body["data"].get("form_id")
        print(f"\nCreated Form URL: {form_url}")
        print(f"Created Form ID: {form_id}")
        
        # Test 4: Close the dummy form we just created
        print(f"\n[TEST 4] Cleaning up dummy form (Action: CLOSE_FORM)...")
        close_res = send_request("close_form", {"form_id": form_id})
        if close_res["success"]:
            print(f"[OK] Success! Form Closed Response: {json.dumps(close_res['body'], indent=2)}")
        else:
            print(f"[FAIL] Failed to close form: {close_res['error']}")
else:
    print(f"[FAIL] Failed to Create Form: {form_res['error']}")

print("\n==================================================")
print("DIAGNOSTIC TEST COMPLETE")
print("==================================================")
