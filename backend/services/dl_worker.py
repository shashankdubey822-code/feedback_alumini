"""
dl_worker.py — Deep Learning / NLP background worker.
Reads unprocessed rows from feedback_responses, writes to feedback_analysis.
Uses native Supabase PostgreSQL via supabase_db.py.
"""

import threading
import time
import json
from backend.services.nlp_service import NLPService
from backend.utils.logger import get_section_logger
from backend.utils.supabase_db import get_db

_dl_thread = None


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
                                fr.future_topics
                            FROM feedback_responses fr
                            LEFT JOIN feedback_analysis fa ON fa.response_id = fr.id
                            WHERE fa.id IS NULL
                            ORDER BY fr.submitted_at ASC
                            LIMIT 20
                        """)
                        rows = cur.fetchall()

                        if not rows:
                            time.sleep(5)
                            continue

                        dl_logger.info(f"DL Worker processing {len(rows)} new response(s)...")

                        for row in rows:
                            response_id = row['id']
                            imp_text  = str(row['improvements_suggestions'] or '').strip()
                            val_text  = str(row['aspect_most_valuable'] or '').strip()
                            fut_text  = str(row['future_topics'] or '').strip()

                            # Combined text for overall sentiment (future_topics primary)
                            text_parts = [t for t in [fut_text] if t and t.lower() != 'nan']
                            full_text  = ". ".join(text_parts)

                            # Core NLP
                            sentiment        = nlp.analyze_sentiment(full_text)
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
                                "valuable_sentiment":     val_sentiment,
                                "future_keywords":        fut_keywords,
                                "imp_keywords":           imp_keywords,
                                "val_keywords":           val_keywords,
                                "is_actionable":          is_actionable,
                                "category":               category,
                                "general_keywords":       general_keywords,
                            }

                            sentiment_label = sentiment.get('label', 'NEUTRAL')
                            if sentiment_label not in ('POSITIVE', 'NEUTRAL', 'NEGATIVE'):
                                sentiment_label = 'NEUTRAL'

                            # Upsert into feedback_analysis
                            cur.execute("""
                                INSERT INTO feedback_analysis
                                    (response_id, sentiment_score, sentiment_label,
                                     keywords_json, processed_at, model_version)
                                VALUES (%s, %s, %s, %s, NOW(), 'v2')
                                ON CONFLICT (response_id) DO UPDATE SET
                                    sentiment_score = EXCLUDED.sentiment_score,
                                    sentiment_label = EXCLUDED.sentiment_label,
                                    keywords_json   = EXCLUDED.keywords_json,
                                    processed_at    = NOW()
                            """, (
                                response_id,
                                sentiment.get('polarity', 0.0),
                                sentiment_label,
                                json.dumps(keywords_payload),
                            ))

                        conn.commit()
                        dl_logger.info(f"DL Worker finished processing {len(rows)} record(s).")

                time.sleep(5)

            except Exception as e:
                dl_logger.error(f"DL Worker Error: {e}")
                time.sleep(10)

    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    _dl_thread = worker_thread
    return worker_thread
