import pandas as pd
from utils.nlp_utils import is_opinion_column, is_non_answer
from utils.data_utils import parse_date_safe

def build_ai_insights(df, column_types, dept_map, columns):
    """Generate AI-powered text insights from the data."""
    insights = []
    numeric_cols = [c for c in columns if column_types.get(c) == 'numeric']

    # 1. High rating insight
    if numeric_cols:
        num_col = numeric_cols[0]
        nums = pd.to_numeric(df[num_col].astype(str).str.strip(), errors='coerce').dropna()
        if len(nums) > 10:
            avg = nums.mean()
            median = nums.median()
            max_val = nums.max()
            if avg >= (max_val * 0.8):
                insights.append({
                    'type': 'positive',
                    'icon': '✨',
                    'text': f'Overall satisfaction for "{num_col[:30]}" is exceptionally high. the average rating is {avg:.1f} (median {median:.1f}).',
                })
            elif avg <= (max_val * 0.5):
                insights.append({
                    'type': 'negative',
                    'icon': '⚠️',
                    'text': f'Attention needed for "{num_col[:30]}" — average rating is notably low at {avg:.2f}.',
                })

    # 2. Consensus / Variance
    if numeric_cols and len(numeric_cols) > 1:
        num_col2 = numeric_cols[1]
        nums2 = pd.to_numeric(df[num_col2].astype(str).str.strip(), errors='coerce').dropna()
        if len(nums2) > 10:
            std = nums2.std()
            if std < 0.6:
                insights.append({
                    'type': 'consensus',
                    'icon': '🤝',
                    'text': f'Strong consensus regarding "{num_col2[:30]}". the standard deviation is minimal ({std:.2f}), showing universal agreement.',
                })
            elif std > 1.2:
                insights.append({
                    'type': 'polarizing',
                    'icon': '⚖️',
                    'text': f'Polarizing feedback for "{num_col2[:30]}". Highly scattered scores (std dev: {std:.2f}) indicate a mixed experience.',
                })

    # 3. Department / Categorical Insight
    for col in columns:
        if column_types.get(col) == 'categorical' and 'speaker' not in col.lower():
            use_col = col + ' (Normalized)' if col in dept_map else col
            if use_col in df.columns:
                top_dept = df[use_col][df[use_col].ne('')].value_counts()
                if len(top_dept) >= 2:
                    insights.append({
                        'type': 'department',
                        'icon': '🏫',
                        'text': f'{top_dept.index[0]} had the most responses ({top_dept.iloc[0]}), followed by {top_dept.index[1]} ({top_dept.iloc[1]}). {len(top_dept)} departments participated.',
                    })
                break

    # 4. Speaker insights
    speaker_cols = [c for c in columns if column_types.get(c) == 'categorical'
                    and any(kw in c.lower() for kw in ['speaker', 'alumni'])]
    for speaker_col in speaker_cols:
        speakers = df[speaker_col].astype(str).str.strip()
        speakers = speakers[speakers.ne('') & speakers.ne('NA')]
        top_speakers = speakers.value_counts()

        if len(top_speakers) >= 2 and len(numeric_cols) > 0:
            num_col = numeric_cols[0]
            nums = pd.to_numeric(df[num_col].astype(str).str.strip(), errors='coerce')
            temp = pd.DataFrame({'speaker': df[speaker_col], 'rating': nums}).dropna()
            temp = temp[temp['speaker'].ne('') & temp['speaker'].ne('NA')]
            speaker_avg = temp.groupby('speaker')['rating'].mean().sort_values(ascending=False)

            if len(speaker_avg) >= 1:
                best = speaker_avg.index[0]
                best_rating = round(speaker_avg.iloc[0], 2)
                worst = speaker_avg.index[-1]
                worst_rating = round(speaker_avg.iloc[-1], 2)

                insights.append({
                    'type': 'speaker',
                    'icon': '🎤',
                    'text': f'{best} received the highest avg rating ({best_rating}). {worst} received the lowest ({worst_rating}). {len(top_speakers)} speakers participated.',
                })
        break

    # 5. Feedback quality
    for col in columns:
        if is_opinion_column(col) and column_types.get(col) in ('text', 'categorical'):
            vals = df[col].astype(str).str.strip()
            vals = vals[vals.ne('')]
            total_responses = len(vals)
            non_answers = vals.apply(is_non_answer).sum()
            real_feedback = total_responses - non_answers

            if total_responses > 5 and non_answers > 0:
                pct_real = round(real_feedback / total_responses * 100, 0)
                insights.append({
                    'type': 'feedback_quality',
                    'icon': '🧹',
                    'text': f'For "{col[:40]}": {int(non_answers)} of {total_responses} responses were non-answers (No, NA, Nil, etc.). {int(pct_real)}% gave real feedback.',
                })

    # 6. Time span
    for col in columns:
        if column_types.get(col) == 'date':
            dates = df[col].astype(str).apply(parse_date_safe).dropna()
            if len(dates) >= 2:
                earliest = dates.min()
                latest = dates.max()
                span = (latest - earliest).days
                months = span // 30
                insights.append({
                    'type': 'timespan',
                    'icon': '📅',
                    'text': f'Data spans {span} days (~{months} months), from {earliest.strftime("%b %d, %Y")} to {latest.strftime("%b %d, %Y")}.',
                })
            break

    return insights
