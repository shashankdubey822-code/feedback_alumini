"""
Script to test the wiki query API and check exactly why it is failing.
"""
import urllib.request
import json
import os

ADMIN_TOKEN = "mock-admin-token"
HF_BASE = "http://127.0.0.1:5000"  # Testing local first, or HF
# HF_BASE = "https://vrfefavr-alumini-feedback.hf.space"

def test_query(question):
    print(f"\nTesting query: '{question}'")
    req = urllib.request.Request(
        f"{HF_BASE}/api/v1/wiki/query",
        data=json.dumps({"question": question, "session_id": "debug-123"}).encode(),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {ADMIN_TOKEN}'
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            print(f"STATUS: {r.status}")
            print(f"BODY: {body}")
    except Exception as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'read'):
            print(f"ERROR BODY: {e.read().decode()}")

if __name__ == "__main__":
    print("Testing against HuggingFace production space...")
    HF_BASE = "https://vrfefavr-alumini-feedback.hf.space"
    test_query("hello")
    test_query("how many student data you have")
