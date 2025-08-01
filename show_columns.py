import pandas as pd

try:
    df = pd.read_excel('data/thisonehere.xlsx')
    print("Columns in 'data/thisonehere.xlsx':")
    print(df.columns.tolist())
except FileNotFoundError:
    print("Error: 'data/thisonehere.xlsx' not found.")
except Exception as e:
    print(f"An error occurred: {e}")