import os
import sys
import sqlite3
import json

# Add project root to sys path so we can import backend packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.nlp_service import NLPService
from backend.config import get_config

def main():
    print("[*] Initializing Hugging Face Deep Learning Pipeline...")
    nlp = NLPService()
    print("[+] Models loaded successfully!\n")

    config = get_config()()
    db_path = config.DATABASE_PATH
    
    # 1. Connect to the actual database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 2. Fetch 5 records containing text feedback
    try:
        cursor.execute('''
            SELECT id, name_of_student, aspect_most_valuable, improvements_suggestions, future_topics
            FROM dashboard_data
            WHERE length(aspect_most_valuable) > 5 OR length(improvements_suggestions) > 5
            LIMIT 5
        ''')
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[!] Error fetching from database: {e}")
        return

    if not rows:
        print("[!] No suitable textual feedback found in the database. Using dummy data fallback...")
        rows = [
            {'id': 'D1', 'name_of_student': 'Alice', 'aspect_most_valuable': 'The session was extremely informative and brilliant!', 'improvements_suggestions': '', 'future_topics': ''},
            {'id': 'D2', 'name_of_student': 'Bob', 'aspect_most_valuable': '', 'improvements_suggestions': 'The pacing was too slow and boring, I hated the audio quality.', 'future_topics': ''},
            {'id': 'D3', 'name_of_student': 'Charlie', 'aspect_most_valuable': 'Good practical examples.', 'improvements_suggestions': 'Maybe provide the slides beforehand.', 'future_topics': 'Advanced ML'}
        ]

    # 3. Process each row with the DL models
    print(f"[*] Analyzing {len(rows)} records...\n")
    print("=" * 60)
    
    for row in rows:
        # Combine text fields (same logic used by the worker)
        text_parts = []
        if dict(row).get('aspect_most_valuable'): text_parts.append(str(row['aspect_most_valuable']))
        if dict(row).get('improvements_suggestions'): text_parts.append(str(row['improvements_suggestions']))
        if dict(row).get('future_topics'): text_parts.append(str(row['future_topics']))
        
        combined_text = " | ".join(text_parts)
        if not combined_text.strip():
            continue
            
        print(f"Student: {row['name_of_student']} (ID: {row['id']})")
        print(f"Text: {combined_text}")
        
        # Run Sentiment Analysis Model
        sentiment = nlp.analyze_sentiment(combined_text)
        print(f"AI Sentiment: {sentiment['label']} ({sentiment['polarity']:.3f})")
        
        # Run Keyword Extraction Model
        keywords = nlp.extract_keywords(combined_text, limit=3)
        print(f"Keywords: {json.dumps(keywords, indent=2)}")
        print("-" * 60)

if __name__ == '__main__':
    main()
