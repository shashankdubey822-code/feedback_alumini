"""
NLP Service - Natural Language Processing and text analysis
Handles sentiment analysis, keyword extraction, and non-answer detection
"""

import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
import nltk
from textblob import TextBlob

# Try to download required NLTK data
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

from nltk.corpus import stopwords


class NLPService:
    """Handle NLP operations: sentiment analysis, keyword extraction, text cleaning"""

    # Non-answer detection patterns
    NON_ANSWER_PATTERNS = [
        r'^n[/\\]?a\.?$',
        r'^na\.?$',
        r'^no\.?$',
        r'^nil\.?$',
        r'^none\.?$',
        r'^nope\.?$',
        r'^ok\.?$',
        r'^okay\.?$',
        r'^-+$',
        r'^\.$',
        r'^nothing\.?$',
        r'^nothing\s+(all\s+)?perfect\.?$',
        r'^all\s+perfect\.?$',
        r'^no\s+suggestion[s]?\.?$',
        r'^no\s+comment[s]?\.?$',
        r'^not\s+any\.?$',
        r'^good\.?$',
        r'^all\s+good\.?$',
        r'^fine\.?$',
        r'^no\s+improvement[s]?\.?$',
    ]

    NON_ANSWER_COMPILED = [re.compile(p, re.IGNORECASE) for p in NON_ANSWER_PATTERNS]

    # Stopwords and filters
    STOP_WORDS = set(stopwords.words('english'))
    STOP_WORDS.update([
        'na', 'n/a', 'nil', 'none', 'nothing', 'no', 'nope', 'ok', 'yes',
        '-', '.', 'the', 'and', 'was', 'for', 'all', 'more', 'would',
        'about', 'also', 'make', 'like', 'good', 'really', 'everything',
        'every', 'lot', 'much', 'get', 'got', 'well', 'can', 'one',
    ])

    def __init__(self, min_word_length: int = 3, max_keywords: int = 10):
        self.min_word_length = min_word_length
        self.max_keywords = max_keywords
        self.sentiment_model = None
        try:
            from transformers import pipeline
            # Load the lightweight DistilBERT sentiment model
            self.sentiment_model = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
        except ImportError:
            pass # Transformers not installed yet, will fallback

    def is_non_answer(self, text: str) -> bool:
        """Detect if text is a non-answer (NA, No, None, etc.)"""
        if not text or not isinstance(text, str):
            return True

        text = text.strip()
        if len(text) == 0:
            return True

        # Pattern matching
        for pattern in self.NON_ANSWER_COMPILED:
            if pattern.match(text):
                return True

        # Heuristic: very short + neutral sentiment
        if len(text) <= 5:
            from textblob import TextBlob
            polarity = TextBlob(text).sentiment.polarity
            if -0.2 <= polarity <= 0.2:
                return True

        return False

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text using HuggingFace Transformers (with TextBlob fallback)"""
        if not text or self.is_non_answer(text):
            return {
                'polarity': 0.0,
                'subjectivity': 0.0,
                'label': 'NO_RESPONSE'
            }

        try:
            if self.sentiment_model:
                # Truncate text to 512 tokens safely
                result = self.sentiment_model(text[:512])[0]
                label = result['label']
                score = result['score']
                
                # Convert to -1 to 1 polarity
                polarity = score if label == 'POSITIVE' else -score
                
                return {
                    'polarity': round(polarity, 3),
                    'subjectivity': round(score, 3), # Using confidence score as subjectivity proxy
                    'label': label
                }
            else:
                # Fallback to lexical approach if DL fails to load
                blob = TextBlob(text)
                polarity = round(blob.sentiment.polarity, 3)

                # Categorize sentiment
                if polarity > 0.1:
                    label = 'POSITIVE'
                elif polarity < -0.1:
                    label = 'NEGATIVE'
                else:
                    label = 'NEUTRAL'

                return {
                    'polarity': polarity,
                    'subjectivity': round(blob.sentiment.subjectivity, 3),
                    'label': label
                }
        except Exception as e:
            return {
                'polarity': 0.0,
                'subjectivity': 0.0,
                'label': 'ERROR'
            }

    def get_sentiment(self, text: str) -> float:
        """Get polarity score (-1 to 1)"""
        sentiment = self.analyze_sentiment(text)
        return sentiment['polarity']

    def extract_keywords(self, text: str, limit: int = None) -> List[str]:
        """Extract meaningful keywords from text"""
        if not text or self.is_non_answer(text):
            return []

        limit = limit or self.max_keywords

        try:
            # Tokenize and clean
            words = text.lower().split()
            words = [
                w.strip('.,!?"\'()-—')
                for w in words
                if w.strip('.,!?"\'()-—') and len(w.strip('.,!?"\'()-—')) >= self.min_word_length
            ]

            # Remove stopwords
            words = [w for w in words if w not in self.STOP_WORDS]

            # Count and return top keywords
            if not words:
                return []

            word_counts = Counter(words)
            return [word for word, _ in word_counts.most_common(limit)]
        except Exception:
            return []

    def extract_bigrams(self, texts: List[str], limit: int = 10) -> List[Tuple[str, str]]:
        """Extract common bigrams from multiple texts"""
        bigrams = []

        for text in texts:
            if text and not self.is_non_answer(text):
                try:
                    words = text.lower().split()
                    words = [
                        w.strip('.,!?"\'()-—')
                        for w in words
                        if w.strip('.,!?"\'()-—') and len(w.strip('.,!?"\'()-—')) >= self.min_word_length
                    ]
                    words = [w for w in words if w not in self.STOP_WORDS]

                    # Create bigrams
                    for i in range(len(words) - 1):
                        bigrams.append((words[i], words[i + 1]))
                except Exception:
                    continue

        # Count and return top bigrams
        if not bigrams:
            return []

        bigram_counts = Counter(bigrams)
        return bigram_counts.most_common(limit)

    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ''

        # Remove extra whitespace
        text = ' '.join(text.split())

        # Remove special characters (keep alphanumeric and basic punctuation)
        text = re.sub(r'[^\w\s.,!?-]', '', text)

        return text.strip()

    def calculate_text_statistics(self, text: str) -> Dict:
        """Calculate statistics about text"""
        if not text:
            return {
                'length': 0,
                'word_count': 0,
                'avg_word_length': 0,
                'sentence_count': 0,
            }

        sentences = len(re.split(r'[.!?]+', text.strip()))
        words = text.split()
        word_count = len(words)
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0

        return {
            'length': len(text),
            'word_count': word_count,
            'avg_word_length': round(avg_word_length, 2),
            'sentence_count': sentences,
        }

    def batch_analyze_sentiment(self, texts: List[str]) -> List[Dict]:
        """Analyze sentiment for multiple texts"""
        return [self.analyze_sentiment(text) for text in texts]
