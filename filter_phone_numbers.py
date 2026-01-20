import pandas as pd
import re
import os
from typing import Optional, Tuple
import argparse

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

def _sniff_csv_separator(input_file_path: str, default: str = ';') -> str:
    """
    Best-effort delimiter detection (prefers ';' for EU-style CSVs).
    """
    try:
        with open(input_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            header = f.readline()
        if header.count(';') >= header.count(',') and header.count(';') > 0:
            return ';'
        if header.count(',') > 0:
            return ','
    except Exception:
        pass
    return default

def _load_dataframe(input_file_path: str) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Loads CSV or Excel into a DataFrame.

    Returns:
      (df, csv_sep) where csv_sep is only set for CSV inputs.
    """
    _, ext = os.path.splitext(input_file_path)
    ext = ext.lower()

    if ext in (".xlsx", ".xls", ".xlsm"):
        # dtype=str helps prevent scientific-notation / float parsing of phone numbers
        return pd.read_excel(input_file_path, dtype=str), None

    if ext in (".csv", ".txt"):
        sep = _sniff_csv_separator(input_file_path)
        return pd.read_csv(input_file_path, sep=sep, dtype=str, encoding="utf-8-sig"), sep

    raise ValueError(f"Unsupported input file type: '{ext}'. Use .csv or Excel (.xlsx/.xls/.xlsm).")

def _ensure_output_ext_matches_input(input_file_path: str, output_file_path: str) -> str:
    """
    If the input is CSV, force CSV output even if OUTPUT_FILE was set to .xlsx.
    Otherwise, keep the provided output path.
    """
    _, in_ext = os.path.splitext(input_file_path)
    _, out_ext = os.path.splitext(output_file_path)
    in_ext = in_ext.lower()
    out_ext = out_ext.lower()

    if in_ext == ".csv" and out_ext != ".csv":
        base, _ = os.path.splitext(output_file_path)
        return f"{base}.csv"

    return output_file_path

def _text_protect_phone(value) -> Optional[str]:
    """
    Prefixes a value with a leading apostrophe so Excel/Sheets treat it as text.
    (Excel typically hides the apostrophe in display, but preserves the value as text.)
    """
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if s == "":
        return ""
    if s.startswith("'"):
        return s
    return f"'{s}"

def _default_filtered_output_path(input_file_path: str) -> str:
    base, ext = os.path.splitext(input_file_path)
    if not ext:
        ext = ".xlsx"
    return f"{base}_filtered{ext}"

def process_and_filter_excel(input_file_path, output_file_path, primary_phone_col, secondary_phone_col=""):
    """
    Reads a CSV or Excel file, filters rows based on phone numbers (DACH only).

    - Keeps rows where the formatted primary phone is in DACH (+49/+41/+43).
    - If a secondary phone column is provided and exists: rows can be "rescued" by a DACH secondary number
      (the primary will be replaced by the secondary).
    - If input is CSV, output files are written as CSV too (same delimiter style).
    - Phone values are prefixed with a leading apostrophe before writing, to "text-protect" them in Excel/Sheets.
    """
    try:
        df, csv_sep = _load_dataframe(input_file_path)
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}")
        return
    except ValueError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Error reading input file {input_file_path}: {e}")
        return

    if primary_phone_col not in df.columns:
        print(f"Error: Primary phone column '{primary_phone_col}' not found in '{input_file_path}'.")
        print(f"Available columns are: {df.columns.tolist()}")
        return

    secondary_phone_col = (secondary_phone_col or "").strip()
    if not secondary_phone_col:
        secondary_phone_col = None
    elif secondary_phone_col not in df.columns:
        print(f"Warning: Secondary phone column '{secondary_phone_col}' not found in input. Continuing without it.")
        secondary_phone_col = None

    # If CSV input, force CSV outputs even if OUTPUT_FILE is set to .xlsx
    output_file_path = _ensure_output_ext_matches_input(input_file_path, output_file_path)

    # Format phone columns
    df['formatted_primary'] = df[primary_phone_col].apply(format_phone_number)
    if secondary_phone_col:
        df['formatted_secondary'] = df[secondary_phone_col].apply(format_phone_number)
    else:
        df['formatted_secondary'] = None

    # Build keep mask, optionally rescuing with secondary
    mask_primary_ok = df['formatted_primary'].apply(lambda p: p is not None and is_desired_country(p))

    if secondary_phone_col:
        mask_secondary_ok = df['formatted_secondary'].apply(lambda p: p is not None and is_desired_country(p))
        mask_rescue = (~mask_primary_ok) & mask_secondary_ok
        if mask_rescue.any():
            df.loc[mask_rescue, primary_phone_col] = df.loc[mask_rescue, 'formatted_secondary']
            df.loc[mask_rescue, 'formatted_primary'] = df.loc[mask_rescue, 'formatted_secondary']
        mask_keep = mask_primary_ok | mask_secondary_ok
    else:
        mask_keep = mask_primary_ok
    
    # Update the original phone column with the formatted number for all kept rows
    df.loc[mask_keep, primary_phone_col] = df.loc[mask_keep, 'formatted_primary']

    # Text-protect phone values before writing output
    df.loc[mask_keep, primary_phone_col] = df.loc[mask_keep, primary_phone_col].apply(_text_protect_phone)

    # Select the DataFrames for kept and removed rows
    df_kept = df[mask_keep].drop(columns=['formatted_primary', 'formatted_secondary'])
    df_removed = df[~mask_keep].drop(columns=['formatted_primary', 'formatted_secondary'])

    # Also text-protect removed rows (so opening the removed file in Excel won't mangle numbers)
    if primary_phone_col in df_removed.columns:
        df_removed[primary_phone_col] = df_removed[primary_phone_col].apply(_text_protect_phone)

    def save_df(dataframe, file_path):
        """Save as CSV or Excel depending on file extension."""
        try:
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")

            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            if ext == ".csv":
                sep_to_use = csv_sep or ';'
                dataframe.to_csv(file_path, index=False, sep=sep_to_use, encoding="utf-8-sig")
                print(f"Successfully saved {len(dataframe)} rows to {file_path}")
                return

            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                dataframe.to_excel(writer, index=False, sheet_name='Sheet1')
                worksheet = writer.sheets['Sheet1']

                # Set phone column as text in Excel (extra safety)
                text_fmt = writer.book.add_format({'num_format': '@'})
                phone_col_idx = None
                if primary_phone_col in dataframe.columns:
                    phone_col_idx = dataframe.columns.get_loc(primary_phone_col)

                for i, col in enumerate(dataframe.columns):
                    max_len = 0
                    if len(dataframe) > 0:
                        col_max = dataframe[col].astype(str).map(len).max()
                        if pd.isna(col_max):
                            col_max = 0
                        max_len = int(col_max)
                    max_len = max(max_len, len(str(col))) + 2

                    if phone_col_idx is not None and i == phone_col_idx:
                        worksheet.set_column(i, i, max_len, text_fmt)
                    else:
                        worksheet.set_column(i, i, max_len)
            
            print(f"Successfully saved {len(dataframe)} rows to {file_path}")
        except Exception as e:
            print(f"Error writing output file {file_path}: {e}")

    # Save the kept and removed rows to separate files
    save_df(df_kept, output_file_path)
    
    base, ext = os.path.splitext(output_file_path)
    removed_output_path = f"{base}_removed{ext}"
    save_df(df_removed, removed_output_path)

    print("\n--- Summary ---")
    print(f"Original rows: {len(df)}")
    print(f"Kept rows: {len(df_kept)} (saved to {output_file_path})")
    print(f"Removed rows: {len(df_removed)} (saved to {removed_output_path})")

if __name__ == "__main__":
    DEFAULT_INPUT_FILE = 'data/input_augmented_5_30_STITCHED.csv'
    DEFAULT_PRIMARY_PHONE_COLUMN = 'found_number'
    DEFAULT_SECONDARY_PHONE_COLUMN = ''

    parser = argparse.ArgumentParser(
        description=(
            "Filter rows by DACH phone numbers (+49/+41/+43). "
            "Reads CSV or Excel; if input is CSV, outputs are CSV too. "
            "Writes both kept rows and a *_removed file for removed rows."
        )
    )
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT_FILE, help="Input file path (.csv/.xlsx/.xls/.xlsm).")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output file path for kept rows. If omitted, uses <input>_filtered.<ext>. "
            "If input is CSV, output extension is forced to .csv."
        ),
    )
    parser.add_argument(
        "--primary-col",
        default=DEFAULT_PRIMARY_PHONE_COLUMN,
        help="Primary phone number column name (will be normalized + text-protected).",
    )
    parser.add_argument(
        "--secondary-col",
        default=DEFAULT_SECONDARY_PHONE_COLUMN,
        help="Optional secondary phone column name; if provided and in DACH, it can replace an invalid primary.",
    )

    args = parser.parse_args()

    input_file = args.input
    output_file = args.output or _default_filtered_output_path(input_file)
    primary_col = args.primary_col
    secondary_col = args.secondary_col

    print(f"Starting phone number filtering for '{input_file}'...")
    print(f"Primary phone column: '{primary_col}'")
    print(f"Secondary phone column: '{secondary_col}'")
    print("If primary number is not in DACH region, will check secondary number (if provided).")
    print(f"Kept rows will be saved to: '{output_file}' (format follows input)")
    print("Removed rows will be saved to a separate file with a '_removed' suffix.")

    process_and_filter_excel(input_file, output_file, primary_col, secondary_col)