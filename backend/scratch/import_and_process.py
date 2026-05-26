import os
import sys
import pandas as pd
import sqlite3
import json

# Add backend directory to sys path so we can import services
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.routes.admin import _normalize_dataframe_for_dashboard
from backend.services.nlp_service import NLPService
from backend.services.wiki_service import WikiService
from backend.utils.db_helper import get_db_connection

def main():
    print("🚀 Starting Data Analysis Project Import & Processing...")
    
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'dashboard.db'))
    if not os.path.exists(db_path):
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'dashboard.db'))
        
    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'uploads', 'Student_Feedback_Trimmed.csv'))
    
    print(f"📄 Reading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"📊 Found {len(df)} records in CSV.")
    
    print("🧹 Normalizing dataset...")
    normalized_df = _normalize_dataframe_for_dashboard(df, source='initial_data_analysis')
    
    print(f"💾 Clearing old data from database: {db_path}...")
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dashboard_data")
    cursor.execute("DELETE FROM events")
    
    # Recreate events for our speakers so they look nice
    speakers = normalized_df['alumni_speaker_name'].dropna().unique()
    for s in speakers:
        cursor.execute(
            "INSERT INTO events (speaker_name, venue_date, status) VALUES (?, ?, ?)",
            (str(s).strip(), '2026-02-24', 'active')
        )
    
    cursor.execute('PRAGMA table_info(dashboard_data)')
    table_columns = [row[1] for row in cursor.fetchall()]
    insert_columns = [col for col in table_columns if col != 'id']

    for col in insert_columns:
        if col not in normalized_df.columns:
            if col == 'dl_processed':
                normalized_df[col] = 0
            else:
                normalized_df[col] = None

    aligned_df = normalized_df[insert_columns]
    
    print("💾 Inserting clean records into database...")
    aligned_df.to_sql('dashboard_data', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()
    
    print("🧠 Initializing NLP Models (this may take a moment to load RoBERTa & KeyBERT)...")
    nlp = NLPService()
    
    print("⚙️ Running Deep Learning / NLP processing over all rows...")
    conn = get_db_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, improvements_suggestions, aspect_most_valuable, session_help_understanding, future_topics
        FROM dashboard_data 
        WHERE dl_processed = 0 
    ''')
    rows = cursor.fetchall()
    
    for i, row in enumerate(rows):
        if i % 50 == 0:
            print(f"   Processing record {i}/{len(rows)}...")
            
        imp_text = str(row['improvements_suggestions'] or '').strip()
        val_text = str(row['aspect_most_valuable'] or '').strip()
        fut_text = str(row['future_topics'] or '').strip()
        
        # Combine text for legacy general analysis
        text_parts = [t for t in [fut_text] if t and t.lower() != 'nan']
        full_text = ". ".join(text_parts)
        
        sentiment = nlp.analyze_sentiment(full_text)
        general_keywords = nlp.extract_keywords(full_text)
        
        imp_sentiment = nlp.analyze_sentiment(imp_text)['label'] if imp_text and not nlp.is_non_answer(imp_text) else 'NO_RESPONSE'
        val_sentiment = nlp.analyze_sentiment(val_text)['label'] if val_text and not nlp.is_non_answer(val_text) else 'NO_RESPONSE'
        
        fut_keywords = nlp.extract_keyphrases(fut_text)
        imp_keywords = nlp.extract_keyphrases(imp_text)
        val_keywords = nlp.extract_keyphrases(val_text)
        
        is_actionable = 1 if imp_text and not nlp.is_non_answer(imp_text) else 0
        
        category = "Other"
        imp_lower = imp_text.lower()
        if any(w in imp_lower for w in ['interact', 'activity', 'engage', 'practical']):
            category = "More Interaction"
        elif any(w in imp_lower for w in ['tech', 'skill', 'code', 'ai', 'program']):
            category = "Technical Deep Dives"
        elif any(w in imp_lower for w in ['career', 'job', 'placement', 'interview', 'resume']):
            category = "Career Advice"
        elif any(w in imp_lower for w in ['time', 'duration', 'short', 'long', 'slow', 'fast', 'pace']):
            category = "Duration/Time"
        elif is_actionable == 1:
            category = "General Improvement"
            
        extended_data = {
            "improvements_sentiment": imp_sentiment,
            "valuable_sentiment": val_sentiment,
            "future_keywords": fut_keywords,
            "imp_keywords": imp_keywords,
            "val_keywords": val_keywords,
            "is_actionable": is_actionable,
            "category": category if is_actionable == 1 else "Non-Actionable",
            "general_keywords": general_keywords
        }
        
        cursor.execute('''
            UPDATE dashboard_data 
            SET dl_sentiment_score = ?, dl_sentiment_label = ?, 
                dl_keywords = ?, dl_processed = 1
            WHERE id = ?
        ''', (sentiment['polarity'], sentiment['label'], 
              json.dumps(extended_data), row['id']))
              
    conn.commit()
    conn.close()
    
    print("✅ NLP Processing Complete!")
    
    print("📚 Compiling AI Knowledge Wiki Pages with new dataset...")
    # Mocking current_app for context if needed, but WikiService takes db_path directly
    try:
        wiki = WikiService(db_path=db_path)
        wiki.compile_wiki(force=True)
        print("✅ Wiki compilation successfully updated.")
    except Exception as e:
        print(f"⚠️ Wiki compilation warning: {e}. If it failed due to missing Gemini API key in env, make sure it is configured.")
        
    print("🎉 Entire project data has been rebuilt and deployed to database!")

if __name__ == '__main__':
    main()
