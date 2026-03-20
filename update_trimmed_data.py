import pandas as pd
from rapidfuzz import process

# Load data
full_df = pd.read_csv('data/uploads/Student Feedback Form-Alumni Connect (Responses) - Form Responses 1.csv')
trimmed_df = pd.read_csv('data/uploads/Student_Feedback_Trimmed.csv')

# Standardize column names
full_df.columns = [c.strip() for c in full_df.columns]
trimmed_df.columns = [c.strip() for c in trimmed_df.columns]

roll_col = 'Roll No.'
name_col = 'Name of Student'
dept_col = 'Department'

# Prepare reference data
reference_data = full_df[full_df[roll_col].notna()].copy()
def normalize_identity(name, dept):
    n = " ".join(str(name).lower().split())
    d = " ".join(str(dept).lower().split())
    return f"{n} | {d}"

reference_data['identity'] = reference_data.apply(lambda x: normalize_identity(x[name_col], x[dept_col]), axis=1)
ref_identities = reference_data['identity'].tolist()

# 1. Fill the 46 recovered roll numbers
recovered_count = 0
for idx, row in trimmed_df[trimmed_df[roll_col].isna()].iterrows():
    target_identity = normalize_identity(row[name_col], row[dept_col])
    match = process.extractOne(target_identity, ref_identities, score_cutoff=90)
    
    if match:
        _, _, match_idx = match
        trimmed_df.at[idx, roll_col] = reference_data.iloc[match_idx][roll_col]
        recovered_count += 1

# 2. Remove the rows where Roll No is still missing (the 55 rows)
final_df = trimmed_df[trimmed_df[roll_col].notna()].copy()

# Save back to the file
final_df.to_csv('data/uploads/Student_Feedback_Trimmed.csv', index=False)

print(f"Update Complete:")
print(f" - Recovered and filled: {recovered_count} roll numbers")
print(f" - Removed: {len(trimmed_df) - len(final_df)} rows with missing roll numbers")
print(f" - Final row count: {len(final_df)}")
