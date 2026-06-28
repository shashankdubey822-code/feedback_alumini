"""
nlp_service.py — NLP analysis via OpenRouter API (google/gemini-2.5-flash:free).

Replaces local transformer models (RoBERTa, DeBERTa, KeyBERT, BAAI/bge).
All heavy ML libraries (torch, transformers, sentence-transformers, keybert, nltk)
have been removed. Sentiment, keyphrases, and actionability now come from a
single structured JSON call to the OpenRouter free-tier LLM.
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

# Optional TextBlob fallback for sentiment when API is unavailable
try:
    from textblob import TextBlob
    _TEXTBLOB_AVAILABLE = True
except ImportError:
    _TEXTBLOB_AVAILABLE = False

_OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
_FREE_MODEL = 'google/gemini-2.5-flash:free'


def _call_openrouter(prompt: str, system: str = None) -> Optional[str]:
    """Make a single OpenRouter API call. Returns response text or None on failure."""
    api_key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not api_key:
        logger.warning('OPENROUTER_API_KEY not set — NLP API calls will fail')
        return None
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    try:
        resp = requests.post(
            _OPENROUTER_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://mamta-feedback.hf.space',
                'X-Title': 'Alumni Feedback System',
            },
            json={
                'model': _FREE_MODEL,
                'messages': messages,
                'response_format': {'type': 'json_object'},
                'temperature': 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f'OpenRouter call failed: {e}')
        return None


class NLPService:
    """
    NLP analysis service — now powered by OpenRouter (google/gemini-2.5-flash:free).
    Public API is identical to the previous transformer-based implementation.
    """

    def __init__(self, min_word_length: int = 3, max_keywords: int = 10):
        self.min_word_length = min_word_length
        self.max_keywords = max_keywords
        # No model loading — all inference is remote via OpenRouter
        self.STOP_WORDS = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'shall',
            'it', 'its', 'i', 'we', 'you', 'he', 'she', 'they', 'them',
            'this', 'that', 'these', 'those', 'my', 'our', 'your', 'their',
            'very', 'also', 'just', 'more', 'about', 'like', 'really', 'so',
            'na', 'n/a', 'pls', 'please', 'ok', 'okay', 'good', 'great', 'nice',
            'thanks', 'thank', 'no', 'yes', 'feedback', 'session',
        }

    # ------------------------------------------------------------------
    # Public methods (same signatures as before)
    # ------------------------------------------------------------------

    def is_non_answer(self, text: str) -> bool:
        """Returns True if text is noise/filler and should be skipped."""
        if not text or not isinstance(text, str):
            return True
        text = text.strip()
        if not text or len(text) <= 2:
            return True
        # Quick heuristic for common noise patterns (no API needed)
        noise_patterns = [
            r'^(ok|okay|nil|na|n/a|none|nothing|no|yes|good|fine|great|\.+)$',
            r'^[^a-zA-Z]*$',
        ]
        cleaned = text.strip().lower()
        for pat in noise_patterns:
            if re.match(pat, cleaned):
                return True
        if len(cleaned.split()) <= 1:
            return True
        # API call for ambiguous multi-word cases
        result = _call_openrouter(
            f'Is this student feedback a non-answer (noise/filler/too vague to be useful)?\n'
            f'Text: "{text[:300]}"\n'
            f'Return JSON: {{"is_non_answer": true}} or {{"is_non_answer": false}}'
        )
        if result:
            try:
                return json.loads(result).get('is_non_answer', False)
            except Exception:
                pass
        return False

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment. Returns {polarity, subjectivity, label}."""
        if not text or not text.strip():
            return {'polarity': 0.0, 'subjectivity': 0.0, 'label': 'NEUTRAL'}
        if self.is_non_answer(text):
            return {'polarity': 0.0, 'subjectivity': 0.0, 'label': 'NO_RESPONSE'}

        result = _call_openrouter(
            f'Analyze the sentiment of this student feedback about an alumni speaker session.\n'
            f'Text: "{text[:500]}"\n'
            f'Return JSON: {{'
            f'"sentiment_label": "POSITIVE" or "NEUTRAL" or "NEGATIVE",'
            f'"polarity": <float from -1.0 to 1.0>,'
            f'"subjectivity": <float from 0.0 to 1.0>'
            f'}}'
        )
        if result:
            try:
                parsed = json.loads(result)
                return {
                    'polarity': float(parsed.get('polarity', 0.0)),
                    'subjectivity': float(parsed.get('subjectivity', 0.5)),
                    'label': parsed.get('sentiment_label', 'NEUTRAL'),
                }
            except Exception:
                pass
        # Fallback to TextBlob
        return self._textblob_sentiment(text)

    def get_sentiment(self, text: str) -> float:
        """Returns polarity score (-1.0 to 1.0)."""
        return self.analyze_sentiment(text).get('polarity', 0.0)

    def extract_keyphrases(self, text: str, limit: int = None) -> List[str]:
        """Extract key phrases from text using OpenRouter."""
        if not text or self.is_non_answer(text):
            return []
        limit = limit or self.max_keywords
        if len(text.split()) < 4:
            return self.extract_keywords(text, limit)

        result = _call_openrouter(
            f'Extract the {limit} most meaningful key phrases from this student feedback.\n'
            f'Text: "{text[:500]}"\n'
            f'Return JSON: {{"keyphrases": ["phrase1", "phrase2", ...]}}'
        )
        if result:
            try:
                phrases = json.loads(result).get('keyphrases', [])
                return [str(p).lower() for p in phrases[:limit]]
            except Exception:
                pass
        return self.extract_keywords(text, limit)

    def extract_keywords(self, text: str, limit: int = None) -> List[str]:
        """Simple frequency-based keyword extraction (no API needed)."""
        if not text:
            return []
        limit = limit or self.max_keywords
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in self.STOP_WORDS]
        freq = Counter(words)
        return [word for word, _ in freq.most_common(limit)]

    def extract_bigrams(self, texts: List[str], limit: int = 10) -> List[Tuple[str, str]]:
        """Counter-based bigram extraction (no API needed)."""
        all_bigrams: List[Tuple[str, str]] = []
        for text in texts:
            if not text:
                continue
            words = [w for w in re.findall(r'\b[a-z]{3,}\b', text.lower())
                     if w not in self.STOP_WORDS]
            all_bigrams.extend(zip(words, words[1:]))
        freq = Counter(all_bigrams)
        return Counter(all_bigrams).most_common(limit)

    def clean_text(self, text: str) -> str:
        """Clean text of special characters and extra whitespace."""
        if not text:
            return ''
        text = re.sub(r'[^\w\s.,!?-]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def calculate_text_statistics(self, text: str) -> Dict[str, Any]:
        """Return basic text statistics (no API needed)."""
        if not text:
            return {'length': 0, 'word_count': 0, 'avg_word_length': 0, 'sentence_count': 0}
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s for s in sentences if s.strip()]
        avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
        return {
            'length': len(text),
            'word_count': len(words),
            'avg_word_length': round(avg_word_len, 2),
            'sentence_count': len(sentences),
        }

    def batch_analyze_sentiment(self, texts: List[str]) -> List[Dict]:
        """Analyze sentiment for a list of texts (sequential API calls)."""
        return [self.analyze_sentiment(t) for t in texts]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _textblob_sentiment(self, text: str) -> Dict[str, Any]:
        """TextBlob fallback when OpenRouter is unavailable."""
        if _TEXTBLOB_AVAILABLE:
            try:
                blob = TextBlob(text)
                pol = blob.sentiment.polarity
                sub = blob.sentiment.subjectivity
                if pol > 0.1:
                    label = 'POSITIVE'
                elif pol < -0.1:
                    label = 'NEGATIVE'
                else:
                    label = 'NEUTRAL'
                return {'polarity': pol, 'subjectivity': sub, 'label': label}
            except Exception:
                pass
        return {'polarity': 0.0, 'subjectivity': 0.0, 'label': 'NEUTRAL'}


# Module-level singleton (same as before)
nlp_service = NLPService()
