import pandas as pd
import re
import sys

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
This script extracts dynamic text and lead counts from a sales pitch column in an Excel file.
It can be run with command-line arguments for flexibility or use the default configuration below.
"""

# --- Configuration (used if no command-line arguments are provided) ---
DEFAULT_INPUT_FILE = 'data/final_output.xlsx'
DEFAULT_OUTPUT_FILE = 'data/final_output_with_pitch_text.xlsx'
DEFAULT_PITCH_COLUMN = 'Sales_Pitch'
# --- End of Configuration ---

def process_excel_file(file_path, pitch_column, output_path):
    """
    Processes an Excel file to extract dynamic pitch text and lead count.
    
    Args:
        file_path (str): The path to the input Excel file.
        pitch_column (str): The name of the column containing the sales pitch.
        output_path (str): The path to save the processed Excel file.
    """
    try:
        # Read the Excel file, ensuring phone number columns are treated as text
        df = pd.read_excel(file_path, dtype={'Telefonnummer': str, '$phone': str})
        
        # Check if the specified pitch column exists
        if pitch_column not in df.columns:
            print(f"Error: Column '{pitch_column}' not found in {file_path}")
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
        df.loc[rows_to_process, 'dynamic_pitch_text'] = df.loc[rows_to_process, pitch_column].apply(extract_dynamic_pitch)
        df.loc[rows_to_process, 'lead_count'] = df.loc[rows_to_process, pitch_column].apply(extract_lead_count)
        
        # Save the updated DataFrame to a new Excel file
        df.to_excel(output_path, index=False)
        
        print(f"Successfully processed {file_path}.")
        print(f"New file created at: {output_path}")
        
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    INPUT_FILE = 'data/step4_phone_numbers_filtered.xlsx'
    OUTPUT_FILE = 'data/final_output.xlsx'
    PITCH_COLUMN = 'Sales_Pitch'

    if len(sys.argv) > 2:
        # Use command-line arguments if provided
        file_path = sys.argv[1]
        pitch_column_name = sys.argv[2]
        output_file_path = file_path.replace('.xlsx', '_processed.xlsx')
        print(f"Starting pitch text extraction for '{file_path}' using command-line arguments...")
        process_excel_file(file_path, pitch_column_name, output_file_path)
    else:
        # Use default configuration if no command-line arguments are provided
        print(f"Starting pitch text extraction for '{INPUT_FILE}' using default configuration...")
        process_excel_file(INPUT_FILE, PITCH_COLUMN, OUTPUT_FILE)
