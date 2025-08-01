import pandas as pd

# Define file paths
file1 = 'data/manuav_b_liste_check_processedfiltered_augmented_20250731_120245.xlsx'
file2 = 'data/thisonehere.xlsx'
output_file = 'data/step1_sales_pitch_updated.xlsx'

# Read the excel files
try:
    df1 = pd.read_excel(file1)
    df2 = pd.read_excel(file2)

    # Create a dictionary from the source dataframe for mapping
    # Company Name -> sales_pitch
    sales_pitch_map = pd.Series(df2.sales_pitch.values, index=df2['Company Name']).to_dict()

    # Update the 'Sales_Pitch' column in the target dataframe
    df1['Sales_Pitch'] = df1['firma'].map(sales_pitch_map).fillna(df1['Sales_Pitch'])

    # Save the updated dataframe to a new excel file
    df1.to_excel(output_file, index=False)

    print(f"Successfully updated sales pitches and saved the output to {output_file}")

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")