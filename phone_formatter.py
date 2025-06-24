import pandas as pd
import re

def format_phone_number(phone_str):
    """
    Adjusts phone numbers to a standard format based on provided examples:
    - Input like "0049 8221 937 130 0" becomes "+4982219371300"
    - Input like "0043 1 503 72 440" becomes "+43150372440"
    Handles potential variations like existing '+' or local numbers (assuming German default for '0' prefix).
    """
    if pd.isna(phone_str):
        return None
    
    s = str(phone_str).strip()
    
    # Remove all common separators: spaces, hyphens, slashes, parentheses
    # This makes subsequent checks easier.
    s_cleaned = re.sub(r'[\s\-\/\(\)]+', '', s)
    
    if s_cleaned.startswith('00'):
        # Example: "004912345" -> "+4912345"
        # Example: "004312345" -> "+4312345"
        return '+' + s_cleaned[2:]
    elif s_cleaned.startswith('+'):
        # Already has a '+', assume it's mostly correct or already formatted.
        # Example: "+4912345" -> "+4912345"
        return s_cleaned
    elif re.match(r'^(49|43)\d+$', s_cleaned): # Known country codes from examples (49, 43)
        # Example: "4912345" -> "+4912345" (if it started without '00' or '+')
        return '+' + s_cleaned
    elif s_cleaned.startswith('0') and not s_cleaned.startswith('00'):
        # Starts with a single '0', not '00'. Assume local German number.
        # Example: "01712345" -> "+491712345"
        # This rule might need adjustment if '0' prefixed numbers can be non-German.
        return '+49' + s_cleaned[1:]
    else:
        # Does not match the primary patterns.
        # Could be an international number from a different country not starting with '00'
        # or an already correctly formatted number without common prefixes.
        # Or it could be a malformed number.
        # Returning the original string (as passed to function) is a safe fallback.
        # Alternatively, return s_cleaned or log an issue.
        # print(f"Warning: Number '{str(phone_str)}' (cleaned: '{s_cleaned}') did not match expected patterns. Returning original.")
        return str(phone_str) # Fallback to the original input string

def process_excel(input_file_path, output_file_path, phone_column_name):
    """
    Reads an Excel file, formats phone numbers in a specified column,
    and saves the result to a new Excel file.
    """
    df = None  # Initialize df
    try:
        # Ensure the sheet is loaded first, then check columns.
        # dtype is applied if the column exists.
        df = pd.read_excel(input_file_path)
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}")
        return
    except Exception as e: # Catch other potential read errors (e.g. bad file format)
        print(f"Error reading Excel file {input_file_path}: {e}")
        return

    if phone_column_name not in df.columns:
        print(f"Error: Column '{phone_column_name}' not found in the Excel file '{input_file_path}'.")
        print(f"Available columns are: {df.columns.tolist()}")
        return
    
    # Now that we know the column exists, we can safely try to read with specific dtype
    # or convert it. For simplicity, convert after load.
    try:
        df[phone_column_name] = df[phone_column_name].astype(str)
    except Exception as e:
        print(f"Error converting column '{phone_column_name}' to string: {e}")
        return

    # Apply the formatting function
    # Create a new column for formatted numbers to compare, or overwrite existing one
    # df['formatted_phone'] = df[phone_column_name].apply(format_phone_number)
    
    # To overwrite the existing column:
    df[phone_column_name] = df[phone_column_name].apply(format_phone_number)
    
    try:
        df.to_excel(output_file_path, index=False)
        print(f"Processing complete. Output saved to {output_file_path}")
    except Exception as e:
        print(f"Error writing Excel file {output_file_path}: {e}")

if __name__ == "__main__":
    # --- Configuration ---
    # !!! IMPORTANT: Update these values !!!
    INPUT_FILE = 'data/A-Liste_001_AS120_ddc_20250530.xlsx'
    OUTPUT_FILE = 'data/A-Liste_001_AS120_ddc_20250530_formatted.xlsx'
    PHONE_COLUMN = 'Number'  # Updated based on user input
    # --- End Configuration ---

    print(f"Starting phone number formatting for {INPUT_FILE}...")
    print(f"Phone numbers will be read from column: '{PHONE_COLUMN}'")
    print(f"Formatted output will be saved to: {OUTPUT_FILE}")
    print("Please ensure the PHONE_COLUMN name is correct in the script.")
    
    process_excel(INPUT_FILE, OUTPUT_FILE, PHONE_COLUMN)

