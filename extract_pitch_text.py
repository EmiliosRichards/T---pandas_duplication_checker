import pandas as pd
import re
import sys
import os
import argparse
from typing import Optional, Tuple, List

def extract_dynamic_pitch(pitch):
    if not isinstance(pitch, str):
        return ""
    
    start_phrase = "Ich rufe Sie an, weil wir bereits sehr erfolgreich ein ähnliches Projekt umgesetzt haben"
    end_phrase = "Für dieses"
    
    # Use regex to find the text between the start and end phrases
    # The (?s) flag allows . to match newlines
    match = re.search(f"{re.escape(start_phrase)}(.*?){re.escape(end_phrase)}", pitch, re.DOTALL)
    
    if match:
        # .strip() removes leading/trailing whitespace and newlines
        return match.group(1).strip()
    return ""

def extract_lead_count(pitch):
    if not isinstance(pitch, str):
        return None
    
    # Regex to find a number followed by "Leads"
    match = re.search(r'(\d+)\s+Leads', pitch, re.IGNORECASE)
    
    if match:
        return int(match.group(1))
    return None

"""
This script extracts dynamic text and lead counts from a sales pitch column in a CSV or Excel file.
"""

# --- Configuration (used if no command-line arguments are provided) ---
DEFAULT_INPUT_FILE = 'data/20250408_kevin_monday_morning_filtered.xlsx'
DEFAULT_OUTPUT_FILE = 'data/kevin_monday_morning_with_pitch_text.xlsx'
DEFAULT_PITCH_COLUMN = 'Sales_Pitch'
# --- End of Configuration ---

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
        return pd.read_excel(input_file_path, dtype=str), None

    if ext in (".csv", ".txt"):
        sep = _sniff_csv_separator(input_file_path)
        return pd.read_csv(input_file_path, sep=sep, dtype=str, encoding="utf-8-sig"), sep

    raise ValueError(f"Unsupported input file type: '{ext}'. Use .csv or Excel (.xlsx/.xls/.xlsm).")

def _ensure_output_ext_matches_input(input_file_path: str, output_file_path: str) -> str:
    """
    If the input is CSV, force CSV output even if the output was set to .xlsx.
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

def _default_output_path(input_file_path: str) -> str:
    base, ext = os.path.splitext(input_file_path)
    if not ext:
        ext = ".xlsx"
    return f"{base}_with_pitch_text{ext}"

def _auto_detect_pitch_column(df: pd.DataFrame, preferred: Optional[str]) -> Optional[str]:
    if preferred and preferred in df.columns:
        return preferred
    if preferred:
        return None

    # Common column names in this repo / datasets
    candidates: List[str] = [
        "sales_pitch",
        "Sales_Pitch",
        "Sales Pitch",
        "pitch",
        "Pitch",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    return None

def process_file(file_path: str, pitch_column: Optional[str], output_path: str):
    """
    Processes a CSV/Excel file to extract dynamic pitch text and lead count.
    
    Args:
        file_path (str): The path to the input file.
        pitch_column (Optional[str]): Column containing the sales pitch. If None, will try to auto-detect.
        output_path (str): The path to save the processed file.
    """
    try:
        df, csv_sep = _load_dataframe(file_path)
        
        detected_pitch_column = _auto_detect_pitch_column(df, pitch_column)
        if not detected_pitch_column:
            if pitch_column:
                print(f"Error: Column '{pitch_column}' not found in {file_path}")
            else:
                print("Error: Could not auto-detect a pitch column.")
            print(f"Available columns are: {df.columns.tolist()}")
            return

        # Identify rows where 'dynamic_pitch_text' is missing or empty
        if 'dynamic_pitch_text' in df.columns:
            rows_to_process = df['dynamic_pitch_text'].isnull() | (df['dynamic_pitch_text'] == '')
        else:
            # If the column doesn't exist, process all rows
            rows_to_process = pd.Series([True] * len(df), index=df.index)
            df['dynamic_pitch_text'] = ''
            df['lead_count'] = None

        print(f"Found {rows_to_process.sum()} rows to process.")

        # Apply the functions to the identified rows
        df.loc[rows_to_process, 'dynamic_pitch_text'] = df.loc[rows_to_process, detected_pitch_column].apply(extract_dynamic_pitch)
        df.loc[rows_to_process, 'lead_count'] = df.loc[rows_to_process, detected_pitch_column].apply(extract_lead_count)
        
        output_path = _ensure_output_ext_matches_input(file_path, output_path)

        _, ext = os.path.splitext(output_path)
        ext = ext.lower()
        if ext == ".csv":
            sep_to_use = csv_sep or ';'
            df.to_csv(output_path, index=False, sep=sep_to_use, encoding="utf-8-sig")
        else:
            df.to_excel(output_path, index=False)
        
        print(f"Successfully processed {file_path}.")
        print(f"New file created at: {output_path}")
        
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Backwards compatibility: if old positional args are used, preserve behavior.
    # Old usage: python extract_pitch_text.py <file_path> <pitch_column>
    if len(sys.argv) > 2 and not sys.argv[1].startswith("-"):
        file_path = sys.argv[1]
        pitch_column_name = sys.argv[2]
        output_file_path = _default_output_path(file_path)
        print(f"Starting pitch text extraction for '{file_path}' (positional args)...")
        process_file(file_path, pitch_column_name, output_file_path)
        raise SystemExit(0)

    parser = argparse.ArgumentParser(
        description=(
            "Extract dynamic pitch text + lead count from a pitch column. "
            "Reads CSV or Excel; if input is CSV, output is CSV too."
        )
    )
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT_FILE, help="Input file path (.csv/.xlsx/.xls/.xlsm).")
    parser.add_argument(
        "-c",
        "--pitch-column",
        default=None,
        help="Pitch column name. If omitted, the script will try to auto-detect (e.g., 'sales_pitch').",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file path. If omitted, uses <input>_with_pitch_text.<ext> (format follows input).",
    )

    args = parser.parse_args()
    input_file = args.input
    output_file = args.output or _default_output_path(input_file)

    print(f"Starting pitch text extraction for '{input_file}'...")
    print(f"Pitch column: '{args.pitch_column or '(auto-detect)'}'")
    print(f"Output will be saved to: '{output_file}'")

    process_file(input_file, args.pitch_column, output_file)
