
import pandas as pd

try:
    df = pd.read_excel('機構額度使用.xls')
    print("Columns:", df.columns.tolist())
    print("First 2 rows:", df.head(2).to_dict())
    print("Dtypes:", df.dtypes)
except Exception as e:
    print("Error reading excel:", e)
