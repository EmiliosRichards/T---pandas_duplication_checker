import pandas as pd

# Define file paths
target_file = 'data/merged_output_filtered.xlsx'
source_file = 'data/add these numbers.xlsx'
output_file = 'data/merged_output_final.xlsx'

# Read the excel files
try:
    target_df = pd.read_excel(target_file)
    source_df = pd.read_excel(source_file)

    # Create a dictionary from the source dataframe for mapping
    # Company Name -> found_number
    phone_map = pd.Series(source_df.found_number.values, index=source_df['Company Name']).to_dict()

    # Update the 'Telefonnummer' column in the target dataframe
    # The .map() function will update the values where a match is found in the phone_map
    # and leave the original value for non-matches (NaN will be ignored by .fillna())
    target_df['Telefonnummer'] = target_df['firma'].map(phone_map).fillna(target_df['Telefonnummer'])

    # Save the updated dataframe to a new file
    target_df.to_excel(output_file, index=False)

    print(f"Successfully updated phone numbers and saved to {output_file}")

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")