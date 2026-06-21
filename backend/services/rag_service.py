"""
RAG Service - Computes embeddings locally and performs semantic vector search
"""

from typing import List, Dict, Any, Optional
from backend.utils.logger import get_section_logger
from backend.utils.insforge_helper import is_insforge_active
from backend.utils.insforge_db import execute_all
import json

logger = get_section_logger('rag')

import os

# Lazy-loaded sentence transformer model
_embedding_model = None

def _get_embedding_model():
    """Load embedding model: Use Gemini if available, else local SentenceTransformer"""
    global _embedding_model
    if _embedding_model is None:
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            try:
                logger.info("Loading Gemini Embedding model (faster, no local download)...")
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                _embedding_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview", google_api_key=gemini_key)
                logger.info("Gemini Embedding model loaded successfully.")
                return _embedding_model
            except Exception as e:
                logger.error(f"Failed to load Gemini embeddings: {str(e)}")
                
        try:
            logger.info("Loading local sentence-transformers/all-mpnet-base-v2 embedding model...")
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-mpnet-base-v2')
            logger.info("Local embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {str(e)}")
            _embedding_model = False  # Flag load failure
    return _embedding_model

class RAGService:
    """Handles vector embeddings and semantic search on SQLite or InsForge"""

    def __init__(self):
        pass

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a float vector for a given text block"""
        if not text or not text.strip():
            return None

        model = _get_embedding_model()
        if not model:
            logger.warning("Embedding model is unavailable. Cannot generate vector.")
            return None

        try:
            # Check if using LangChain Gemini Embeddings
            if hasattr(model, 'embed_query'):
                embedding = model.embed_query(text.strip())
                # Truncate to first 768 dimensions (leveraging Matryoshka Representation Learning)
                return [float(x) for x in embedding[:768]]
            else:
                # Local SentenceTransformer (all-mpnet-base-v2 is 768 dims)
                embedding = model.encode(text.strip(), convert_to_numpy=True)
                return [float(x) for x in embedding[:768]]
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
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
            logger.info("InsForge not active. Using fast keyword search fallback.")
            return self._fallback_keyword_search(query_text, limit)

        query_vector = self.generate_embedding(query_text)
        if not query_vector:
            return self._fallback_keyword_search(query_text, limit)

        try:
            logger.info(
                f"pgvector search: '{query_text}' | year={filter_year} "
                f"sem={filter_semester} dept={filter_dept}"
            )
            rows = execute_all(
                "SELECT * FROM match_feedback_filtered(%s::vector, %s, %s, %s, %s, %s)",
                (str(query_vector), threshold, limit, filter_year, filter_semester, filter_dept),
            )
            if rows:
                logger.info(f"pgvector returned {len(rows)} results.")
                return rows
            # No vector results — fall back
            logger.warning("pgvector returned 0 results. Embeddings may not be populated yet.")
        except Exception as e:
            logger.error(f"pgvector search failed: {str(e)}")

        return self._fallback_keyword_search(query_text, limit)

    def _fallback_keyword_search(self, query_text: str, limit: int) -> List[Dict[str, Any]]:
        """Simple InsForge-backed substring search in case vector models fail"""
        try:
            tokens = [f"%{t}%" for t in query_text.lower().split() if len(t) > 2]
            if not tokens:
                tokens = [f"%{query_text.lower()}%"]

            conditions = []
            params = []
            for t in tokens:
                conditions.append("(COALESCE(e.speaker_name, '') ILIKE %s OR COALESCE(r.aspect_most_valuable, '') ILIKE %s OR COALESCE(r.improvements_suggestions, '') ILIKE %s OR COALESCE(r.future_topics, '') ILIKE %s)")
                params.extend([t, t, t, t])

            query = f'''
                SELECT r.id, s.name AS name_of_student, e.speaker_name AS alumni_speaker_name, r.aspect_most_valuable,
                       r.improvements_suggestions, r.future_topics, r.session_rating
                FROM feedback_responses r
                JOIN students s ON r.student_id = s.id
                JOIN events e ON r.event_id = e.id
                WHERE {' OR '.join(conditions)}
                ORDER BY r.submitted_at DESC
                LIMIT %s
            '''
            rows = execute_all(query, tuple(params + [limit]))

            for row in rows:
                row['similarity'] = 0.5
            return rows
        except Exception as e:
            logger.error(f"Fallback keyword search failed: {str(e)}")
            return []
