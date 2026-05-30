"""
NLP Service - Natural Language Processing and text analysis
Handles sentiment analysis, keyword extraction, and non-answer detection.

Models used:
  - Sentiment: cardiffnlp/twitter-roberta-base-sentiment-latest
      Trained on short-form social/feedback text; outputs positive/neutral/negative natively.
  - Keywords: KeyBERT (sentence-transformers/all-MiniLM-L6-v2 backend)
      Embedding-based keyphrase extraction; far more accurate than TextBlob noun phrases.
  - Fallback: TextBlob polarity for is_non_answer heuristic only.
"""

import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
import nltk
from textblob import TextBlob

# ── NLTK data bootstrap ──────────────────────────────────────────────────────
for _resource, _path in [
    ('punkt_tab',  'tokenizers/punkt_tab'),
    ('stopwords',  'corpora/stopwords'),
    ('brown',      'corpora/brown'),
    ('wordnet',    'corpora/wordnet'),
]:
    try:
        nltk.data.find(_path)
    except LookupError:
        nltk.download(_resource, quiet=True)

from nltk.corpus import stopwords


class NLPService:
    """Handle NLP operations: sentiment analysis, keyword extraction, text cleaning."""

    # ── Non-answer patterns ──────────────────────────────────────────────────
    NON_ANSWER_PATTERNS = [
        r'^n[/\\]?a\.?$', r'^na\.?$', r'^no\.?$', r'^nil\.?$', r'^none\.?$',
        r'^nope\.?$', r'^ok\.?$', r'^okay\.?$', r'^-+$', r'^\.$',
        r'^nothing\.?$', r'^nothing\s+(all\s+)?perfect\.?$', r'^all\s+perfect\.?$',
        r'^no\s+suggestion[s]?\.?$', r'^no\s+comment[s]?\.?$', r'^not\s+any\.?$',
        r'^good\.?$', r'^all\s+good\.?$', r'^fine\.?$', r'^no\s+improvement[s]?\.?$',
    ]
    NON_ANSWER_COMPILED = [re.compile(p, re.IGNORECASE) for p in NON_ANSWER_PATTERNS]

    # ── Stop words ───────────────────────────────────────────────────────────
    STOP_WORDS = set(stopwords.words('english'))
    STOP_WORDS.update([
        'na', 'n/a', 'pls', 'please', 'ok', 'okay', 'good', 'great', 'nice',
        'thanks', 'thank', 'no', 'yes', 'feedback', 'session', 'v', 'b', 'c', 'n',
        'related', 'domain', 'area', 'topics', 'field', 'like', 'aspect',
        'subjects', 'about', 'more', 'would', 'also', 'make', 'really',
        'everything', 'every', 'lot', 'much', 'get', 'got', 'well', 'can', 'one',
    ])

    def __init__(self, min_word_length: int = 3, max_keywords: int = 10):
        self.min_word_length = min_word_length
        self.max_keywords = max_keywords

        # ── Sentiment model (RoBERTa, 3-class) ──────────────────────────────
        self.sentiment_model = None
        self._sentiment_id2label: Dict[int, str] = {}
        try:
            from transformers import pipeline, AutoConfig
            _model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
            _cfg = AutoConfig.from_pretrained(_model_name)
            self._sentiment_id2label = {int(k): v for k, v in _cfg.id2label.items()}
            self.sentiment_model = pipeline(
                "sentiment-analysis",
                model=_model_name,
                tokenizer=_model_name,
                truncation=True,
                max_length=512,
            )
        except Exception:
            pass  # Falls back to TextBlob

        # ── KeyBERT (lazy-loaded on first use) ───────────────────────────────
        self._kw_model = None

    # ── KeyBERT lazy loader ──────────────────────────────────────────────────
    def _get_kw_model(self):
        if self._kw_model is None:
            try:
                from keybert import KeyBERT
                self._kw_model = KeyBERT(model="all-MiniLM-L6-v2")
            except Exception:
                pass
        return self._kw_model

    # ── Non-answer detection ─────────────────────────────────────────────────
    def is_non_answer(self, text: str) -> bool:
        if not text or not isinstance(text, str):
            return True
        text = text.strip()
        if not text:
            return True
        for pattern in self.NON_ANSWER_COMPILED:
            if pattern.match(text):
                return True
        if len(text) <= 5:
            try:
                polarity = TextBlob(text).sentiment.polarity
                if -0.2 <= polarity <= 0.2:
                    return True
            except Exception:
                pass
        return False

    # ── Sentiment analysis ───────────────────────────────────────────────────
    def analyze_sentiment(self, text: str) -> Dict:
        """
        Returns {'polarity': float, 'subjectivity': float, 'label': str}.
        label is one of: POSITIVE | NEUTRAL | NEGATIVE | NO_RESPONSE | ERROR
        """
        if not text or self.is_non_answer(text):
            return {'polarity': 0.0, 'subjectivity': 0.0, 'label': 'NO_RESPONSE'}

        try:
            if self.sentiment_model:
                result = self.sentiment_model(text[:512])[0]
                raw_label: str = result['label'].lower()   # e.g. "positive", "neutral", "negative"
                score: float   = result['score']

                # Normalise to uppercase canonical labels
                if 'positive' in raw_label:
                    label    = 'POSITIVE'
                    polarity = score
                elif 'negative' in raw_label:
                    label    = 'NEGATIVE'
                    polarity = -score
                else:
                    label    = 'NEUTRAL'
                    polarity = 0.0

                return {
                    'polarity':     round(polarity, 3),
                    'subjectivity': round(score, 3),
                    'label':        label,
                }

            # ── TextBlob fallback ────────────────────────────────────────────
            blob     = TextBlob(text)
            polarity = round(blob.sentiment.polarity, 3)
            label    = 'POSITIVE' if polarity > 0.1 else ('NEGATIVE' if polarity < -0.1 else 'NEUTRAL')
            return {
                'polarity':     polarity,
                'subjectivity': round(blob.sentiment.subjectivity, 3),
                'label':        label,
            }

        except Exception:
            return {'polarity': 0.0, 'subjectivity': 0.0, 'label': 'ERROR'}

    def get_sentiment(self, text: str) -> float:
        return self.analyze_sentiment(text)['polarity']

    # ── Keyword extraction (unigrams, fast) ──────────────────────────────────
    def extract_keywords(self, text: str, limit: int = None) -> List[str]:
        """Simple unigram extraction — used as fallback for very short texts."""
        if not text or self.is_non_answer(text):
            return []
        limit = limit or self.max_keywords
        try:
            words = [
                w.strip('.,!?"\'()-—')
                for w in text.lower().split()
            ]
            words = [w for w in words if len(w) >= self.min_word_length and w not in self.STOP_WORDS]
            if not words:
                return []
            return [w for w, _ in Counter(words).most_common(limit)]
        except Exception:
            return []

    # ── Keyphrase extraction (KeyBERT) ────────────────────────────────────────
    def extract_keyphrases(self, text: str, limit: int = None) -> List[str]:
        """
        Embedding-based keyphrase extraction via KeyBERT.
        Falls back to unigram extraction if KeyBERT is unavailable or text is too short.
        """
        if not text or self.is_non_answer(text):
            return []
        limit = limit or self.max_keywords

        # KeyBERT needs at least a few words to be meaningful
        word_count = len(text.split())
        kw_model = self._get_kw_model() if word_count >= 4 else None

        if kw_model:
            try:
                results = kw_model.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 2),
                    stop_words='english',
                    top_n=limit,
                    use_mmr=True,       # Maximal Marginal Relevance for diversity
                    diversity=0.5,
                )
                # results: List[Tuple[str, float]]
                return [phrase for phrase, _score in results if phrase]
            except Exception:
                pass

        # Fallback: unigrams
        return self.extract_keywords(text, limit)

    # ── Bigram extraction ─────────────────────────────────────────────────────
    def extract_bigrams(self, texts: List[str], limit: int = 10) -> List[Tuple[str, str]]:
        bigrams: List[Tuple[str, str]] = []
        for text in texts:
            if text and not self.is_non_answer(text):
                try:
                    words = [
                        w.strip('.,!?"\'()-—')
                        for w in text.lower().split()
                    ]
                    words = [w for w in words if len(w) >= self.min_word_length and w not in self.STOP_WORDS]
                    for i in range(len(words) - 1):
                        bigrams.append((words[i], words[i + 1]))
                except Exception:
                    continue
        if not bigrams:
            return []
        return Counter(bigrams).most_common(limit)

    # ── Utilities ─────────────────────────────────────────────────────────────
    def clean_text(self, text: str) -> str:
        if not text:
            return ''
        text = ' '.join(text.split())
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        return text.strip()

    def calculate_text_statistics(self, text: str) -> Dict:
        if not text:
            return {'length': 0, 'word_count': 0, 'avg_word_length': 0, 'sentence_count': 0}
        sentences  = len(re.split(r'[.!?]+', text.strip()))
        words      = text.split()
        word_count = len(words)
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0
        return {
            'length':          len(text),
            'word_count':      word_count,
            'avg_word_length': round(avg_word_length, 2),
            'sentence_count':  sentences,
        }

    def batch_analyze_sentiment(self, texts: List[str]) -> List[Dict]:
        return [self.analyze_sentiment(t) for t in texts]
