import pandas as pd

"""
This script is used to compare two Excel files to see how they will match up before a merge.
It is designed to be highly configurable. Simply update the variables in the 'Configuration'
section to specify the files and columns to compare.
"""

# --- Configuration ---
# File path for the first file (the target of the merge)
FILE_1_PATH = 'data/step1_sales_pitch_updated.xlsx'
# File path for the second file (the source of the new data)
FILE_2_PATH = 'data/add these numbers.xlsx'

# Column name for matching in the first file
FILE_1_MATCH_COLUMN = 'firma'
# Column name for matching in the second file
FILE_2_MATCH_COLUMN = 'Company Name'

# Columns to display from the first file for verification
FILE_1_DISPLAY_COLUMNS = ['firma', 'Telefonnummer']
# Columns to display from the second file for verification
FILE_2_DISPLAY_COLUMNS = ['Company Name', 'found_number']
# --- End of Configuration ---

def check_columns(df, columns, file_path):
    """Checks if the specified columns exist in the dataframe."""
    for col in columns:
        if col not in df.columns:
            print(f"Error: Column '{col}' not found in {file_path}.")
            print(f"Available columns are: {df.columns.tolist()}")
            return False
    return True

def main():
    """Main function to execute the comparison."""
    try:
        # Read the Excel files
        df1 = pd.read_excel(FILE_1_PATH)
        df2 = pd.read_excel(FILE_2_PATH)

        # Check if all specified columns exist
        if not check_columns(df1, FILE_1_DISPLAY_COLUMNS, FILE_1_PATH) or \
           not check_columns(df2, FILE_2_DISPLAY_COLUMNS, FILE_2_PATH):
            return

        # --- Display comparison ---
        print("--- Columns for matching ---")
        print(f"\nFrom: {FILE_1_PATH}")
        print(df1[FILE_1_DISPLAY_COLUMNS].head())

        print(f"\nFrom: {FILE_2_PATH}")
        print(df2[FILE_2_DISPLAY_COLUMNS].head())

        # Show which companies from the second file are present in the first file
        matching_companies = df2[df2[FILE_2_MATCH_COLUMN].isin(df1[FILE_1_MATCH_COLUMN])]
        print(f"\nFound {len(matching_companies)} matching companies to update.")
        if not matching_companies.empty:
            print("Example of matching companies and the data to be added:")
            print(matching_companies[FILE_2_DISPLAY_COLUMNS].head())

    except FileNotFoundError as e:
        print(f"Error: {e.filename} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()