import re

# ── NLTK Setup ──────────────────────────────────────────────────────
import nltk
from nltk.corpus import stopwords

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

STOP_WORDS = set(stopwords.words('english'))
STOP_WORDS.update([
    'na', 'n/a', 'nil', 'none', 'nothing', 'no', 'nope', 'ok', 'yes',
    '-', '.', 'the', 'and', 'was', 'for', 'all', 'more', 'would',
    'about', 'also', 'make', 'like', 'good', 'really', 'everything',
    'every', 'lot', 'much', 'get', 'got', 'well', 'can', 'one',
])

# ── AI: Non-Answer Detection Patterns ───────────────────────────────
NON_ANSWER_PATTERNS = [
    r'^n[/\\]?a\.?$',                          # NA, N/A, N\A
    r'^na\.?$',                                 # na
    r'^no\.?$',                                 # No, No.
    r'^nil\.?$',                                # Nil
    r'^none\.?$',                               # None
    r'^nope\.?$',                               # Nope
    r'^ok\.?$',                                 # Ok
    r'^okay\.?$',                               # Okay
    r'^-+$',                                    # -, --, ---
    r'^\.$',                                    # .
    r'^nothing\.?$',                            # Nothing
    r'^nothing\s+(all\s+)?perfect\.?$',         # Nothing all perfect
    r'^all\s+perfect\.?$',                      # All perfect
    r'^no\s+suggestion[s]?\.?$',               # No suggestions
    r'^no\s+comment[s]?\.?$',                  # No comments
    r'^not\s+any\.?$',                         # Not any
    r'^good\.?$',                               # Good (not real feedback)
    r'^all\s+good\.?$',                        # All good
    r'^fine\.?$',                               # Fine
    r'^no\s+improvement[s]?\.?$',              # No improvements
]

NON_ANSWER_COMPILED = [re.compile(p, re.IGNORECASE) for p in NON_ANSWER_PATTERNS]

# ── AI: Column Intent Detection ─────────────────────────────────────
OPINION_KEYWORDS = [
    'suggest', 'improve', 'recommend', 'feedback', 'comment', 'opinion',
    'valuable', 'help', 'gain', 'topic', 'aspect', 'rate', 'rating',
    'experience', 'thought', 'review', 'what',
]

IDENTIFIER_KEYWORDS = [
    'name', 'roll', 'id', 'number', 'date', 'time', 'timestamp',
    'department', 'dept', 'school', 'speaker', 'alumni', 'instructor',
]

def is_non_answer(text):
    """AI-powered non-answer detection using pattern matching + heuristics."""
    if not text or not isinstance(text, str):
        return True
    text = text.strip()
    if len(text) == 0:
        return True

    for pattern in NON_ANSWER_COMPILED:
        if pattern.match(text):
            return True

    if len(text.split()) <= 2 and len(text) <= 10:
        try:
            from textblob import TextBlob
            if -0.1 <= TextBlob(text).sentiment.polarity <= 0.1:
                return True
        except Exception:
            pass

    return False

def is_opinion_column(col_name):
    """Detect if a column likely contains subjective feedback."""
    name_lower = col_name.lower()
    if any(kw in name_lower for kw in IDENTIFIER_KEYWORDS):
        return False
    if any(kw in name_lower for kw in OPINION_KEYWORDS):
        return True
    return False

def is_department_like(col_name, series):
    name_lower = col_name.lower()
    dept_keywords = ['department', 'dept', 'school', 'faculty', 'program', 'course', 'branch']
    if any(kw in name_lower for kw in dept_keywords):
        return True
    unique = series[series.ne('')].str.lower().nunique()
    total = len(series[series.ne('')])
    if total > 0 and 5 < unique < total * 0.8:
        return True
    return False
