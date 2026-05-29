"""
RAG Service - Computes embeddings locally and performs semantic vector search
"""

from typing import List, Dict, Any, Optional
import numpy as np
from backend.utils.logger import get_section_logger
from backend.utils.supabase_helper import get_supabase_client, is_supabase_active
from backend.utils import pg_helper as sqlite3
import json

logger = get_section_logger('rag')

import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings

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
                _embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=gemini_key)
                logger.info("Gemini Embedding model loaded successfully.")
                return _embedding_model
            except Exception as e:
                logger.error(f"Failed to load Gemini embeddings: {str(e)}")
                
        try:
            logger.info("Loading local sentence-transformers/all-MiniLM-L6-v2 embedding model...")
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Local embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {str(e)}")
            _embedding_model = False  # Flag load failure
    return _embedding_model

class RAGService:
    """Handles vector embeddings and semantic search on SQLite or Supabase"""

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
                # Ensure 384 dimensions if Supabase uses 384! Gemini is 768
                return [float(x) for x in embedding[:384]]
            else:
                # Local SentenceTransformer
                embedding = model.encode(text.strip(), convert_to_numpy=True)
                return [float(x) for x in embedding]
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None

    def search_similar_feedback(self, query_text: str, limit: int = 5, threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Execute semantic search for feedback matching the query text.
        Routes to Supabase RPC 'match_feedback' if active, otherwise runs local SQL search.
        """
        # If Supabase is not active, skip generating the embedding (which loads the slow SentenceTransformer model)
        # and go straight to the fast fallback keyword search.
        if not is_supabase_active():
            logger.info("Supabase not active. Skipping slow local embedding generation and using fast keyword search.")
            return self._fallback_keyword_search(query_text, limit)

        query_vector = self.generate_embedding(query_text)
        if not query_vector:
            # Fallback to simple keyword search
            return self._fallback_keyword_search(query_text, limit)

        # ─── 1. SUPABASE VECTOR SEARCH (RPC) ──────────────────────────────────
        if is_supabase_active():
            client = get_supabase_client()
            if client:
                try:
                    logger.info(f"Executing Supabase pgvector RPC search for query: '{query_text}'")
                    response = client.rpc(
                        'match_feedback',
                        {
                            'query_embedding': query_vector,
                            'match_threshold': threshold,
                            'match_count': limit
                        }
                    ).execute()
                    return response.data or []
                except Exception as e:
                    logger.error(f"Supabase pgvector query failed: {str(e)}")
                    # Fallback to local
        
        # ─── 2. LOCAL SQLITE FALLBACK ─────────────────────────────────────────
        logger.info(f"Running local SQLite search fallback for query: '{query_text}'")
        from backend.config import get_config
        db_path = get_config()().DATABASE_PATH
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Simple fallback: retrieve rows that have keywords or run a simple cosine
            # similarity search if we have embeddings stored locally in the JSON payload
            cursor.execute('''
                SELECT id, name_of_student, alumni_speaker_name, aspect_most_valuable, improvements_suggestions, future_topics, session_rating, dl_keywords
                FROM dashboard_data
                LIMIT 500
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            # Perform python-side cosine similarity if local vectors are present
            scored_results = []
            for r in rows:
                row_dict = dict(r)
                # Check if we have a vector saved in dl_keywords (e.g. if we cached it locally)
                saved_vector = None
                try:
                    kw_payload = json.loads(row_dict.get('dl_keywords') or '{}')
                    if isinstance(kw_payload, dict) and 'embedding' in kw_payload:
                        saved_vector = kw_payload['embedding']
                except:
                    pass
                
                if saved_vector and len(saved_vector) == len(query_vector):
                    # Compute cosine similarity
                    v1 = np.array(query_vector)
                    v2 = np.array(saved_vector)
                    sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                    if sim > threshold:
                        row_dict['similarity'] = sim
                        scored_results.append(row_dict)
            
            if scored_results:
                scored_results.sort(key=lambda x: x['similarity'], reverse=True)
                return scored_results[:limit]
                
            # If no embeddings, fall back to regex/substring matches
            return self._fallback_keyword_search(query_text, limit)
            
        except Exception as e:
            logger.error(f"Local RAG search fallback failed: {str(e)}")
            return self._fallback_keyword_search(query_text, limit)

    def _fallback_keyword_search(self, query_text: str, limit: int) -> List[Dict[str, Any]]:
        """Simple substring database search in case vector models fail"""
        from backend.config import get_config
        import time
        db_path = get_config()().DATABASE_PATH
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            tokens = [f"%{t}%" for t in query_text.lower().split() if len(t) > 2]
            if not tokens:
                tokens = [f"%{query_text.lower()}%"]
                
            conditions = []
            params = []
            for t in tokens:
                conditions.append("(alumni_speaker_name LIKE ? OR aspect_most_valuable LIKE ? OR improvements_suggestions LIKE ? OR future_topics LIKE ?)")
                params.extend([t, t, t, t])
                
            query = f'''
                SELECT id, name_of_student, alumni_speaker_name, aspect_most_valuable, improvements_suggestions, future_topics, session_rating
                FROM dashboard_data
                WHERE {' OR '.join(conditions)}
                LIMIT ?
            '''
            params.append(limit)
            cursor.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            
            for r in rows:
                r['similarity'] = 0.5  # Neutral default score for substring matches
            return rows
        except Exception as e:
            logger.error(f"Fallback keyword search failed: {str(e)}")
            return []
