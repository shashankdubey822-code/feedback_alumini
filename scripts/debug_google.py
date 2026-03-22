import os
import json
import urllib.request
import urllib.error

print("=== Google Apps Script Debugger ===")

script_url = os.getenv("APPS_SCRIPT_URL", None)
if not script_url:
    # try reading .env manually
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("APPS_SCRIPT_URL="):
                    script_url = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass

print(f"1. APPS_SCRIPT_URL Configuration: {'FOUND' if script_url else 'MISSING'}")
if script_url:
    print(f"   URL: {script_url}")
    if "/library/" in script_url:
        print("   [!] WARNING: This is a Library URL. It will likely fail with a 405 Method Not Allowed or HTML page instead of JSON.")
    elif "/exec" not in script_url:
        print("   [!] WARNING: This URL does not end in /exec. It is likely not a Web App URL.")
else:
    print("   [❌] ERROR: Cannot proceed without APPS_SCRIPT_URL. You must add it to Hugging Face secrets or .env file.")
    exit(1)

print("\n2. Attempting a direct POST request to the Google Script...")
payload = {
    "secret": os.getenv("APPS_SCRIPT_SECRET", "datalens2026"),
    "action": "create_form",
    "speaker_name": "Timeout Debug Test Speaker",
    "venue_date": "2026-03-21",
    "webhook_url": "https://test.com/webhook",
    "event_id": 9999
}
payload_bytes = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    script_url, 
    data=payload_bytes, 
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=15) as response:
        code = response.getcode()
        print(f"   [HTTP Status]: {code}")
        content = response.read().decode('utf-8')
        print(f"   [Raw Response]: {content}")
        try:
            data = json.loads(content)
            if data.get("success"):
                print("   [✅] SUCCESS: Google Script is correctly responding to the backend!")
            else:
                print(f"   [❌] Apps Script Error: {data.get('error')}")
        except json.JSONDecodeError:
            print("   [❌] ERROR: Google returned HTML, not JSON. It is likely a permissions issue or the wrong Web App URL.")
            
except urllib.error.HTTPError as e:
    print(f"   [❌] HTTP ERROR {e.code}: {e.reason}")
    print(f"   [Details]: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"   [❌] CONNECTION ERROR: {str(e)}")

print("\n=== Debug Finished ===")
