import pandas as pd
import re
import os

def format_phone_number(phone_str):
    """
    Adjusts phone numbers to a standard format.
    Returns None if the number is invalid or cannot be formatted.
    """
    if pd.isna(phone_str):
        return None
    
    s = str(phone_str).strip()
    
    # Remove all common separators: spaces, hyphens, slashes, parentheses
    s_cleaned = re.sub(r'[\s\-\/\(\)]+', '', s)

    # Check for obviously non-numeric or too short strings after cleaning
    if not s_cleaned or not re.match(r'^\+?\d+$', s_cleaned.replace('00', '+', 1)): # Allow leading '00' to become '+'
        if not re.match(r'^\d+$', s_cleaned): # If not purely digits (after initial check)
             return None # Likely not a number if it contains non-digits after cleaning and not starting with +
    
    # Min length check (e.g., country code + few digits)
    # A very short number like "+491" is unlikely to be valid.
    # This is a basic check; more sophisticated validation could be added.
    if len(s_cleaned.replace('00', '', 1).replace('+', '', 1)) < 7: # Arbitrary minimum length for number part
        return None

    if s_cleaned.startswith('00'):
        # Example: "004912345" -> "+4912345"
        return '+' + s_cleaned[2:]
    elif s_cleaned.startswith('+'):
        # Example: "+4912345" -> "+4912345"
        return s_cleaned
    elif re.match(r'^(49|43|41)\d+$', s_cleaned): # Known desired country codes without prefix
        return '+' + s_cleaned
    elif s_cleaned.startswith('0') and not s_cleaned.startswith('00'):
        # Assume local German number if it starts with '0' and is not '00'
        # This is a common convention but might need adjustment for other local formats.
        # For this task, we are primarily interested in +49, +41, +43 after this stage.
        return '+49' + s_cleaned[1:] # Default to German for '0' prefix
    else:
        # If it doesn't match common international prefixes or local German '0' start,
        # and it's not already starting with '+', it's hard to determine the country code reliably
        # or it might be a malformed number.
        return None # Treat as unformattable/invalid for filtering purposes

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
    Rows are kept if the phone number is valid and from Germany, Switzerland, or Austria.
    Rows with invalid/empty numbers or numbers from other countries are removed.
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

    # Create a list to store indices of rows to keep
    rows_to_keep_indices = []

    for index, row in df.iterrows():
        phone_val = row[phone_column_name]
        formatted_phone = format_phone_number(phone_val)

        if formatted_phone and is_desired_country(formatted_phone):
            rows_to_keep_indices.append(index)
    
    df_filtered = df.loc[rows_to_keep_indices]

    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        # Use XlsxWriter to auto-adjust column widths
        with pd.ExcelWriter(output_file_path, engine='xlsxwriter') as writer:
            df_filtered.to_excel(writer, index=False, sheet_name='Sheet1')
            workbook = writer.book
            worksheet = writer.sheets['Sheet1']
            for i, col in enumerate(df_filtered.columns):
                # find length of column i
                column_len = df_filtered[col].astype(str).str.len().max()
                # Setting the length of the column header
                column_len = max(column_len, len(col)) + 2 # Add a little padding
                worksheet.set_column(i, i, column_len)

        print(f"Processing complete. Filtered data saved to {output_file_path}")
        print(f"Original rows: {len(df)}, Filtered rows: {len(df_filtered)}")
    except Exception as e:
        print(f"Error writing Excel file {output_file_path}: {e}")

if __name__ == "__main__":
    INPUT_FILE = 'data/unknown_001_KF8K_rbt_apol_20250530.xlsx'
    OUTPUT_FILE = 'filter_output/unknown_001_KF8K_rbt_apol_20250530_filtered.xlsx'
    PHONE_COLUMN = 'Number'

    print(f"Starting phone number filtering for '{INPUT_FILE}'...")
    print(f"Reading from column: '{PHONE_COLUMN}'")
    print(f"Filtering for German (+49), Swiss (+41), Austrian (+43) numbers.")
    print(f"Rows with invalid numbers or numbers from other countries will be removed.")
    print(f"Output will be saved to: '{OUTPUT_FILE}'")
    
    process_and_filter_excel(INPUT_FILE, OUTPUT_FILE, PHONE_COLUMN)