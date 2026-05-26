import os
import json
import urllib.request
import urllib.error
import socket
from dotenv import load_dotenv

load_dotenv()

HF_KEY = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

prompt = "Hello! Please reply with a single short JSON object containing a 'status' field set to 'success'."

def list_all_free_openrouter_models():
    print("--- Listing All Free OpenRouter Models ---")
    url = "https://openrouter.ai/api/v1/models"
    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=30) as r:
            res = json.loads(r.read().decode('utf-8'))
            models = res.get('data', [])
            free_models = [m['id'] for m in models if 'free' in m['id'] or m.get('pricing', {}).get('prompt') == '0']
            for fm in free_models:
                print(f" - {fm}")
    except Exception as e:
        print(f"Failed to list: {e}")

def test_openrouter_free_model():
    print("\n--- Testing OpenRouter with 'openrouter/free' ---")
    if not OPENROUTER_KEY:
        print("No OpenRouter key")
        return
    url = "https://openrouter.ai/api/v1/chat/completions"
    # Let's try 'openrouter/free' model or 'meta-llama/llama-3.2-3b-instruct:free'
    req_data = json.dumps({
        "model": "openrouter/free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }).encode('utf-8')
    request = urllib.request.Request(
        url, data=req_data,
        headers={
            'Authorization': f'Bearer {OPENROUTER_KEY}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://huggingface.co/spaces/vrfefavr/alumini_feedback',
            'X-Title': 'Alumni Feedback System'
        }
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as r:
            res = json.loads(r.read().decode('utf-8'))
            print("OpenRouter 'openrouter/free' Success:")
            print(res['choices'][0]['message']['content'])
    except Exception as e:
        print(f"OpenRouter free failed: {e}")

def test_dns_resolution():
    print("\n--- Resolving Hostnames ---")
    for host in ["api-inference.huggingface.co", "huggingface.co", "api.cohere.ai", "openrouter.ai", "api.mistral.ai"]:
        try:
            ip = socket.gethostbyname(host)
            print(f"Resolved {host} -> {ip}")
        except Exception as e:
            print(f"Failed to resolve {host}: {e}")

if __name__ == "__main__":
    test_dns_resolution()
    list_all_free_openrouter_models()
    test_openrouter_free_model()
