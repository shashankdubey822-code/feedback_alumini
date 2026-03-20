import pandas as pd

# Define paths
SOURCE_FILE = 'data/uploads/Student Feedback Form-Alumni Connect (Responses) - Form Responses 1.csv'
OUTPUT_FILE = 'data/uploads/Student_Feedback_Trimmed.csv'

def trim_csv():
    try:
        # Load the data
        df = pd.read_csv(SOURCE_FILE)
        
        # Keep only the first 364 rows, then drop the 364th (index 363)
        trimmed_df = df.iloc[:364].drop(df.index[363])
        
        # Save to a new file
        trimmed_df.to_csv(OUTPUT_FILE, index=False)
        
        print(f"Success!")
        print(f"Original rows: {len(df)}")
        print(f"New file rows: {len(trimmed_df)}")
        print(f"Trimmed file saved as: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    trim_csv()
