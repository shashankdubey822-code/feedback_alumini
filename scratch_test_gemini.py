import os
import urllib.request
from dotenv import load_dotenv

def test_gemini():
    load_dotenv('.env')
    key = os.getenv('GEMINI_API_KEY')
    print(f"Key found: {bool(key)}")
    if not key:
        print("Error: No GEMINI_API_KEY found in .env")
        return
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(url)
    try:
        res = urllib.request.urlopen(req)
        print("API Status: OK (200)")
        print("API Key is VALID.")
    except Exception as e:
        print(f"API Error: {str(e)}")
        print("API Key is INVALID or EXPIRED.")

if __name__ == '__main__':
    test_gemini()
