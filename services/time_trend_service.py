import pandas as pd
from utils.data_utils import parse_date_safe

def build_time_trends(df, column_types, columns):
    results = []
    date_cols = [c for c in columns if column_types.get(c) == 'date']
    numeric_cols = [c for c in columns if column_types.get(c) == 'numeric']

    for date_col in date_cols:
        dates = df[date_col].astype(str).apply(parse_date_safe)
        valid = dates.dropna()

        if len(valid) < 3:
            continue

        temp_df = pd.DataFrame({'date': valid})
        temp_df['month'] = temp_df['date'].dt.to_period('M')
        monthly = temp_df.groupby('month').size().reset_index(name='count')
        monthly['month_str'] = monthly['month'].astype(str)

        trend = {
            'dateColumn': date_col,
            'responseCount': {
                'labels': monthly['month_str'].tolist(),
                'data': monthly['count'].tolist(),
                'xLabel': 'Month',
                'yLabel': 'Number of Responses',
            },
            'ratingTrends': [],
        }

        for num_col in numeric_cols:
            nums = pd.to_numeric(df[num_col].astype(str).str.strip(), errors='coerce')
            temp2 = pd.DataFrame({'date': dates, 'value': nums}).dropna()
            temp2['month'] = temp2['date'].dt.to_period('M')
            monthly_avg = temp2.groupby('month')['value'].mean().reset_index()
            monthly_avg['month_str'] = monthly_avg['month'].astype(str)

            if len(monthly_avg) >= 2:
                trend['ratingTrends'].append({
                    'column': num_col,
                    'labels': monthly_avg['month_str'].tolist(),
                    'data': [round(v, 2) for v in monthly_avg['value'].tolist()],
                    'xLabel': 'Month',
                    'yLabel': f'Average {num_col[:25]}',
                })

        results.append(trend)

    return results
