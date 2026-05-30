import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.services.wiki_service import WikiService
import logging

logging.basicConfig(level=logging.INFO)

wiki = WikiService()

print("Executing RAG query...")
result = wiki.query_wiki("hey how many speaker total number of you have")
print("\n--- RAG RESULT ---")
print(result)
