import pandas as pd

# Define file paths
file_with_extras = 'data/manuav_b_liste_check.xlsx'
target_file = 'data/step2_phone_numbers_updated.xlsx'
output_file = 'data/step3_rows_appended.xlsx'

try:
    df_extras = pd.read_excel(file_with_extras)
    df_target = pd.read_excel(target_file)

    # Find rows in df_extras that are not in df_target, based on the '$id' column
    extra_rows = df_extras[~df_extras['$id'].isin(df_target['$id'])]

    # Append the extra rows to the target dataframe
    updated_df = pd.concat([df_target, extra_rows], ignore_index=True)

    # Save the updated dataframe to a new excel file
    updated_df.to_excel(output_file, index=False)

    print(f"Successfully appended {len(extra_rows)} rows and saved the output to {output_file}")

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")