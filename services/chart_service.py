import math
from utils.nlp_utils import is_department_like

def classify_axis_labels(col_name, ctype, chart_purpose='distribution'):
    """Assign smart X and Y axis labels based on column type and name."""
    col_str = str(col_name)

    if chart_purpose == 'distribution':
        if is_department_like(col_str, None):
            return ('Department Name', 'Number of Responses')
        elif 'speaker' in col_str.lower() or 'alumni' in col_str.lower():
            return ('Speaker Name', 'Response Count')

        x_label = col_str[:30] + '...' if len(col_str) > 30 else col_str

        if ctype == 'numeric':
            return (f'{x_label} (Rating)', 'Frequency')
        elif ctype == 'categorical':
            return (f'{x_label} (Category)', 'Number of Responses')
        else:
            return (x_label, 'Count')

    return ('Category', 'Value')

def build_chart_data(df, column_types, dept_map, columns):
    charts = []

    for col in columns:
        ctype = column_types.get(col, 'text')

        # Use normalized copy if department mapping exists
        use_col = col + ' (Normalized)' if col in dept_map else col

        if use_col not in df.columns:
            continue

        values = df[use_col].astype(str).str.strip()
        values = values[values.ne('') & values.ne('NA') & values.ne('N/A')
                        & values.ne('-') & values.ne('.') & values.ne('na')]

        if len(values) == 0:
            continue

        if ctype == 'categorical':
            freq = values.value_counts().head(10)
            if len(freq) >= 2:
                # Decide chart type
                unique = values.nunique()
                total = len(values)
                chart_type = 'pie'
                if unique > 6:
                    chart_type = 'bar'
                elif unique > 3 and unique <= 6 and sorted(freq.values) != list(freq.values):
                    chart_type = 'doughnut'
                elif unique <= 3 and total > 50:
                    chart_type = 'doughnut'
                elif unique > 10:
                    chart_type = 'line'

                x_label, y_label = classify_axis_labels(col, ctype, 'distribution')

                # Horizontal bar for very long names
                horizontal_bar = False
                if chart_type == 'bar':
                    max_label_len = max(len(str(lbl)) for lbl in freq.index)
                    if max_label_len > 15:
                        horizontal_bar = True

                charts.append({
                    'title': f'{col[:40]} — Distribution',
                    'type': chart_type,
                    'column': col,
                    'columnType': 'categorical',
                    'labels': freq.index.tolist(),
                    'data': freq.values.tolist(),
                    'normalized': col in dept_map,
                    'xLabel': x_label,
                    'yLabel': y_label,
                    'horizontal': horizontal_bar,
                })

        elif ctype == 'numeric':
            nums = pd.to_numeric(values, errors='coerce').dropna()
            if len(nums) >= 5:
                # Binning numeric distributions
                min_val = nums.min()
                max_val = nums.max()
                rng = max_val - min_val
                
                # Smart binning
                bin_count = 5
                if rng <= 10 and all(nums.apply(lambda x: x.is_integer())):
                    bin_count = int(rng) + 1
                    all_int = True
                else:
                    all_int = False

                if bin_count == 0:
                    bin_count = 1
                elif bin_count > 10:
                    bin_count = 10

                bin_size = rng / bin_count if bin_count > 0 else 1
                if bin_size == 0:
                    bin_size = 1
                
                bins = [0] * bin_count
                bin_labels = []

                if all_int and rng <= 10:
                    bin_labels = [str(int(min_val + i)) for i in range(bin_count)]
                else:
                    for i in range(bin_count):
                        start = min_val + (i * bin_size)
                        end = min_val + ((i + 1) * bin_size)
                        label = f"{math.floor(start)}-{math.ceil(end)}" if bin_size >= 1 else f"{start:.1f}-{end:.1f}"
                        if i == bin_count - 1:
                            label = f">={math.floor(start)}" if bin_size >= 1 else f">={start:.1f}"
                        bin_labels.append(label)

                for val in nums:
                    idx = int((val - min_val) / bin_size) if bin_size > 0 else 0
                    if idx >= bin_count:
                        idx = bin_count - 1
                    bins[idx] += 1

                bins_data = [int(b) for b in bins]
                x_label, y_label = classify_axis_labels(col, ctype, 'distribution')

                # For numeric bins, also store bin boundaries for exact click filtering
                if all_int and rng <= 10:
                    bin_boundaries = [{'exact': i} for i in range(int(min_val), int(max_val) + 1)]
                else:
                    bin_boundaries = [
                        {'min': min_val + i * bin_size, 'max': min_val + (i + 1) * bin_size, 'isLast': i == bin_count - 1}
                        for i in range(bin_count)
                    ]

                charts.append({
                    'title': f'{col[:40]} — Distribution',
                    'type': 'bar',
                    'column': col,
                    'columnType': 'numeric',
                    'binBoundaries': bin_boundaries,
                    'labels': bin_labels,
                    'data': bins_data,
                    'normalized': False,
                    'xLabel': x_label,
                    'yLabel': y_label,
                })

    return charts
