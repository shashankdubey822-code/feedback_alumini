import threading
import time
import sqlite3
import json
from backend.services.nlp_service import NLPService
from backend.config import get_config

def start_dl_worker(logger):
    """Start the deep learning background worker thread"""
    config = get_config()()
    db_path = config.DATABASE_PATH
    
    def worker_loop():
        logger.info("DL Worker Thread Started. Initializing AI Models...")
        nlp = NLPService()
        logger.info("AI Models Initialized. Waiting for data in background...")
        
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
                    SELECT id, improvements_suggestions, aspect_most_valuable, session_help_understanding
                    FROM dashboard_data 
                    WHERE dl_processed = 0 
                    LIMIT 20
                ''')
                rows = cursor.fetchall()
                
                if rows:
                    logger.info(f"DL Worker processing {len(rows)} new records...")
                    for row in rows:
                        # Combine text for comprehensive analysis
                        text_parts = []
                        for col in ['improvements_suggestions', 'aspect_most_valuable', 'session_help_understanding']:
                            if row[col] and str(row[col]).strip() and str(row[col]).lower() != 'nan':
                                text_parts.append(str(row[col]))
                        
                        full_text = ". ".join(text_parts)
                        
                        # Run the deep learning pipeline
                        sentiment = nlp.analyze_sentiment(full_text)
                        keywords = nlp.extract_keywords(full_text)
                        
                        cursor.execute('''
                            UPDATE dashboard_data 
                            SET dl_sentiment_score = ?, dl_sentiment_label = ?, 
                                dl_keywords = ?, dl_processed = 1
                            WHERE id = ?
                        ''', (sentiment['polarity'], sentiment['label'], 
                              json.dumps(keywords), row['id']))
                    conn.commit()
                    logger.info(f"DL Worker finished processing {len(rows)} records.")
                conn.close()
                time.sleep(5) # Poll every 5 seconds
            except Exception as e:
                logger.error(f"DL Worker Error: {e}")
                time.sleep(10)
    
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    return worker_thread
