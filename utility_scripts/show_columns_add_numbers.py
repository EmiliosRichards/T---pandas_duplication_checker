import pandas as pd

try:
    df = pd.read_excel('data/add these numbers.xlsx')
    print("Columns in 'data/add these numbers.xlsx':")
    print(df.columns.tolist())
except FileNotFoundError:
    print("Error: 'data/add these numbers.xlsx' not found.")
except Exception as e:
    print(f"An error occurred: {e}")