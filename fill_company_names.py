import pandas as pd
import tldextract
import os

# --- Configuration ---
INPUT_FILE_PATH = 'filter_output/unknown_001_KF8K_rbt_apol_20250530_filtered.xlsx'
COMPANY_COLUMN = 'Company Name'
URL_COLUMN = 'URL'
# Set to True to overwrite the input file, False to save to a new file specified by OUTPUT_FILE_PATH
OVERWRITE_FILE = True
# This path is used if OVERWRITE_FILE is False
OUTPUT_FILE_PATH = 'filter_output/unknown_001_KF8K_rbt_apol_20250530_companies_filled.xlsx'
# --- End Configuration ---

def get_base_domain(url_str):
    """
    Extracts the base domain from a URL string.
    e.g., 'https://www.example.co.uk/path' -> 'example'
    Returns None if the URL is invalid or the domain cannot be extracted.
    """
    if pd.isna(url_str) or not isinstance(url_str, str) or not url_str.strip():
        return None
    try:
        # Add http scheme if missing, tldextract works better with it
        if not url_str.startswith(('http://', 'https://')):
            url_str = 'http://' + url_str
        ext = tldextract.extract(url_str)
        return ext.domain if ext.domain else None
    except Exception: # Catch any error during extraction
        return None

def process_company_names(input_path, company_col, url_col, overwrite, output_path_if_not_overwrite):
    """
    Processes an Excel file to fill empty company names using URLs.
    """
    try:
        # Read all columns as string to be safe, especially URL and Company Name
        df = pd.read_excel(input_path, dtype=str)
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_path}")
        return
    except Exception as e:
        print(f"Error reading Excel file {input_path}: {e}")
        return

    if company_col not in df.columns:
        print(f"Error: Company column '{company_col}' not found. Available: {df.columns.tolist()}")
        return
    if url_col not in df.columns:
        print(f"Error: URL column '{url_col}' not found. Available: {df.columns.tolist()}")
        return

    filled_count = 0
    for index, row in df.iterrows():
        # Explicitly convert cell value to string to handle various 'empty' representations
        company_name_str = str(row[company_col]).strip()
        
        # Check if the string is empty or represents a common NA value after conversion to string
        # Common string forms of NA: 'nan' (from np.nan), 'None' (from None object)
        # An empty string or string with only whitespace is also considered empty.
        if not company_name_str or company_name_str.lower() == 'nan' or company_name_str.lower() == 'none':
            url = row[url_col]
            base_domain = get_base_domain(url)
            if base_domain:
                df.at[index, company_col] = base_domain
                filled_count += 1
    
    print(f"Filled {filled_count} empty company names.")

    final_output_path = input_path if overwrite else output_path_if_not_overwrite
    
    try:
        output_dir = os.path.dirname(final_output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        with pd.ExcelWriter(final_output_path, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            workbook = writer.book
            worksheet = writer.sheets['Sheet1']
            for i, col_name in enumerate(df.columns):
                column_len = df[col_name].astype(str).map(len).max()
                column_len = max(column_len, len(col_name)) + 2 # Header length + padding
                worksheet.set_column(i, i, column_len)
        
        print(f"Processing complete. Output saved to {final_output_path}")
        if overwrite:
            print(f"Input file '{input_path}' was overwritten.")
    except Exception as e:
        print(f"Error writing Excel file {final_output_path}: {e}")

if __name__ == "__main__":
    print(f"Starting company name filling process for: {INPUT_FILE_PATH}")
    print(f"Company Name column: '{COMPANY_COLUMN}', URL column: '{URL_COLUMN}'")
    if OVERWRITE_FILE:
        print(f"Input file will be overwritten.")
    else:
        print(f"Output will be saved to a new file: {OUTPUT_FILE_PATH}")
    
    # Check if tldextract is available
    try:
        import tldextract
    except ImportError:
        print("Error: The 'tldextract' library is not installed. Please install it by running: pip install tldextract")
        exit()

    process_company_names(INPUT_FILE_PATH, COMPANY_COLUMN, URL_COLUMN, OVERWRITE_FILE, OUTPUT_FILE_PATH)