import pandas as pd
from utils.data_utils import parse_date_safe

def build_kpis(df, column_types, columns, total_original):
    kpis = []

    kpis.append({
        'label': 'Total Records',
        'value': len(df),
        'sub': f'out of {total_original} total',
        'icon': 'records',
    })

    for col in columns:
        col_lower = col.lower()
        if "did the session help you" in col_lower:
            continue
            
        ctype = column_types.get(col, 'text')
        values = df[col].astype(str).str.strip()
        values = values[values.ne('') & values.ne('NA') & values.ne('N/A')
                        & values.ne('-') & values.ne('.') & values.ne('na')]

        if ctype == 'numeric':
            nums = pd.to_numeric(values, errors='coerce').dropna()
            if len(nums) > 0:
                avg = round(nums.mean(), 2)
                kpis.append({
                    'label': f'Avg {col[:25]}',
                    'value': avg,
                    'sub': f'Min: {nums.min()} | Max: {nums.max()} | Median: {round(nums.median(), 1)}',
                    'icon': 'numeric',
                })
        elif ctype == 'date':
            dates = values.apply(parse_date_safe).dropna()
            if len(dates) > 0:
                earliest = dates.min().strftime('%Y-%m-%d')
                latest = dates.max().strftime('%Y-%m-%d')
                kpis.append({
                    'label': col[:25],
                    'value': f'{len(dates)} dates',
                    'sub': f'{earliest} → {latest}',
                    'icon': 'date',
                })
        elif ctype == 'categorical':
            unique_count = values.nunique()
            top_val = values.mode().iloc[0] if len(values) > 0 else ''
            kpis.append({
                'label': col[:25],
                'value': f'{unique_count} unique',
                'sub': f'Top: {str(top_val)[:20]}',
                'icon': 'category',
            })
            
    return kpis[:8]  # Limit to 8 KPIs max for UI layout
