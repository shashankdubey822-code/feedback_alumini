import re
from collections import Counter
from textblob import TextBlob
from utils.nlp_utils import is_opinion_column, is_non_answer, STOP_WORDS

def build_sentiment(df, column_types, columns):
    results = []
    
    for col in columns:
        ctype = column_types.get(col, 'text')
        if ctype not in ('text', 'categorical'):
            continue

        if not is_opinion_column(col):
            continue

        values = df[col].astype(str).str.strip()
        values = values[values.apply(lambda v: not is_non_answer(v))]
        values = values[values.str.len() > 3].tolist()

        if len(values) < 3:
            continue

        sentiments = []
        for text in values:
            try:
                blob = TextBlob(str(text))
                sentiments.append({
                    'polarity': round(blob.sentiment.polarity, 3),
                    'subjectivity': round(blob.sentiment.subjectivity, 3),
                })
            except Exception:
                continue

        if not sentiments:
            continue

        polarities = [s['polarity'] for s in sentiments]
        subjectivities = [s['subjectivity'] for s in sentiments]

        positive = sum(1 for p in polarities if p > 0.1)
        neutral = sum(1 for p in polarities if -0.1 <= p <= 0.1)
        negative = sum(1 for p in polarities if p < -0.1)

        original_count = len(df[col].astype(str).str.strip())
        non_answer_count = original_count - len(values) - df[col].astype(str).str.strip().eq('').sum()

        results.append({
            'column': col,
            'avgPolarity': round(sum(polarities) / len(polarities), 3),
            'avgSubjectivity': round(sum(subjectivities) / len(subjectivities), 3),
            'positive': positive,
            'neutral': neutral,
            'negative': negative,
            'total': len(sentiments),
            'nonAnswers': max(0, non_answer_count),
            'distribution': {
                'labels': ['Positive', 'Neutral', 'Negative'],
                'data': [positive, neutral, negative],
            },
        })

    return results

def build_keywords(df, column_types, columns):
    results = []

    for col in columns:
        ctype = column_types.get(col, 'text')
        if ctype not in ('text', 'categorical'):
            continue

        if not is_opinion_column(col):
            continue

        values = df[col].astype(str).str.strip()
        values = values[values.apply(lambda v: not is_non_answer(v))]
        values = values[values.str.len() > 3]

        if len(values) < 3:
            continue

        all_words = []
        all_bigrams = []

        for text in values:
            words = re.findall(r'[a-zA-Z]{3,}', text.lower())
            words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
            all_words.extend(words)

            if len(words) >= 2:
                for i in range(len(words) - 1):
                    bigram = f'{words[i]} {words[i+1]}'
                    all_bigrams.append(bigram)

        if not all_words:
            continue

        word_freq = Counter(all_words)
        bigram_freq = Counter(all_bigrams)

        top_words = [{'text': w, 'count': c, 'type': 'word'}
                     for w, c in word_freq.most_common(20)]

        top_bigrams = [{'text': b, 'count': c, 'type': 'bigram'}
                       for b, c in bigram_freq.most_common(10) if c >= 2]

        combined = sorted(top_bigrams + top_words,
                         key=lambda x: x['count'], reverse=True)[:25]

        if len(combined) < 2:
            continue

        results.append({
            'column': col,
            'words': combined,
        })

    return results
