import pandas as pd

# Define file paths
file_with_extras = 'data/manuav_b_liste_check.xlsx'
file_to_compare = 'data/merged_output_final.xlsx'

try:
    df_extras = pd.read_excel(file_with_extras)
    df_compare = pd.read_excel(file_to_compare)

    print("--- Comparing files to find extra rows ---")

    # Find rows in df_extras that are not in df_compare, based on the '$id' column
    extra_rows = df_extras[~df_extras['$id'].isin(df_compare['$id'])]

    print(f"\nFound {len(extra_rows)} extra rows in '{file_with_extras}'.")

    if not extra_rows.empty:
        print("\nHere are the extra rows:")
        print(extra_rows)

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")