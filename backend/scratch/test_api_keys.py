"""
OpenRouter Free Model Evaluator
Queries the OpenRouter models list, filters for free models,
and tests each model to evaluate performance and availability.
"""

import os
import json
import time
import urllib.request
import urllib.error
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

def fetch_openrouter_models():
    """Fetch all available models from OpenRouter API"""
    print("[INFO] Fetching models list from OpenRouter...")
    url = "https://openrouter.ai/api/v1/models"
    headers = {
        "Content-Type": "application/json"
    }
    # Include API key if available to fetch user-specific/unlocked model visibility
    if OPENROUTER_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_KEY}"
        
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = json.loads(response.read().decode('utf-8'))
            return res_body.get('data', [])
    except Exception as e:
        print(f"[ERROR] Failed to fetch models: {e}")
        return []

def filter_free_models(models):
    """Filter models that are free (slug ending with :free or price is 0.0)"""
    free_models = []
    for model in models:
        model_id = model.get('id', '')
        name = model.get('name', '')
        pricing = model.get('pricing', {})
        
        # Check if id/name indicate it's free, or if prompt/completion costs are 0
        prompt_cost = float(pricing.get('prompt', '1.0') or 0.0)
        completion_cost = float(pricing.get('completion', '1.0') or 0.0)
        
        is_free = (
            model_id.endswith(':free') or 
            'free' in name.lower() or 
            (prompt_cost == 0.0 and completion_cost == 0.0)
        )
        
        if is_free:
            free_models.append({
                "id": model_id,
                "name": name,
                "context_length": model.get('context_length', 0)
            })
            
    # Remove duplicates if any
    unique_free = []
    seen = set()
    for fm in free_models:
        if fm['id'] not in seen:
            unique_free.append(fm)
            seen.add(fm['id'])
            
    return unique_free

def test_model_chat(model_id, prompt="Say 'Ready' and the model name in under 10 words."):
    """Test a single model with a chat completion request"""
    if not OPENROUTER_KEY:
        return False, 0.0, "API Key is missing", ""
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    req_data = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 50
    }).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENROUTER_KEY}',
        # OpenRouter-specific headers for identification (optional but recommended)
        'HTTP-Referer': 'https://github.com/shashankdubey822-code/feedback_alumini',
        'X-Title': 'Alumni Feedback Fallback Evaluator'
    }
    
    request = urllib.request.Request(url, data=req_data, headers=headers)
    start_time = time.time()
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            latency = time.time() - start_time
            res_body = json.loads(response.read().decode('utf-8'))
            choices = res_body.get('choices', [])
            if choices:
                content = (choices[0]['message'].get('content') or "").strip()
                return True, latency, "", content
            else:
                return False, latency, f"No choices: {res_body}", ""
    except urllib.error.HTTPError as e:
        latency = time.time() - start_time
        try:
            err_body = e.read().decode('utf-8')
            err_json = json.loads(err_body)
            err_msg = err_json.get('error', {}).get('message', err_body)
        except Exception:
            err_msg = str(e)
        return False, latency, f"HTTP {e.code}: {err_msg}", ""
    except Exception as e:
        latency = time.time() - start_time
        return False, latency, str(e), ""

def main():
    print("=" * 70)
    print("          OPENROUTER FREE MODELS EVALUATION SUITE")
    print("=" * 70)
    
    if not OPENROUTER_KEY:
        print("[CRITICAL] OPENROUTER_API_KEY environment variable is not set!")
        print("Please check your .env file.")
        return

    # 1. Fetch models
    all_models = fetch_openrouter_models()
    if not all_models:
        print("[ERROR] Could not retrieve models list.")
        return
        
    print(f"[OK] Fetched {len(all_models)} total models from OpenRouter.")
    
    # 2. Filter free models
    free_models = filter_free_models(all_models)
    print(f"[OK] Found {len(free_models)} free models available.")
    print("-" * 70)
    
    # List detected free models
    for idx, fm in enumerate(free_models, 1):
        print(f"  {idx:02d}. {fm['name']} ({fm['id']}) [Ctx: {fm['context_length']}]")
    print("-" * 70)
    
    # 3. Test each free model
    print("\n[INFO] Starting active testing of free models...")
    print("This will send a small test query to each model. Please wait...")
    print("=" * 70)
    
    results = []
    
    # Define a clean test prompt
    test_prompt = "Verify your status: write exactly 'Online and working' followed by your model name."
    
    for idx, fm in enumerate(free_models, 1):
        model_id = fm['id']
        model_name = fm['name']
        print(f"[{idx}/{len(free_models)}] Testing: {model_name}...")
        
        # Add a tiny delay between tests to respect general rate limits
        time.sleep(0.5)
        
        success, latency, err, response = test_model_chat(model_id, test_prompt)
        
        status_str = "SUCCESS" if success else "FAILED"
        print(f"      Status: {status_str} | Latency: {latency:.2f}s")
        if success:
            print(f"      Response: \"{response}\"")
        else:
            print(f"      Error: {err}")
            
        results.append({
            "id": model_id,
            "name": model_name,
            "success": success,
            "latency": latency,
            "error": err,
            "response": response
        })
        print("-" * 50)
        
    # 4. Generate Summary Report
    print("\n" + "=" * 70)
    print("                      EVALUATION REPORT")
    print("=" * 70)
    
    working_models = [r for r in results if r['success']]
    failed_models = [r for r in results if not r['success']]
    
    print(f"Total Evaluated: {len(results)}")
    print(f"Working Models:  {len(working_models)}")
    print(f"Failed Models:   {len(failed_models)}")
    print("-" * 70)
    
    if working_models:
        print("\n[OK] WORKING FREE MODELS (Ordered by Latency):")
        # Sort working models by latency
        working_models_sorted = sorted(working_models, key=lambda x: x['latency'])
        for idx, r in enumerate(working_models_sorted, 1):
            print(f"  {idx:02d}. Model: {r['name']}")
            print(f"      ID:    {r['id']}")
            print(f"      Speed: {r['latency']:.2f} seconds")
            print(f"      Reply: {r['response']}")
            print()
    else:
        print("\n[WARNING] No free models successfully responded to the test query.")
        print("This could be due to API rate limits (HTTP 429), server load, or invalid credentials.")
        
    if failed_models:
        print("\n[INFO] FAILED FREE MODELS:")
        for idx, r in enumerate(failed_models, 1):
            print(f"  {idx:02d}. Model: {r['name']} ({r['id']})")
            print(f"      Reason: {r['error']}")
            print()
            
    print("=" * 70)

if __name__ == "__main__":
    main()
