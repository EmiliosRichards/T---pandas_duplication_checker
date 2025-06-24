import pandas as pd
import os
from datetime import datetime
from openpyxl.utils import get_column_letter

# --- Configuration ---
INPUT_FILE_PATH = r"data\Anna_sent\Kunden wie Medwing 02.06.25.xlsx"  # IMPORTANT: Change this to your input file path
DEDUPLICATION_COLUMN = "Company Name"  # Column to use for identifying duplicates
OUTPUT_DIR = "single_output"
LOG_DIR = "single_logs"

# --- Timestamp for output files ---
# TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S") # No longer primary for main output name

# --- Ensure output and log directories exist ---
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# --- Output file paths (will be defined in main based on input file) ---
# CLEANED_OUTPUT_PATH = os.path.join(OUTPUT_DIR, f"cleaned_data_{TIMESTAMP}.xlsx")
# REMOVED_LOG_PATH = os.path.join(LOG_DIR, f"removed_duplicates_{TIMESTAMP}.xlsx")

def format_excel_sheet(writer, df, sheet_name="Sheet1"):
    """Applies formatting to the Excel sheet."""
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]

    # 1. Format 'Number' column as text, if it exists
    if "Number" in df.columns:
        try:
            number_col_idx = df.columns.get_loc("Number")
            number_col_letter = get_column_letter(number_col_idx + 1)  # openpyxl columns are 1-based

            for row_idx in range(2, len(df) + 2):  # Skip header, Excel rows are 1-based
                cell = worksheet[f"{number_col_letter}{row_idx}"]
                cell.number_format = "@"
        except KeyError:
            print(f"Warning: Column 'Number' not found for text formatting.")
        except Exception as e:
            print(f"Error formatting 'Number' column: {e}")


    # 2. Auto-adjust column widths
    for col_idx, column_name in enumerate(df.columns, 1):
        column_letter = get_column_letter(col_idx)
        max_length = 0
        
        # Check column header length
        if column_name is not None:
            max_length = max(max_length, len(str(column_name)))

        # Check cell content length
        # Iterate through the column cells in the worksheet
        # worksheet.columns is an iterator of tuples of cells for each column
        # We need to access the correct column by its letter or index
        # For simplicity, we iterate through DataFrame column values
        if not df[column_name].empty:
             max_length = max(
                max_length,
                df[column_name].astype(str).map(len).max()
            )
        
        adjusted_width = max_length + 2  # Adding a little padding
        worksheet.column_dimensions[column_letter].width = adjusted_width

def main():
    print(f"Starting deduplication process for: {INPUT_FILE_PATH}")

    # --- Load the Excel file ---
    try:
        df_original = pd.read_excel(INPUT_FILE_PATH, dtype=str)
        print(f"Successfully loaded {INPUT_FILE_PATH}. Original rows: {len(df_original)}")
    except FileNotFoundError:
        print(f"Error: Input file not found at {INPUT_FILE_PATH}")
        print("Please ensure the INPUT_FILE_PATH variable is set correctly.")
        return
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return

    if DEDUPLICATION_COLUMN not in df_original.columns:
        print(f"Error: Deduplication column '{DEDUPLICATION_COLUMN}' not found in the input file.")
        print(f"Available columns are: {df_original.columns.tolist()}")
        return

    # --- Define output file paths based on input file name ---
    base_name, ext = os.path.splitext(os.path.basename(INPUT_FILE_PATH))
    
    cleaned_file_name = f"{base_name}_deduped{ext}"
    CLEANED_OUTPUT_PATH = os.path.join(OUTPUT_DIR, cleaned_file_name)
    
    removed_log_file_name = f"{base_name}_deduped_removed_log{ext}"
    REMOVED_LOG_PATH = os.path.join(LOG_DIR, removed_log_file_name)

    # --- Identify and separate duplicates ---
    # Keep the first occurrence, mark others as duplicates
    duplicates_mask = df_original.duplicated(subset=[DEDUPLICATION_COLUMN], keep='first')
    
    df_cleaned = df_original[~duplicates_mask]
    df_removed = df_original[duplicates_mask]

    print(f"Deduplication based on column: '{DEDUPLICATION_COLUMN}'")
    print(f"Number of rows removed as duplicates: {len(df_removed)}")
    print(f"Number of rows remaining after deduplication: {len(df_cleaned)}")

    # --- Save the cleaned data ---
    try:
        with pd.ExcelWriter(CLEANED_OUTPUT_PATH, engine="openpyxl") as writer:
            df_cleaned.to_excel(writer, index=False, sheet_name="Sheet1")
            format_excel_sheet(writer, df_cleaned, sheet_name="Sheet1")
        print(f"✅ Cleaned data saved to: {CLEANED_OUTPUT_PATH}")
    except Exception as e:
        print(f"Error saving cleaned data: {e}")

    # --- Save the removed duplicates (log) ---
    if not df_removed.empty:
        try:
            with pd.ExcelWriter(REMOVED_LOG_PATH, engine="openpyxl") as writer:
                df_removed.to_excel(writer, index=False, sheet_name="RemovedDuplicates")
                format_excel_sheet(writer, df_removed, sheet_name="RemovedDuplicates")
            print(f"ℹ️ Removed duplicates logged to: {REMOVED_LOG_PATH}")
        except Exception as e:
            print(f"Error saving removed duplicates log: {e}")
    else:
        print("ℹ️ No duplicates found to log.")

    print("\n--- Summary ---")
    print(f"Original rows: {len(df_original)}")
    print(f"Rows removed: {len(df_removed)}")
    print(f"Final cleaned rows: {len(df_cleaned)}")
    print("--- Process Complete ---")

if __name__ == "__main__":
    main()