"""
rag_service.py — RAG semantic search via InsForge pgvector.

Embedding generation now uses OpenRouter text-embedding-3-small (remote API)
instead of the local BAAI/bge-base-en-v1.5 SentenceTransformer model (768MB RAM).
All 1,758 existing rows already have embeddings stored in the DB.
This only generates embeddings for NEW feedback rows as they arrive.

Note: text-embedding-3-small with dimensions=768 matches the existing vector(768) column.
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional

from backend.utils.logger import get_section_logger
from backend.utils.insforge_helper import is_insforge_active
from backend.utils.insforge_db import execute_all

logger = get_section_logger('rag')

_OPENROUTER_EMBED_URL = 'https://openrouter.ai/api/v1/embeddings'
_EMBED_MODEL = 'openai/text-embedding-3-small'


class RAGService:
    """Semantic search on feedback using InsForge pgvector + remote embeddings."""

    def __init__(self):
        pass  # No model loading — all inference is remote via OpenRouter

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate a 768-dim embedding via OpenRouter text-embedding-3-small.
        Only called for NEW feedback rows; existing rows already have embeddings.
        """
        if not text or not text.strip():
            return None

        api_key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not api_key:
            logger.warning('OPENROUTER_API_KEY not set — cannot generate embedding')
            return None

        try:
            resp = requests.post(
                _OPENROUTER_EMBED_URL,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': _EMBED_MODEL,
                    'input': text.strip()[:8000],  # token limit safety
                    'dimensions': 768,              # Match existing vector(768) column schema
                },
                timeout=30,
            )
            resp.raise_for_status()
            embedding = resp.json()['data'][0]['embedding']
            return [float(x) for x in embedding]
        except Exception as e:
            logger.error(f'Embedding generation failed: {e}')
            return None

    def search_similar_feedback(
        self,
        query_text: str,
        limit: int = 50,
        threshold: float = 0.3,
        filter_year: int = None,
        filter_semester: str = None,
        filter_dept: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute semantic vector search on feedback with optional year/semester/dept filters.
        Uses match_feedback_filtered stored procedure on InsForge (pgvector).
        Falls back to keyword search if embeddings unavailable.
        """
        if not is_insforge_active():
            logger.info('InsForge not active. Using fast keyword search fallback.')
            return self._fallback_keyword_search(query_text, limit)

        query_vector = self.generate_embedding(query_text)
        if not query_vector:
            return self._fallback_keyword_search(query_text, limit)

        try:
            logger.info(
                f"pgvector search: '{query_text}' | year={filter_year} "
                f'sem={filter_semester} dept={filter_dept}'
            )
            rows = execute_all(
                'SELECT * FROM match_feedback_filtered(%s::vector, %s, %s, %s, %s, %s)',
                (str(query_vector), threshold, limit, filter_year, filter_semester, filter_dept),
            )
            if rows:
                logger.info(f'pgvector returned {len(rows)} results.')
                return rows
            logger.warning('pgvector returned 0 results. Falling back to keyword search.')
        except Exception as e:
            logger.error(f'pgvector search failed: {str(e)}')

        return self._fallback_keyword_search(query_text, limit)

    def _fallback_keyword_search(self, query_text: str, limit: int) -> List[Dict[str, Any]]:
        """Simple InsForge-backed substring search when vector search is unavailable."""
        try:
            tokens = [f'%{t}%' for t in query_text.lower().split() if len(t) > 2]
            if not tokens:
                tokens = [f'%{query_text.lower()}%']

            conditions = []
            params = []
            for t in tokens:
                conditions.append(
                    "(COALESCE(e.speaker_name, '') ILIKE %s "
                    "OR COALESCE(r.aspect_most_valuable, '') ILIKE %s "
                    "OR COALESCE(r.improvements_suggestions, '') ILIKE %s "
                    "OR COALESCE(r.future_topics, '') ILIKE %s)"
                )
                params.extend([t, t, t, t])

            query = f'''
                SELECT r.id, s.name AS name_of_student,
                       e.speaker_name AS alumni_speaker_name,
                       r.aspect_most_valuable,
                       r.improvements_suggestions, r.future_topics,
                       r.session_rating
                FROM feedback_responses r
                JOIN students s ON r.student_id = s.id
                JOIN events e ON r.event_id = e.id
                WHERE {" OR ".join(conditions)}
                ORDER BY r.submitted_at DESC
                LIMIT %s
            '''
            rows = execute_all(query, tuple(params + [limit]))
            for row in rows:
                row['similarity'] = 0.5
            return rows
        except Exception as e:
            logger.error(f'Fallback keyword search failed: {str(e)}')
            return []


# Module-level singleton (same as before)
rag_service = RAGService()
