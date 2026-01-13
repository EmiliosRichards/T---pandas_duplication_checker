import pandas as pd
import re
import os

def format_phone_number(phone_str):
    """
    Adjusts phone numbers to a standard international format.
    Handles various formats and cleans the input string.
    Also handles numbers read as floats (e.g., '49123456789.0') and scientific notation.
    Returns a standardized string (e.g., '+49...') or None if invalid.
    """
    if pd.isna(phone_str):
        return None
    
    s = str(phone_str).strip()

    # Handle scientific notation
    if 'E+' in s.upper() or 'E-' in s.upper():
        try:
            s = f"{int(float(s))}"
        except (ValueError, TypeError):
            pass  # If conversion fails, proceed with the original string

    # If the string ends with '.0', remove it.
    if s.endswith('.0'):
        s = s[:-2]
    
    # Remove all non-digit characters except for a leading '+'
    s_cleaned = re.sub(r'[^\d\+]', '', s)
    
    if s_cleaned.startswith('00'):
        s_cleaned = '+' + s_cleaned[2:]
    elif s_cleaned.startswith('0'):
        s_cleaned = '+49' + s_cleaned[1:]
    
    if not s_cleaned.startswith('+'):
        s_cleaned = '+' + s_cleaned
        
    # Basic validation
    if not s_cleaned.startswith('+') or len(s_cleaned) < 9:
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

def process_and_filter_excel(input_file_path, output_file_path, primary_phone_col, secondary_phone_col):
    """
    Reads an Excel file, filters rows based on phone numbers.
    If the primary phone number is not in the DACH region, it checks the secondary phone number.
    If the secondary number is in the DACH region, it replaces the primary number.
    """
    try:
        df = pd.read_excel(input_file_path)
        # Convert both phone columns to numeric to handle scientific notation, then to string
        for col in [primary_phone_col, secondary_phone_col]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64').astype(str).replace('<NA>', '')
            else:
                print(f"Warning: Column '{col}' not found in the Excel file.")
                return
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}")
        return
    except Exception as e:
        print(f"Error reading Excel file {input_file_path}: {e}")
        return

    # Format both phone columns
    df['formatted_primary'] = df[primary_phone_col].apply(format_phone_number)
    df['formatted_secondary'] = df[secondary_phone_col].apply(format_phone_number)

    # Identify rows to be initially removed
    rows_to_remove = df[~df['formatted_primary'].apply(lambda p: p is not None and is_desired_country(p))].copy()

    for index, row in rows_to_remove.iterrows():
        secondary_phone = row['formatted_secondary']
        if secondary_phone and is_desired_country(secondary_phone):
            # If the secondary phone is valid, update the primary phone number in the original dataframe
            df.at[index, primary_phone_col] = secondary_phone
            # Re-format the primary phone number after update
            df.at[index, 'formatted_primary'] = secondary_phone

    # Re-evaluate the mask for rows to keep after potential updates
    mask_keep = df['formatted_primary'].apply(lambda p: p is not None and is_desired_country(p))
    
    # Update the original phone column with the formatted number for all kept rows
    df.loc[mask_keep, primary_phone_col] = df.loc[mask_keep, 'formatted_primary']

    # Select the DataFrames for kept and removed rows
    df_kept = df[mask_keep].drop(columns=['formatted_primary', 'formatted_secondary'])
    df_removed = df[~mask_keep].drop(columns=['formatted_primary', 'formatted_secondary'])

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
    INPUT_FILE = 'data/20250408_kevin_monday_morning.xlsx'
    OUTPUT_FILE = 'data/20250408_kevin_monday_morning_filtered.xlsx'
    PRIMARY_PHONE_COLUMN = 'Telefonnummer'
    SECONDARY_PHONE_COLUMN = '$phone'

    print(f"Starting phone number filtering for '{INPUT_FILE}'...")
    print(f"Primary phone column: '{PRIMARY_PHONE_COLUMN}'")
    print(f"Secondary phone column: '{SECONDARY_PHONE_COLUMN}'")
    print("If primary number is not in DACH region, will check secondary number.")
    print(f"Kept rows will be saved to: '{OUTPUT_FILE}'")
    print("Removed rows will be saved to a separate file with a '_removed' suffix.")

    process_and_filter_excel(INPUT_FILE, OUTPUT_FILE, PRIMARY_PHONE_COLUMN, SECONDARY_PHONE_COLUMN)