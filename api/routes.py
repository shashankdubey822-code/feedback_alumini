import os
import json
from io import StringIO
import pandas as pd
from flask import Blueprint, request, jsonify

# Utils
from utils.nlp_utils import is_department_like, fuzzy_normalize, is_non_answer
from utils.data_utils import parse_date_safe, sanitize_for_json

# Services
from services.analytics import build_analytics

api_bp = Blueprint('api', __name__)

# Basic app state within the context of the blueprint
# In a real heavy multi-user app, this would be tied to sessions or DB
current_data = {
    'original_df': None,
    'filtered_df': None,
    'column_types': {},
    'dept_map': {},
    'filename': '',
    'original_columns': []
}

def detect_column_types(df):
    types = {}
    for col in df.columns:
        sample = df[col].dropna()
        if len(sample) == 0:
            types[col] = 'text'
            continue

        # Convert to string and strip for unified checking
        sample_str = sample.astype(str).str.strip()
        sample_str = sample_str[sample_str.ne('') & sample_str.ne('NA') & sample_str.ne('N/A') & sample_str.ne('-')]

        if len(sample_str) == 0:
            types[col] = 'text'
            continue

        # Check Date
        date_parsed = sample_str.apply(parse_date_safe)
        if date_parsed.notna().sum() > (len(sample_str) * 0.5):
            types[col] = 'date'
            continue

        # Check Numeric
        num_parsed = pd.to_numeric(sample_str, errors='coerce')
        if num_parsed.notna().sum() > (len(sample_str) * 0.8):
            types[col] = 'numeric'
            continue

        # Check Categorical (few unique values compared to total length, or specific names)
        unique_ratio = sample_str.nunique() / len(sample_str)
        if is_department_like(col, sample_str):
            types[col] = 'categorical'
        elif unique_ratio < 0.3 and sample_str.nunique() <= 20:
            types[col] = 'categorical'
        else:
            types[col] = 'text'

    return types

@api_bp.route('/upload', methods=['POST'])
def handle_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Only CSV files supported'})

    try:
        content = file.read().decode('utf-8')
        df = pd.read_csv(StringIO(content))

        original_columns = df.columns.tolist()
        df.columns = df.columns.str.strip()
        
        # Clean entire dataframe
        df = df.fillna('')
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()

        col_types = detect_column_types(df)

        dept_map = {}
        # Identify department-like columns and fuzzy normalize them
        for col, ctype in col_types.items():
            if ctype == 'categorical' and is_department_like(col, df[col]):
                mapping = fuzzy_normalize(df[col].tolist())
                if mapping:
                    norm_col = col + ' (Normalized)'
                    df[norm_col] = df[col].map(lambda x: mapping.get(str(x).strip(), x))
                    dept_map[col] = mapping

        current_data['original_df'] = df.copy()
        current_data['filtered_df'] = df.copy()
        current_data['column_types'] = col_types
        current_data['dept_map'] = dept_map
        current_data['filename'] = file.filename
        current_data['original_columns'] = original_columns

        result = build_analytics(
            df=df,
            current_data=current_data,
            column_types=col_types,
            dept_map=dept_map,
            original_columns=original_columns,
            is_non_answer=is_non_answer
        )
        return jsonify(sanitize_for_json(result))

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/filter', methods=['POST'])
def handle_filter():
    if current_data['original_df'] is None:
        return jsonify({'error': 'No data uploaded yet'}), 400

    filters = request.json.get('filters', {})
    search = request.json.get('search', '').lower()

    df = current_data['original_df'].copy()

    # Global Text Search
    if search:
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask |= df[col].astype(str).str.lower().str.contains(search, na=False)
        df = df[mask]

    # Specific Column Filters
    for col, value in filters.items():
        if not value or col not in df.columns:
            continue

        ctype = current_data['column_types'].get(col, 'text')

        if ctype == 'categorical':
            df = df[df[col].astype(str).str.strip() == value]
        elif ctype == 'text':
            df = df[df[col].astype(str).str.lower().str.contains(value.lower(), na=False)]
        elif ctype == 'date' and isinstance(value, list) and len(value) == 2:
            start_date, end_date = value
            dates = df[col].astype(str).apply(parse_date_safe)
            mask = pd.Series(True, index=df.index)
            if start_date:
                mask &= (dates >= pd.to_datetime(start_date))
            if end_date:
                mask &= (dates <= pd.to_datetime(end_date))
            df = df[mask]
        elif ctype == 'numeric':
            nums = pd.to_numeric(df[col], errors='coerce')
            val = str(value).strip()
            if val.startswith('>='):
                df = df[nums >= float(val[2:])]
            elif val.startswith('<='):
                df = df[nums <= float(val[2:])]
            elif val.startswith('>'):
                df = df[nums > float(val[1:])]
            elif val.startswith('<'):
                df = df[nums < float(val[1:])]
            elif val.startswith('='):
                df = df[nums == float(val[1:])]
            elif '-' in val:
                parts = val.split('-')
                if len(parts) == 2:
                    try:
                        low, high = float(parts[0]), float(parts[1])
                        df = df[(nums >= low) & (nums <= high)]
                    except:
                        pass
            else:
                try:
                    exact = float(val)
                    df = df[nums == exact]
                except:
                    pass

    current_data['filtered_df'] = df

    result = build_analytics(
        df=df,
        current_data=current_data,
        column_types=current_data['column_types'],
        dept_map=current_data['dept_map'],
        original_columns=current_data['original_columns'],
        is_non_answer=is_non_answer
    )
    return jsonify(sanitize_for_json(result))
