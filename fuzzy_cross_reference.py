import pandas as pd
from rapidfuzz import process, utils

# Load data
full_df = pd.read_csv('data/uploads/Student Feedback Form-Alumni Connect (Responses) - Form Responses 1.csv')
trimmed_df = pd.read_csv('data/uploads/Student_Feedback_Trimmed.csv')

# Standardize column names
full_df.columns = [c.strip() for c in full_df.columns]
trimmed_df.columns = [c.strip() for c in trimmed_df.columns]

roll_col = 'Roll No.'
name_col = 'Name of Student'
dept_col = 'Department'

# Prepare reference data (rows that HAVE a roll number)
reference_data = full_df[full_df[roll_col].notna()].copy()

# Create a combined "Identity" string for fuzzy matching: "Name | Department"
def normalize_identity(name, dept):
    # Normalize: lowercase, strip, remove extra internal spaces
    n = " ".join(str(name).lower().split())
    d = " ".join(str(dept).lower().split())
    return f"{n} | {d}"

reference_data['identity'] = reference_data.apply(lambda x: normalize_identity(x[name_col], x[dept_col]), axis=1)
ref_identities = reference_data['identity'].tolist()

# Identify rows in trimmed data where Roll No is missing
missing_mask = trimmed_df[roll_col].isna()
students_with_missing_roll = trimmed_df[missing_mask].copy()

found_count = 0
found_details = []

print("Searching for matches using Fuzzy Logic (Similarity > 90%)...")

for idx, row in students_with_missing_roll.iterrows():
    target_identity = normalize_identity(row[name_col], row[dept_col])
    
    # Use fuzzy matching to find the best match in our reference data
    # score_cutoff=90 ensures we only take high-confidence matches
    match = process.extractOne(target_identity, ref_identities, score_cutoff=90)
    
    if match:
        best_match_str, score, match_idx = match
        found_roll = reference_data.iloc[match_idx][roll_col]
        found_count += 1
        found_details.append({
            'Original Name': row[name_col],
            'Matched With': reference_data.iloc[match_idx][name_col],
            'Score': round(score, 1),
            'Roll': found_roll
        })

print(f"\n--- Deep Analysis Results ---")
print(f"Total missing Roll Numbers in trimmed file: {len(students_with_missing_roll)}")
print(f"Roll Numbers recovered with Fuzzy Matching: {found_count}")

if found_count > 0:
    print("\nTop 5 Fuzzy Matches Found:")
    # Sort by score to show best matches
    for item in found_details[:10]:
        print(f" - '{item['Original Name']}' matched with '{item['Matched With']}' (Score: {item['Score']}) -> Roll: {item['Roll']}")
else:
    print("\nNo fuzzy matches were found.")
