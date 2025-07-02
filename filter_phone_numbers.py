import pandas as pd
import re
import os

def format_phone_number(phone_str):
    """
    Adjusts phone numbers to a standard international format.
    Handles various formats like '0049...', '+49...', '01...', and numbers with spaces.
    Returns a standardized string (e.g., '+49...') or None if invalid.
    """
    if pd.isna(phone_str):
        return None
    
    s = str(phone_str).strip()
    
    # Remove all non-digit characters except for a leading '+'
    s_cleaned = re.sub(r'[^\d\+]', '', s)
    
    # Further cleaning for specific common patterns like leading '00'
    if s_cleaned.startswith('00'):
        # Replace '00' with '+'
        s_cleaned = '+' + s_cleaned[2:]
    elif s_cleaned.startswith('0'):
        # Assume it's a local German number and replace leading '0' with '+49'
        s_cleaned = '+49' + s_cleaned[1:]

    # If after cleaning, it doesn't start with a '+', it might be a direct country code
    # e.g. 491234567. Add '+' to it.
    if not s_cleaned.startswith('+'):
        s_cleaned = '+' + s_cleaned

    # Basic validation: must start with '+' and have a reasonable length
    if not s_cleaned.startswith('+') or len(s_cleaned) < 9: # e.g. +49123456
        return None

    return s_cleaned

def is_desired_country(phone_number_str):
    """
    Checks if the formatted phone number belongs to Germany (+49), Switzerland (+41), or Austria (+43).
    Assumes phone_number_str is already formatted (e.g., starts with '+').
    """
    if not phone_number_str or not phone_number_str.startswith('+'):
        return False
    
    return (phone_number_str.startswith('+49') or \
            phone_number_str.startswith('+41') or \
            phone_number_str.startswith('+43'))

def process_and_filter_excel(input_file_path, output_file_path, phone_column_name):
    """
    Reads an Excel file, filters rows based on phone numbers in the specified column,
    and saves the result to a new Excel file.
    Rows are kept if the phone number is from Germany, Switzerland, or Austria.
    Rows with invalid numbers or numbers from other countries are removed and
    saved to a separate file with a '_removed' suffix.
    """
    try:
        df = pd.read_excel(input_file_path, dtype={phone_column_name: str})
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}")
        return
    except Exception as e:
        print(f"Error reading Excel file {input_file_path}: {e}")
        return

    if phone_column_name not in df.columns:
        print(f"Error: Column '{phone_column_name}' not found in the Excel file '{input_file_path}'.")
        print(f"Available columns are: {df.columns.tolist()}")
        return

    # Create lists to store indices of rows to keep and remove
    rows_to_keep_indices = []
    rows_to_remove_indices = []

    for index, row in df.iterrows():
        phone_val = row[phone_column_name]
        formatted_phone = format_phone_number(phone_val)

        if formatted_phone and is_desired_country(formatted_phone):
            rows_to_keep_indices.append(index)
        else:
            rows_to_remove_indices.append(index)
    
    df_kept = df.loc[rows_to_keep_indices]
    df_removed = df.loc[rows_to_remove_indices]

    def save_df_to_excel(dataframe, file_path):
        """Helper function to save a DataFrame to an Excel file with auto-adjusted columns."""
        try:
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")

            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                dataframe.to_excel(writer, index=False, sheet_name='Sheet1')
                worksheet = writer.sheets['Sheet1']
                for i, col in enumerate(dataframe.columns):
                    max_len = dataframe[col].astype(str).map(len).max()
                    max_len = max(max_len, len(col)) + 2
                    worksheet.set_column(i, i, max_len)
            
            print(f"Successfully saved {len(dataframe)} rows to {file_path}")
        except Exception as e:
            print(f"Error writing Excel file {file_path}: {e}")

    # Save the kept and removed rows to separate files
    save_df_to_excel(df_kept, output_file_path)
    
    base, ext = os.path.splitext(output_file_path)
    removed_output_path = f"{base}_removed{ext}"
    save_df_to_excel(df_removed, removed_output_path)

    print("\n--- Summary ---")
    print(f"Original rows: {len(df)}")
    print(f"Kept rows: {len(df_kept)} (saved to {output_file_path})")
    print(f"Removed rows: {len(df_removed)} (saved to {removed_output_path})")

if __name__ == "__main__":
    INPUT_FILE = 'data/manuav_001_ER4K_spg_apol_20250702.xlsx'
    OUTPUT_FILE = 'data/manuav_001_ER4K_spg_apol_20250702_filtered_D_A_CH.xlsx'
    PHONE_COLUMN = 'Number'

    print(f"Starting phone number filtering for '{INPUT_FILE}'...")
    print(f"Reading from column: '{PHONE_COLUMN}'")
    print(f"Keeping only German (+49), Swiss (+41), and Austrian (+43) numbers.")
    print(f"Rows with invalid or other country numbers will be removed.")
    print(f"Kept rows will be saved to: '{OUTPUT_FILE}'")
    print("Removed rows will be saved to a separate file with a '_removed' suffix.")
    
    process_and_filter_excel(INPUT_FILE, OUTPUT_FILE, PHONE_COLUMN)