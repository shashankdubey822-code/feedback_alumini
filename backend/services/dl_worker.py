"""
dl_worker.py — Deep Learning / NLP background worker.
Reads unprocessed rows from feedback_responses, writes to feedback_analysis.
Uses native InsForge PostgreSQL via insforge_db.py.
"""

import threading
import time
import json
from datetime import datetime
from backend.services.nlp_service import NLPService
from backend.utils.logger import get_section_logger
from backend.utils.insforge_db import get_db

_dl_thread = None
_dl_wakeup_event = threading.Event()


def trigger_dl_processing():
    """Wake up the DL worker thread to process new responses immediately."""
    _dl_wakeup_event.set()


def start_dl_worker(logger_unused=None):
    """Start the deep learning background worker thread."""
    global _dl_thread
    dl_logger = get_section_logger('dl_worker')

    def worker_loop():
        dl_logger.info("DL Worker Thread Started. Initializing AI Models...")
        nlp = NLPService()
        dl_logger.info("AI Models Initialized. Polling for unprocessed feedback...")

        while True:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        # Find feedback_responses that don't yet have an analysis row
                        cur.execute("""
                            SELECT
                                fr.id,
                                fr.improvements_suggestions,
                                fr.aspect_most_valuable,
                                fr.session_help_understanding,
                                fr.future_topics,
                                fr.session_rating,
                                e.speaker_name,
                                e.venue_date,
                                s.name as student_name
                            FROM feedback_responses fr
                            LEFT JOIN feedback_analysis fa ON fa.response_id = fr.id
                            LEFT JOIN events e ON fr.event_id = e.id
                            LEFT JOIN students s ON fr.student_id = s.id
                            WHERE fa.response_id IS NULL
                            ORDER BY fr.submitted_at ASC
                            LIMIT 20
                        """)
                        rows = cur.fetchall()

                if not rows:
                    _dl_wakeup_event.wait(5)
                    _dl_wakeup_event.clear()
                    continue

                dl_logger.info(f"DL Worker processing {len(rows)} new response(s)...")

                for row in rows:
                    response_id = row['id']
                    imp_text = str(row['improvements_suggestions'] or '').strip()
                    val_text = str(row['aspect_most_valuable'] or '').strip()
                    fut_text = str(row['future_topics'] or '').strip()

                    # Combined text for overall sentiment (valuable aspects, suggestions, and future topics)
                    text_parts = [t for t in [val_text, imp_text, fut_text] if t and t.lower() != 'nan' and t.strip()]
                    full_text = ". ".join(text_parts)

                    # Core NLP
                    sentiment = nlp.analyze_sentiment(full_text)
                    general_keywords = nlp.extract_keywords(full_text)

                    # Per-field sentiment
                    imp_sentiment = (
                        nlp.analyze_sentiment(imp_text)['label']
                        if imp_text and not nlp.is_non_answer(imp_text)
                        else 'NO_RESPONSE'
                    )
                    val_sentiment = (
                        nlp.analyze_sentiment(val_text)['label']
                        if val_text and not nlp.is_non_answer(val_text)
                        else 'NO_RESPONSE'
                    )

                    # Keyphrases per field
                    fut_keywords = nlp.extract_keyphrases(fut_text)
                    imp_keywords = nlp.extract_keyphrases(imp_text)
                    val_keywords = nlp.extract_keyphrases(val_text)

                    # Actionability + Category
                    is_actionable = bool(imp_text and not nlp.is_non_answer(imp_text))
                    imp_lower = imp_text.lower()
                    if not is_actionable:
                        category = "Non-Actionable"
                    elif any(w in imp_lower for w in ['interact', 'activity', 'engage', 'practical']):
                        category = "More Interaction"
                    elif any(w in imp_lower for w in ['tech', 'skill', 'code', 'ai', 'program']):
                        category = "Technical Deep Dives"
                    elif any(w in imp_lower for w in ['career', 'job', 'placement', 'interview', 'resume']):
                        category = "Career Advice"
                    elif any(w in imp_lower for w in ['time', 'duration', 'short', 'long', 'slow', 'fast', 'pace']):
                        category = "Duration/Time"
                    else:
                        category = "General Improvement"

                    keywords_payload = {
                        "improvements_sentiment": imp_sentiment,
                        "valuable_sentiment": val_sentiment,
                        "future_keywords": fut_keywords,
                        "imp_keywords": imp_keywords,
                        "val_keywords": val_keywords,
                        "is_actionable": is_actionable,
                        "category": category,
                        "general_keywords": general_keywords,
                    }

                    sentiment_label = sentiment.get('label', 'NEUTRAL')
                    if sentiment_label not in ('POSITIVE', 'NEUTRAL', 'NEGATIVE'):
                        sentiment_label = 'NEUTRAL'

                    # Upsert into feedback_analysis using REST API
                    try:
                        from backend.utils.insforge_db import api_upsert
                        api_upsert('feedback_analysis', {
                            'response_id': response_id,
                            'sentiment_score': sentiment.get('polarity', 0.0),
                            'sentiment_label': sentiment_label,
                            'key_topics': json.dumps(keywords_payload),
                            'analyzed_at': datetime.now().isoformat()
                        }, 'response_id')
                        
                        # Sync analytics cache immediately and emit socket event
                        try:
                            from backend.services.analytics_engine import analytics_engine
                            from backend.extensions import socketio
                            
                            analytics_engine.refresh_single_record(response_id)
                            
                            raw_date = row.get('venue_date')
                            date_str = str(raw_date).split('T')[0] if raw_date else ''
                            
                            rating_val = row.get('session_rating')
                            rating_str = rating_val if rating_val is not None else ''
                            
                            socketio.emit('nlp_completed', {
                                'record_id': response_id,
                                'speaker': str(row.get('speaker_name') or ''),
                                'student_name': str(row.get('student_name') or ''),
                                'date': date_str,
                                'sentiment': str(sentiment_label or ''),
                                'rating': rating_str
                            })
                        except Exception as e_sync:
                            dl_logger.error(f"Failed to sync analytics/emit socket: {e_sync}")
                    except Exception as e_row:
                        dl_logger.error(f"DL Worker failed processing response {response_id}: {e_row}")
                        try:
                            err_payload = {
                                'error': str(e_row),
                                'notes': 'processing_failed'
                            }
                            api_upsert('feedback_analysis', {
                                'response_id': response_id,
                                'sentiment_score': 0.0,
                                'sentiment_label': None,
                                'key_topics': json.dumps(err_payload),
                                'analyzed_at': datetime.now().isoformat()
                            }, 'response_id')
                        except Exception as e_marker:
                            dl_logger.error(f"Failed to write failure marker for {response_id}: {e_marker}")

                dl_logger.info(f"DL Worker finished processing {len(rows)} record(s).")

                _dl_wakeup_event.wait(5)
                _dl_wakeup_event.clear()

            except Exception as e:
                dl_logger.error(f"DL Worker Error: {e}")
                _dl_wakeup_event.wait(10)
                _dl_wakeup_event.clear()

    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    _dl_thread = worker_thread
    return worker_thread
