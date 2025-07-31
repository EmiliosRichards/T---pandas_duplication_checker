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

def process_excel_file(file_path, pitch_column):
    try:
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # Check if the specified pitch column exists
        if pitch_column not in df.columns:
            print(f"Error: Column '{pitch_column}' not found in {file_path}")
            return
            
        # Apply the functions to create the new columns
        df['dynamic_pitch_text'] = df[pitch_column].apply(extract_dynamic_pitch)
        df['lead_count'] = df[pitch_column].apply(extract_lead_count)
        
        # Check if any dynamic pitch text was extracted
        if df['dynamic_pitch_text'].str.strip().eq('').all():
            print("Warning: No dynamic pitch text could be extracted from the 'sales_pitch' column for any row.")
            print("Please check the start and end phrases and the content of the 'sales_pitch' column.")

        # Check if any lead counts were extracted
        if df['lead_count'].isnull().all():
            print("Warning: No lead count could be extracted from the 'sales_pitch' column for any row.")

        # Define the output file path
        output_path = file_path.replace('.xlsx', '_processed.xlsx')

        # Save the updated DataFrame to a new Excel file
        df.to_excel(output_path, index=False)
        
        print(f"Successfully processed {file_path}.")
        print(f"New file created at: {output_path}")
        
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        file_path = sys.argv[1]
        pitch_column_name = sys.argv[2]
        process_excel_file(file_path, pitch_column_name)
    else:
        print("Usage: python extract_pitch_text.py <file_path> <pitch_column_name>")
        print("Example: python extract_pitch_text.py \"data/my_file.xlsx\" \"Sales Pitch\"")
