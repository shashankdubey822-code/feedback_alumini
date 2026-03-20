import pandas as pd
import numpy as np

# Load the CSV
df = pd.read_csv('data/uploads/Student Feedback Form-Alumni Connect (Responses) - Form Responses 1.csv')

# Find the specific Roll No. column (it has a trailing space)
roll_col = [c for c in df.columns if 'Roll No.' in c][0]
roll_nos = df[roll_col]

total = len(df)
# NaN/NULL values (truly missing)
nan_count = roll_nos.isna().sum()

# Convert everything to string for character-based checking
as_str = roll_nos.astype(str).str.strip().str.lower()
empty_str = (as_str == '').sum()
# Subtract nan_count from empty_str since as_str (roll_nos.astype(str)) treats NaN as 'nan'
# Let's be more precise
real_nan = roll_nos.isna()
is_empty = (as_str == '') & (~real_nan)
is_placeholder = (as_str.isin(['.', '-', 'na', 'none'])) & (~real_nan)

print(f"Total Rows: {total}")
print(f"NULL/NaN values: {nan_count}")
print(f"Empty/Whitespace strings (not NaN): {is_empty.sum()}")
print(f"Placeholder values (., -, NA): {is_placeholder.sum()}")
print(f"Total Missing/Invalid: {nan_count + is_empty.sum() + is_placeholder.sum()}")
print(f"Percentage missing: {(nan_count + is_empty.sum() + is_placeholder.sum()) / total * 100:.2f}%")
