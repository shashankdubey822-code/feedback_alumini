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
from backend.services.rag_service import RAGService
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

        # ── AUTO-BACKFILL: Quietly generate embeddings for all old rows ────────
        def _backfill_embeddings():
            try:
                from backend.utils.insforge_db import api_update
                _rag = RAGService()
                dl_logger.info("[BACKFILL] Checking for feedback rows missing embeddings...")
                batch_size = 10
                total_done = 0
                while True:
                    with get_db() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT fr.id,
                                       fr.aspect_most_valuable,
                                       fr.improvements_suggestions,
                                       fr.future_topics,
                                       e.speaker_name,
                                       e.lecture_title
                                FROM feedback_responses fr
                                LEFT JOIN events e ON fr.event_id = e.id
                                WHERE fr.embedding IS NULL
                                  AND (
                                      fr.aspect_most_valuable IS NOT NULL OR
                                      fr.improvements_suggestions IS NOT NULL OR
                                      fr.future_topics IS NOT NULL
                                  )
                                ORDER BY fr.submitted_at ASC
                                LIMIT %s
                            """, (batch_size,))
                            batch = cur.fetchall()
                    if not batch:
                        dl_logger.info(f"[BACKFILL] Complete. {total_done} embeddings generated.")
                        break
                    
                    batch_attempted = 0
                    batch_success = 0
                    
                    for row in batch:
                        try:
                            # 1. Clean and combine feedback responses
                            val_text = str(row['aspect_most_valuable'] or '').strip()
                            imp_text = str(row['improvements_suggestions'] or '').strip()
                            fut_text = str(row['future_topics'] or '').strip()
                            feedback_parts = [t for t in [val_text, imp_text, fut_text] if t and t.lower() != 'nan' and t.strip()]
                            clean_feedback = " ".join(feedback_parts)

                            # 2. Block low-value noise strings from generating embeddings
                            if (not clean_feedback.strip() or 
                                    len(clean_feedback) < 4 or 
                                    clean_feedback.lower() in ['na', 'none', 'n/a', 'nil', '.', 'ok', 'okay', 'good', 'nothing']):
                                # Save dummy zero-vector so we don't query it next time
                                dummy_emb = [0.0] * 768
                                api_update('feedback_responses', 'id', row['id'], {'embedding': dummy_emb})
                                continue

                            # 3. Enrich the text with context details (Speaker & Topic)
                            speaker = str(row['speaker_name'] or 'Unknown').strip()
                            topic = str(row['lecture_title'] or 'Unknown').strip()
                            enriched_text = f"Speaker: {speaker} | Topic: {topic} | Feedback: {clean_feedback}"

                            batch_attempted += 1
                            emb = _rag.generate_embedding(enriched_text)
                            if emb:
                                api_update('feedback_responses', 'id', row['id'], {'embedding': emb})
                                total_done += 1
                                batch_success += 1
                            else:
                                dl_logger.warning(f"[BACKFILL] Failed to generate embedding for row {row['id']}.")
                        except Exception as e_b:
                            dl_logger.warning(f"[BACKFILL] Skipped row {row['id']}: {e_b}")
                        time.sleep(0.05)  # small pause — don't hammer the model
                    
                    # Prevent infinite loops when all real embedding generations in a batch fail
                    if batch_attempted > 0 and batch_success == 0:
                        dl_logger.error("[BACKFILL] All embedding generations in this batch failed. Stopping backfill to prevent infinite retry loops.")
                        break

                    dl_logger.info(f"[BACKFILL] Progress: {total_done} embeddings done so far...")
            except Exception as e_bf:
                dl_logger.error(f"[BACKFILL] Failed: {e_bf}")

        # Run backfill in a separate daemon thread so it doesn't block the main worker
        threading.Thread(target=_backfill_embeddings, daemon=True, name="embedding_backfill").start()
        # ── END BACKFILL ───────────────────────────────────────────────────────


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
                                e.lecture_title,
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
                        from backend.utils.insforge_db import api_upsert, api_update
                        api_upsert('feedback_analysis', {
                            'response_id': response_id,
                            'sentiment_score': sentiment.get('polarity', 0.0),
                            'sentiment_label': sentiment_label,
                            'key_topics': json.dumps(keywords_payload),
                            'analyzed_at': datetime.now().isoformat()
                        }, 'response_id')

                        # ── Generate and persist embedding vector ─────────────────────
                        try:
                            _rag = RAGService()
                            # 1. Clean and combine feedback responses
                            val_clean = str(row.get('aspect_most_valuable') or '').strip()
                            imp_clean = str(row.get('improvements_suggestions') or '').strip()
                            fut_clean = str(row.get('future_topics') or '').strip()
                            feedback_parts = [t for t in [val_clean, imp_clean, fut_clean] if t and t.lower() != 'nan' and t.strip()]
                            clean_feedback = " ".join(feedback_parts)

                            if not clean_feedback.strip() or len(clean_feedback) < 4 or clean_feedback.lower() in ['na', 'none', 'n/a', 'nil', '.', 'ok', 'okay', 'good', 'nothing']:
                                # Save dummy zero-vector so we don't query it again during backfill
                                dummy_emb = [0.0] * 768
                                api_update('feedback_responses', 'id', response_id, {'embedding': dummy_emb})
                            else:
                                # 2. Enrich the text with context details (Speaker & Topic)
                                speaker = str(row.get('speaker_name') or 'Unknown').strip()
                                topic = str(row.get('lecture_title') or 'Unknown').strip()
                                enriched_text = f"Speaker: {speaker} | Topic: {topic} | Feedback: {clean_feedback}"

                                emb = _rag.generate_embedding(enriched_text)
                                if emb:
                                    api_update('feedback_responses', 'id', response_id, {'embedding': emb})
                                    dl_logger.info(f"Embedding saved for response {response_id} ({len(emb)} dims)")
                        except Exception as e_emb:
                            dl_logger.warning(f"Embedding generation skipped for {response_id}: {e_emb}")

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
