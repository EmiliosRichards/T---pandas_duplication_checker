import pandas as pd
import re

def format_phone_number(phone_str):
    """
    Adjusts phone numbers to a standard format based on provided examples:
    - Input like "0049 8221 937 130 0" becomes "+4982219371300"
    - Input like "0043 1 503 72 440" becomes "+43150372440"
    Handles potential variations like existing '+' or local numbers (assuming German default for '0' prefix).
    Also handles numbers read as floats (e.g., '49123456789.0').
    """
    if pd.isna(phone_str):
        return None
    
    s = str(phone_str).strip()

    # If the string ends with '.0', remove it. This handles cases where numbers were read as floats.
    if s.endswith('.0'):
        s = s[:-2]
    
    # Remove all common separators: spaces, hyphens, slashes, parentheses
    # This makes subsequent checks easier.
    s_cleaned = re.sub(r'[\s\-\/\(\)]+', '', s)
    
    if s_cleaned.startswith('00'):
        # Example: "004912345" -> "+4912345"
        return '+' + s_cleaned[2:]
    elif s_cleaned.startswith('+'):
        # Already has a '+', assume it's mostly correct or already formatted.
        return s_cleaned
    elif re.match(r'^(49|43|41)\d+$', s_cleaned): # DE, AT, CH country codes
        # Example: "4912345" -> "+4912345"
        return '+' + s_cleaned
    elif s_cleaned.startswith('0') and not s_cleaned.startswith('00'):
        # Starts with a single '0', assume local German number.
        return '+49' + s_cleaned[1:]
    else:
        # If it's a long number without a prefix, assume it's a direct number and add '+'
        if re.match(r'^\d{11,}$', s_cleaned):
            return '+' + s_cleaned
        # Fallback for numbers that don't match expected patterns
        return str(phone_str)

def process_excel(input_file_path, output_file_path, phone_column_name):
    """
    Reads an Excel file, formats phone numbers in a specified column,
    and saves the result to a new Excel file.
    """
    df = None
    try:
        # Read the Excel file, ensuring the phone number column is treated as a string
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
    
    # Apply the formatting function to the specified column
    df[phone_column_name] = df[phone_column_name].apply(format_phone_number)
    
    try:
        df.to_excel(output_file_path, index=False)
        print(f"Processing complete. Output saved to {output_file_path}")
    except Exception as e:
        print(f"Error writing Excel file {output_file_path}: {e}")

if __name__ == "__main__":
    # --- Configuration ---
    # !!! IMPORTANT: Update these values !!!
    INPUT_FILE = 'data/manuav_002_ER5K_spg_apol_20250703_filtered.xlsx'
    OUTPUT_FILE = 'data/manuav_002_ER5K_spg_apol_20250703_formatted.xlsx'
    PHONE_COLUMN = 'Number'  # Updated based on user input
    # --- End Configuration ---

    print(f"Starting phone number formatting for {INPUT_FILE}...")
    print(f"Phone numbers will be read from column: '{PHONE_COLUMN}'")
    print(f"Formatted output will be saved to: {OUTPUT_FILE}")
    print("Please ensure the PHONE_COLUMN name is correct in the script.")
    
    process_excel(INPUT_FILE, OUTPUT_FILE, PHONE_COLUMN)

