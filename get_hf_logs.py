import os
import requests
import sys

def fetch_hf_logs(space_id: str, token: str):
    """
    Fetches the build and runtime logs of a Hugging Face Space using the Hub API.
    """
    url = f"https://huggingface.co/api/spaces/{space_id}/logs"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print(f"Fetching logs for Hugging Face Space: {space_id}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        print("Logs retrieved successfully!\n")
        logs = response.text
        print(logs)
        
        # Optionally write to a file
        with open("hf_space_logs.txt", "w", encoding="utf-8") as f:
            f.write(logs)
        print("\n[SUCCESS] Logs have been saved to hf_space_logs.txt")
    else:
        print(f"[ERROR] Failed to fetch logs. HTTP {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    # The script expects HF_SPACE_ID and HF_TOKEN to be set in the environment
    space_id = os.environ.get("HF_SPACE_ID")
    token = os.environ.get("HF_TOKEN")
    
    if not space_id or not token:
        print("Error: Missing environment variables.")
        print("Please ensure HF_SPACE_ID (e.g., 'username/spacename') and HF_TOKEN are set.")
        sys.exit(1)
        
    fetch_hf_logs(space_id, token)
