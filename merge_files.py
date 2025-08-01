import pandas as pd

# Define file paths
file1 = 'data/manuav_b_liste_check_processedfiltered_augmented_20250731_120245.xlsx'
file2 = 'data/thisonehere.xlsx'
output_file = 'data/merged_output.xlsx'

# Read the excel files
try:
    df1 = pd.read_excel(file1)
    df2 = pd.read_excel(file2)

    # Perform the merge
    # The 'firma' column from df1 is matched with the 'Company Name' column from df2.
    # We are adding the 'sales_pitch' column from df2 to df1.
    merged_df = pd.merge(df1, df2[['Company Name', 'sales_pitch']], left_on='firma', right_on='Company Name', how='left')

    # Drop the extra 'Company Name' column from the merged dataframe
    merged_df = merged_df.drop(columns=['Company Name'])

    # Save the merged dataframe to a new excel file
    merged_df.to_excel(output_file, index=False)

    print(f"Successfully merged files and saved the output to {output_file}")

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")