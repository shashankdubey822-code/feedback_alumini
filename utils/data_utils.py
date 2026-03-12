from rapidfuzz import fuzz
from collections import Counter
import pandas as pd
import numpy as np

def fuzzy_normalize(values, threshold=65):
    """Group similar categorical strings using Levenshtein distance."""
    clean = [v.strip() for v in values if v and v.strip() and
             v.strip() not in ('', 'NA', 'N/A', '-', '.')]
    if not clean:
        return {}

    freq = Counter(clean)
    sorted_vals = sorted(freq.keys(), key=lambda x: (-freq[x], x))
    mapping = {}
    canonical_groups = []

    for val in sorted_vals:
        if val in mapping:
            continue
        matched = False
        for canonical, members in canonical_groups:
            score = fuzz.token_sort_ratio(val.lower(), canonical.lower())
            if score >= threshold:
                mapping[val] = canonical
                members.append(val)
                matched = True
                break
        if not matched:
            mapping[val] = val
            canonical_groups.append((val, [val]))

    final_mapping = {}
    for canonical, members in canonical_groups:
        best = max(members, key=lambda m: (freq.get(m, 0), len(m)))
        for m in members:
            final_mapping[m] = best

    return final_mapping


def parse_date_safe(val):
    """Safely parse strings to pandas datetime."""
    if not isinstance(val, str) or not val.strip():
        return pd.NaT
    val = str(val).split()[0]
    return pd.to_datetime(val, errors='coerce')


def sanitize_for_json(obj):
    """Recursively convert numpy types to Python native for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        if np.isnan(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return [sanitize_for_json(v) for v in obj.tolist()]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj
