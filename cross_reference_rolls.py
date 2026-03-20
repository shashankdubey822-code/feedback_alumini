import pandas as pd

# Load both the trimmed and full datasets
full_df = pd.read_csv('data/uploads/Student Feedback Form-Alumni Connect (Responses) - Form Responses 1.csv')
trimmed_df = pd.read_csv('data/uploads/Student_Feedback_Trimmed.csv')

# Standardize column names
full_df.columns = [c.strip() for c in full_df.columns]
trimmed_df.columns = [c.strip() for c in trimmed_df.columns]

roll_col = 'Roll No.'
name_col = 'Name of Student'
dept_col = 'Department'

# 1. Identify rows in trimmed data where Roll No is missing
missing_mask = trimmed_df[roll_col].isna()
students_with_missing_roll = trimmed_df[missing_mask].copy()

# 2. Create a reference mapping from the FULL dataset where Roll No IS present
# We normalize names and depts for better matching
full_df['name_lower'] = full_df[name_col].astype(str).str.strip().str.lower()
full_df['dept_lower'] = full_df[dept_col].astype(str).str.strip().str.lower()

# Filter full_df for rows that HAVE a roll number
reference_data = full_df[full_df[roll_col].notna()].copy()

# 3. Try to find the missing roll numbers
found_count = 0
found_details = []

for idx, row in students_with_missing_roll.iterrows():
    s_name = str(row[name_col]).strip().lower()
    s_dept = str(row[dept_col]).strip().lower()
    
    # Search for this student in the reference data
    match = reference_data[(reference_data['name_lower'] == s_name) & 
                           (reference_data['dept_lower'] == s_dept)]
    
    if not match.empty:
        found_roll = match[roll_col].iloc[0]
        found_count += 1
        found_details.append({
            'Name': row[name_col],
            'Dept': row[dept_col],
            'Recovered Roll': found_roll
        })

print(f"--- Analysis Results ---")
print(f"Total missing Roll Numbers in trimmed file: {len(students_with_missing_roll)}")
print(f"Roll Numbers successfully recovered via cross-reference: {found_count}")

if found_count > 0:
    print("\nSample of recovered data:")
    for item in found_details[:5]:
        print(f" - {item['Name']} ({item['Dept']}): Found Roll No {item['Recovered Roll']}")
else:
    print("\nNo matching records with Roll Numbers were found for these students in the rest of the data.")
