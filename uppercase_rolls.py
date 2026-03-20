import pandas as pd

# Define path
FILE_PATH = 'data/uploads/Student_Feedback_Trimmed.csv'

def uppercase_rolls():
    try:
        # Load the data
        df = pd.read_csv(FILE_PATH)
        
        # Find the Roll No. column
        roll_col = [c for c in df.columns if 'Roll No.' in c][0]
        
        # Convert to uppercase
        # We also strip any accidental spaces during the process
        df[roll_col] = df[roll_col].astype(str).str.upper().str.strip()
        
        # Save back to the file
        df.to_csv(FILE_PATH, index=False)
        print(f"Success! All Roll Numbers in '{roll_col}' are now in UPPERCASE.")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    uppercase_rolls()
