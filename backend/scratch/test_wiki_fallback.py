import os
import sys
from dotenv import load_dotenv

# Ensure backend can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

load_dotenv()

from backend.services.wiki_service import WikiService

# Instantiate WikiService
wiki = WikiService()

# Temporarily mock out Gemini and Groq key fields to force fallback to HF, Cohere, OpenRouter, Mistral
wiki.gemini_key = None
wiki.groq_key = None

# Sample feedback data
feedback_data = [
    {
        "session_rating": 5,
        "session_help_understanding": "Greatly helped",
        "aspect_most_valuable": "The real world examples of LLM agent architectures were extremely insightful.",
        "improvements_suggestions": "None, the pacing was perfect.",
        "future_topics": "Advanced RAG pipelines and vector database optimization."
    },
    {
        "session_rating": 4,
        "session_help_understanding": "Helped a lot",
        "aspect_most_valuable": "Interactive Q&A session at the end was great.",
        "improvements_suggestions": "Provide code templates beforehand.",
        "future_topics": "Agentic workflows and tool-calling models."
    }
]

print("Starting mock fallback compilation...")
print(f"HF Key configured: {bool(wiki.hf_key)}")
print(f"Cohere Key configured: {bool(wiki.cohere_key)}")
print(f"OpenRouter Key configured: {bool(wiki.openrouter_key)}")
print(f"Mistral Key configured: {bool(wiki.mistral_key)}")

try:
    event_id = wiki.compile_session("Test Speaker", "2026-05-26", feedback_data)
    print("\nCompilation Result event_id:", event_id)
    
    # Read compilation logs
    from backend.services.wiki_service import _ingest_logs
    print("\nCompilation Logs:")
    for log in _ingest_logs:
        print(log)
except Exception as e:
    print("Test failed with exception:", e)
