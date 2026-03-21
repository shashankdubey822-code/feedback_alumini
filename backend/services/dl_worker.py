import threading
import time
import sqlite3
import json
from backend.services.nlp_service import NLPService
from backend.config import get_config
from backend.utils.logger import get_section_logger

def start_dl_worker(logger_unused):
    """Start the deep learning background worker thread"""
    dl_logger = get_section_logger('dl_worker')
    config = get_config()()
    db_path = config.DATABASE_PATH
    
    def worker_loop():
        dl_logger.info("DL Worker Thread Started. Initializing AI Models...")
        nlp = NLPService()
        dl_logger.info("AI Models Initialized. Waiting for data in background...")
        
        while True:
            try:
                conn = sqlite3.connect(db_path, timeout=10.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check if the columns exist yet (startup safety)
                cursor.execute("PRAGMA table_info(dashboard_data)")
                cols = [row['name'] for row in cursor.fetchall()]
                if 'dl_processed' not in cols:
                    conn.close()
                    time.sleep(5)
                    continue

                # Find unprocessed rows
                cursor.execute('''
                    SELECT id, improvements_suggestions, aspect_most_valuable, session_help_understanding, future_topics
                    FROM dashboard_data 
                    WHERE dl_processed = 0 
                    LIMIT 20
                ''')
                rows = cursor.fetchall()
                
                if rows:
                    dl_logger.info(f"DL Worker processing {len(rows)} new records...")
                    for row in rows:
                        # Fetch text parts
                        imp_text = str(row['improvements_suggestions'] or '').strip()
                        val_text = str(row['aspect_most_valuable'] or '').strip()
                        fut_text = str(row['future_topics'] or '').strip()
                        help_text = str(row['session_help_understanding'] or '').strip()
                        
                        # Combine text for legacy general analysis
                        text_parts = [t for t in [imp_text, val_text, help_text] if t and t.lower() != 'nan']
                        full_text = ". ".join(text_parts)
                        
                        # Run the deep learning pipeline (overall)
                        sentiment = nlp.analyze_sentiment(full_text)
                        general_keywords = nlp.extract_keywords(full_text)
                        
                        # ----- DEEP ANALYSIS -----
                        # 1. Sentiment Scorecards
                        imp_sentiment = nlp.analyze_sentiment(imp_text)['label'] if imp_text and not nlp.is_non_answer(imp_text) else 'NO_RESPONSE'
                        val_sentiment = nlp.analyze_sentiment(val_text)['label'] if val_text and not nlp.is_non_answer(val_text) else 'NO_RESPONSE'
                        
                        # 2. Top Trending Topics Word Cloud
                        fut_keywords = nlp.extract_keywords(fut_text)
                        
                        # 3. Actionable vs Non-Actionable Filter
                        is_actionable = 1 if imp_text and not nlp.is_non_answer(imp_text) else 0
                        
                        # 4. Suggestion Categorization
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
                            
                        # Store in extended JSON payload
                        extended_data = {
                            "improvements_sentiment": imp_sentiment,
                            "valuable_sentiment": val_sentiment,
                            "future_keywords": fut_keywords,
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
                    dl_logger.info(f"DL Worker finished processing {len(rows)} records.")
                conn.close()
                time.sleep(5) # Poll every 5 seconds
            except Exception as e:
                dl_logger.error(f"DL Worker Error: {e}")
                time.sleep(10)
    
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    return worker_thread
