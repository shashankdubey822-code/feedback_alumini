import pandas as pd
from textblob import TextBlob
from utils.nlp_utils import is_opinion_column, is_non_answer

def build_speaker_stats(df, column_types, columns):
    results = []

    speaker_cols = [c for c in columns if column_types.get(c) == 'categorical'
                    and any(kw in c.lower() for kw in ['speaker', 'alumni', 'instructor',
                                                         'teacher', 'presenter', 'mentor'])]

    numeric_cols = [c for c in columns if column_types.get(c) == 'numeric']

    text_cols = [c for c in columns if column_types.get(c) in ('text', 'categorical')
                 and is_opinion_column(c) and c not in speaker_cols]

    for speaker_col in speaker_cols:
        speakers = df[speaker_col].astype(str).str.strip()
        unique_speakers = speakers[speakers.ne('') & speakers.ne('NA')].unique()

        speaker_data = []
        for speaker in unique_speakers:
            mask = speakers == speaker
            speaker_rows = df[mask]
            entry = {
                'name': speaker,
                'count': int(mask.sum()),
                'ratings': {},
                'sentiment': 0,
            }

            for num_col in numeric_cols:
                nums = pd.to_numeric(speaker_rows[num_col].astype(str).str.strip(),
                                     errors='coerce').dropna()
                if len(nums) > 0:
                    entry['ratings'][num_col] = round(nums.mean(), 2)

            all_text = []
            for text_col in text_cols:
                texts = speaker_rows[text_col].astype(str).str.strip()
                texts = texts[texts.apply(lambda v: not is_non_answer(v))]
                texts = texts[texts.str.len() > 3]
                all_text.extend(texts.tolist())

            if all_text:
                polarities = []
                for t in all_text:
                    try:
                        polarities.append(TextBlob(t).sentiment.polarity)
                    except Exception:
                        pass
                if polarities:
                    entry['sentiment'] = round(sum(polarities) / len(polarities), 3)

            speaker_data.append(entry)

        speaker_data.sort(key=lambda x: x['count'], reverse=True)

        results.append({
            'column': speaker_col,
            'speakers': speaker_data,
        })

    return results
