import pandas as pd

# Define file paths
file1 = 'data/merged_output_filtered.xlsx'
file2 = 'data/add these numbers.xlsx'

try:
    df1 = pd.read_excel(file1)
    df2 = pd.read_excel(file2)

    print("--- Columns for matching ---")
    print(f"\nFrom: {file1}")
    print(df1[['firma']].head())

    print(f"\nFrom: {file2}")
    print(df2[['Company Name', 'found_number']].head())

    # Show which companies from the second file are present in the first file
    matching_companies = df2[df2['Company Name'].isin(df1['firma'])]
    print(f"\nFound {len(matching_companies)} matching companies to update.")
    if not matching_companies.empty:
        print("Example of matching companies and the numbers to be added:")
        print(matching_companies[['Company Name', 'found_number']].head())

except FileNotFoundError as e:
    print(f"Error: {e.filename} not found.")
except Exception as e:
    print(f"An error occurred: {e}")