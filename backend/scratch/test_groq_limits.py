import os, json, urllib.request
from dotenv import load_dotenv

load_dotenv()
groq_key = os.getenv("GROQ_API_KEY")

url = "https://api.groq.com/openai/v1/chat/completions"
req_data = json.dumps({
    "model": "llama-3.3-70b-versatile", 
    "messages": [{"role": "user", "content": "hi"}], 
    "max_tokens": 1
}).encode('utf-8')
req = urllib.request.Request(url, data=req_data, headers={'Authorization': f'Bearer {groq_key}', 'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print(dict(response.headers))
except Exception as e:
    print(e)
