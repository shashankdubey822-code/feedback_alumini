"""
Debug script — hits the LIVE Hugging Face API to test the close-form endpoint.
Run: python backend/scratch/debug_close_form.py
"""
import urllib.request, json

HF_BASE = "https://vrfefavr-alumini-feedback.hf.space"
ADMIN_TOKEN = "mock-admin-token"

def call(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {ADMIN_TOKEN}'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode()
            print(f"  STATUS : {r.status}")
            print(f"  BODY   : {body}")
            return json.loads(body)
    except Exception as e:
        body = e.read().decode() if hasattr(e, 'read') else str(e)
        print(f"  ERROR  : {e}")
        print(f"  BODY   : {body}")
        return None

# STEP 1 — Get list of events
print("\n[1] Fetching events from HF...")
req = urllib.request.Request(
    f"{HF_BASE}/api/admin/events",
    headers={'Authorization': f'Bearer {ADMIN_TOKEN}'},
    method='GET'
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
        events = data.get('events', [])
        print(f"  Found {len(events)} events:")
        for ev in events:
            print(f"    id={ev.get('id')} | speaker={ev.get('speaker_name')} | form_id={ev.get('form_id')} | status={ev.get('status')}")
except Exception as e:
    print(f"  ERROR fetching events: {e}")
    events = []

if not events:
    print("\nNo events found. Cannot test close.")
    exit()

# STEP 2 — Try closing the first active event
target = next((e for e in events if e.get('status') != 'closed'), events[0])
print(f"\n[2] Testing close-form on event id={target['id']} ({target['speaker_name']})...")
print(f"  Sending: form_id={target.get('form_id')}, event_id={target.get('id')}")

# Simulate exactly what the JS does after our fix
raw_form_id = target.get('form_id')
clean_form_id = raw_form_id if (raw_form_id and str(raw_form_id) not in ('null', 'None')) else None
clean_event_id = str(target['id'])

print(f"  cleanFormId={clean_form_id}, cleanEventId={clean_event_id}")

result = call(
    f"{HF_BASE}/api/admin/close-form",
    {'form_id': clean_form_id, 'event_id': clean_event_id}
)

# STEP 3 — Verify DB was updated
print("\n[3] Re-fetching events to confirm status updated...")
req2 = urllib.request.Request(
    f"{HF_BASE}/api/admin/events",
    headers={'Authorization': f'Bearer {ADMIN_TOKEN}'},
    method='GET'
)
try:
    with urllib.request.urlopen(req2, timeout=15) as r:
        data2 = json.loads(r.read().decode())
        for ev in data2.get('events', []):
            if ev['id'] == target['id']:
                print(f"  Event id={ev['id']} status is now: {ev['status']}")
except Exception as e:
    print(f"  ERROR: {e}")
