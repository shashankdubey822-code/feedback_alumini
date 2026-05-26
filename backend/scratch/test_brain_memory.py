import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.wiki_service import WikiService

def test():
    # Instantiate WikiService
    service = WikiService()
    
    # 1. Ask a question about compiled speakers/events to make sure it matches
    print("\n--- Test 1: Compile info Yogesh ---")
    res1 = service.query_wiki("who is Yogesh?")
    print("Answer:", res1['answer'])
    
    # 2. Try follow-up question with history (memory test)
    print("\n--- Test 2: Follow-up query (what is his patent topic?) ---")
    history = [
        {"role": "user", "content": "who is Yogesh?"},
        {"role": "assistant", "content": res1['answer']}
    ]
    res2 = service.query_wiki("what is his patent topic?", history=history)
    print("Answer:", res2['answer'])

    # 3. Factual Integrity Test (general question)
    print("\n--- Test 3: General knowledge refusal test ---")
    res3 = service.query_wiki("can you write a Python function to sort a list?")
    print("Answer:", res3['answer'])

    # 4. Factual Integrity Test (missing speaker/feedback)
    print("\n--- Test 4: Missing feedback data refusal test ---")
    res4 = service.query_wiki("what did Albert Einstein talk about in his alumni lecture?")
    print("Answer:", res4['answer'])

if __name__ == '__main__':
    test()
