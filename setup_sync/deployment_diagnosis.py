import requests
import json
import os

def check_remote_hf():
    # Attempt to check the actual HF URL provided by the user
    hf_url = "https://vrfefavr-feedback-dashboard.hf.space/api/v1/webhook/status"
    print(f"📡 Probing Remote Hugging Face Space: {hf_url}")
    
    try:
        response = requests.get(hf_url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ HF SPACE IS UPDATED: The new /status endpoint was found.")
            print(f"Response Body: {response.text}")
        elif response.status_code == 404:
            print("❌ HF SPACE IS STILL OLD: The new /status code is NOT live yet on Hugging Face.")
        else:
            print(f"⚠️ Unexpected status from HF: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Could not reach HF Space: {e}")

def check_local():
    # Check the local process I see in the terminal
    local_url = "http://127.0.0.1:7860/api/v1/webhook/status"
    print(f"\n📡 Probing Local Server: {local_url}")
    try:
        response = requests.get(local_url, timeout=5)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✅ LOCAL SERVER IS UPDATED.")
        else:
            print(f"❌ LOCAL SERVER IS OLD (Status {response.status_code}).")
    except Exception as e:
        print(f"❌ Local server not reachable on 7860: {e}")

if __name__ == "__main__":
    print("--- LIVE DEPLOYMENT DIAGNOSIS ---")
    check_remote_hf()
    check_local()
