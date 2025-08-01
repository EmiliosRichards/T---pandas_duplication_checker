import pandas as pd

# Define file paths
target_file = 'data/step1_sales_pitch_updated.xlsx'
source_file = 'data/add these numbers.xlsx'
output_file = 'data/step2_phone_numbers_updated.xlsx'

# Read the excel files
try:
    target_df = pd.read_excel(target_file)
    source_df = pd.read_excel(source_file)

    # Ensure phone number column is read correctly
    source_df['found_number'] = pd.to_numeric(source_df['found_number'], errors='coerce').astype('Int64').astype(str).replace('<NA>', '')

    # Create a dictionary from the source dataframe for mapping
    # Company Name -> found_number
    phone_map = pd.Series(source_df.found_number.values, index=source_df['Company Name']).to_dict()

    # Update the 'Telefonnummer' column in the target dataframe
    target_df['Telefonnummer'] = target_df['firma'].map(phone_map).fillna(target_df['Telefonnummer'])

    # Save the updated dataframe to a new file
    target_df.to_excel(output_file, index=False)

    print(f"Successfully updated phone numbers and saved to {output_file}")

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")