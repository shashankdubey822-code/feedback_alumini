from services.kpi_service import build_kpis
from services.chart_service import build_chart_data
from services.nlp_service import build_sentiment, build_keywords
from services.time_trend_service import build_time_trends
from services.speaker_service import build_speaker_stats
from services.ai_insight_service import build_ai_insights
from utils.data_utils import parse_date_safe

def build_table_data(df, columns):
    """Format DataFrame directly to list of dicts for the frontend data table."""
    try:
        # Use pandas built-in orientation for records (list of dicts)
        # Handle nan values by replacing with empty string before converting
        clean_df = df[columns].fillna('')
        return clean_df.to_dict('records')
    except Exception as e:
        print(f"Error building table data: {e}")
        return []

def build_filter_options(df_original, column_types, columns, is_non_answer):
    filters = []

    for col in columns:
        ctype = column_types.get(col, 'text')
        f = {'column': col, 'type': ctype}

        if ctype == 'categorical':
            values = df_original[col].astype(str).str.strip()
            values = values[values.ne('') & values.ne('NA')]
            # Filter out non-answers
            values = values[values.apply(lambda v: not is_non_answer(v))]
            freq = values.value_counts().head(50)
            f['options'] = [{'value': v, 'count': int(c)} for v, c in freq.items()]
        elif ctype == 'date':
            dates = df_original[col].astype(str).apply(parse_date_safe).dropna()
            if len(dates) > 0:
                unique_dates = sorted(dates.dt.strftime('%Y-%m-%d').unique())
                f['options'] = unique_dates

        filters.append(f)

    return filters

def build_analytics(df, current_data, column_types, dept_map, original_columns, is_non_answer):
    """Orchestrates all analytics builder functions."""
    total_rows = len(df)
    total_original = len(current_data['original_df'])

    result = {
        'meta': {
            'totalRows': total_rows,
            'totalOriginal': total_original,
            'totalColumns': len(original_columns),
            'columns': original_columns,
            'columnTypes': column_types,
            'filename': current_data['filename'],
        },
        'kpis': build_kpis(df, column_types, original_columns, total_original),
        'charts': build_chart_data(df, column_types, dept_map, original_columns),
        'sentiment': build_sentiment(df, column_types, original_columns),
        'keywords': build_keywords(df, column_types, original_columns),
        'timeTrends': build_time_trends(df, column_types, original_columns),
        'speakerStats': build_speaker_stats(df, column_types, original_columns),
        'tableData': build_table_data(df, original_columns),
        'filters': build_filter_options(current_data['original_df'], column_types, original_columns, is_non_answer),
        'aiInsights': build_ai_insights(df, column_types, dept_map, original_columns),
    }

    return result
