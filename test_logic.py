
import pandas as pd
import unittest

def clean_currency_column(series):
    """Removes commas and converts to float."""
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce').fillna(0)

def get_aggregated_usage(df):
    """
    Simulates the app's aggregation logic.
    """
    # Clean
    df['照管金額分配額度'] = clean_currency_column(df['照管金額分配額度'])
    df['服務紀錄(不含自費)'] = clean_currency_column(df['服務紀錄(不含自費)'])
    
    # Aggregate
    grouped = df.groupby(['月份', '機構', '主責人員', '個案']).agg({
        '照管金額分配額度': 'max',
        '服務紀錄(不含自費)': 'max'
    }).reset_index()
    
    return grouped

class TestUsageLogic(unittest.TestCase):
    def test_aggregation(self):
        # Mock Data: One Case, One Month, 3 Service Items
        # Quota and TotalUsed should be repeated
        data = {
            '月份': ['11', '11', '11'],
            '機構': ['Agency A'] * 3,
            '主責人員': ['Staff A'] * 3,
            '個案': ['Case 1'] * 3,
            '照管金額分配額度': ['10,000', '10,000', '10,000'], # Repeated
            '服務紀錄(不含自費)': ['5,000', '5,000', '5,000'],   # Repeated
            '服務項目': ['Item 1', 'Item 2', 'Item 3'],
            '服務紀錄使用額度': [1000, 2000, 2000] # Sums to 5000
        }
        df = pd.DataFrame(data)
        
        agg = get_aggregated_usage(df)
        
        # Expect 1 row
        self.assertEqual(len(agg), 1)
        
        # Expect Quota = 10000 (not 30000)
        self.assertEqual(agg.iloc[0]['照管金額分配額度'], 10000)
        
        # Expect Used = 5000 (not 15000)
        self.assertEqual(agg.iloc[0]['服務紀錄(不含自費)'], 5000)
        
        print("\nTest Passed: Aggregation logic correctly handled repeated columns.")

    def test_string_cleaning(self):
        s = pd.Series(['1,234', '500', 'invalid'])
        cleaned = clean_currency_column(s)
        self.assertEqual(cleaned[0], 1234)
        self.assertEqual(cleaned[1], 500)
        self.assertEqual(cleaned[2], 0)
        print("Test Passed: String cleaning works.")

if __name__ == '__main__':
    unittest.main()
