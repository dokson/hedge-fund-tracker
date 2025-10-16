from app.utils.database import DB_FOLDER, HEDGE_FUNDS_FILE, MODELS_FILE, STOCKS_FILE, LATEST_SCHEDULE_FILINGS_FILE, count_funds_in_quarter, get_all_quarter_files, get_all_quarters, get_last_quarter, get_last_quarter_for_fund, load_quarterly_data, load_stocks, save_comparison, save_non_quarterly_filings
from pathlib import Path
import pandas as pd
import os
import shutil
import unittest
import unittest.mock


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """
        Set up a temporary database directory and files for testing.
        This runs before each test.
        """
        self.test_db_folder = 'test_db'
        os.makedirs(self.test_db_folder, exist_ok=True)

        # Create dummy quarter directories and files
        os.makedirs(os.path.join(self.test_db_folder, '2025Q1'), exist_ok=True)
        os.makedirs(os.path.join(self.test_db_folder, '2024Q4'), exist_ok=True)
        os.makedirs(os.path.join(self.test_db_folder, 'not_a_quarter'), exist_ok=True)
        
        with open(os.path.join(self.test_db_folder, '2025Q1', 'Fund_A.csv'), 'w') as f:
            f.write("CUSIP,Value\n123,100\n")
        with open(os.path.join(self.test_db_folder, '2025Q1', 'Fund_B.csv'), 'w') as f:
            f.write("CUSIP,Value\n456,200\n")
        with open(os.path.join(self.test_db_folder, '2024Q4', 'Fund_A.csv'), 'w') as f:
            f.write("CUSIP,Value\n789,300\n")

        # Create dummy main db files
        with open(os.path.join(self.test_db_folder, HEDGE_FUNDS_FILE), 'w') as f:
            f.write("CIK,Fund,Manager,Denomination,CIKs\n001,Fund A,Manager A,Denom A,\n")
        with open(os.path.join(self.test_db_folder, MODELS_FILE), 'w') as f:
            f.write("ID,Description,Client\nmodel-1,Google Model,Google\nmodel-2,Groq Model,Groq\n")
        with open(os.path.join(self.test_db_folder, STOCKS_FILE), 'w') as f:
            f.write("CUSIP,Ticker,Company\n123,TICKA,Company A\n")
        with open(os.path.join(self.test_db_folder, LATEST_SCHEDULE_FILINGS_FILE), 'w') as f:
            f.write("Fund,Ticker,Filing_Date,Date\nFund A,TICKA,2025-01-01,2025-01-01\nFund A,TICKA,2025-01-02,2025-01-02\n")

        # Patch the DB_FOLDER constant to use the test directory
        self.original_db_folder = DB_FOLDER
        self.patcher = unittest.mock.patch('app.utils.database.DB_FOLDER', self.test_db_folder)
        self.patcher.start()


    def test_get_all_quarters(self):
        """
        Tests that `get_all_quarters` correctly identifies and sorts quarter directories.
        """
        quarters = get_all_quarters()
        self.assertEqual(quarters, ['2025Q1', '2024Q4'])


    def test_get_last_quarter(self):
        """
        Tests that `get_last_quarter` returns the most recent quarter.
        """
        last_quarter = get_last_quarter()
        self.assertEqual(last_quarter, '2025Q1')


    def test_count_funds_in_quarter(self):
        """
        Tests `count_funds_in_quarter` for both an existing and a non-existent quarter.
        """
        count = count_funds_in_quarter('2025Q1')
        self.assertEqual(count, 2)
        count_empty = count_funds_in_quarter('2023Q1') # Non-existent
        self.assertEqual(count_empty, 0)


    def test_get_last_quarter_for_fund(self):
        """
        Tests `get_last_quarter_for_fund` for existing and non-existent funds.
        """
        last_quarter = get_last_quarter_for_fund('Fund A')
        self.assertEqual(last_quarter, '2025Q1')
        last_quarter_b = get_last_quarter_for_fund('Fund B')
        self.assertEqual(last_quarter_b, '2025Q1')
        last_quarter_c = get_last_quarter_for_fund('Fund C') # Non-existent
        self.assertIsNone(last_quarter_c)


    def test_get_all_quarter_files(self):
        """
        Tests that `get_all_quarter_files` returns all CSV files in a given quarter directory.
        """
        files = get_all_quarter_files('2025Q1')
        self.assertEqual(len(files), 2)
        self.assertTrue(any('Fund_A.csv' in f for f in files))
        self.assertTrue(any('Fund_B.csv' in f for f in files))


    def test_load_quarterly_data(self):
        """
        Tests that `load_quarterly_data` correctly loads and concatenates data from all fund files in a quarter.
        """
        df = load_quarterly_data('2025Q1')
        self.assertEqual(len(df), 2)
        self.assertTrue('Fund' in df.columns)
        self.assertEqual(df['Fund'].nunique(), 2)


    def test_load_stocks(self):
        """
        Tests loading stocks from a correctly formatted file.
        """
        filepath = os.path.join(self.test_db_folder, STOCKS_FILE)
        df = load_stocks(filepath)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.index.name, 'CUSIP')
        self.assertEqual(df.loc['123', 'Ticker'], 'TICKA')


    def test_load_stocks_file_not_found(self):
        """
        Tests that load_stocks returns an empty DataFrame when the file doesn't exist.
        """
        filepath = os.path.join(self.test_db_folder, 'non_existent_stocks.csv')
        df = load_stocks(filepath)
        self.assertTrue(df.empty)


    def test_load_stocks_empty_file(self):
        """
        Tests that load_stocks returns an empty DataFrame for an empty file (with headers).
        """
        filepath = os.path.join(self.test_db_folder, 'empty_stocks.csv')
        with open(filepath, 'w') as f:
            f.write("CUSIP,Ticker,Company\n")
        df = load_stocks(filepath)
        self.assertTrue(df.empty)


    def test_save_comparison(self):
        """
        Tests that `save_comparison` correctly saves a DataFrame to a CSV file in the correct quarter directory.
        """
        df_to_save = pd.DataFrame([{'col1': 'val1'}])
        save_comparison(df_to_save, '2025-03-31', 'My Test Fund')
        
        expected_path = Path(self.test_db_folder) / '2025Q1' / 'My_Test_Fund.csv'
        self.assertTrue(expected_path.exists())
        
        df_read = pd.read_csv(expected_path)
        self.assertEqual(df_read.iloc[0]['col1'], 'val1')


    def test_save_non_quarterly_filings(self):
        """
        Tests that `save_non_quarterly_filings` correctly combines and saves a list of DataFrames.
        """
        df1 = pd.DataFrame([{'Fund': 'F1', 'Date': '2025-01-01', 'Filing_Date': '2025-01-01', 'Ticker': 'T1'}])
        df2 = pd.DataFrame([{'Fund': 'F2', 'Date': '2025-01-02', 'Filing_Date': '2025-01-02', 'Ticker': 'T2'}])
        
        filepath = os.path.join(self.test_db_folder, 'test_nq.csv')
        save_non_quarterly_filings([df1, df2], filepath=filepath)

        self.assertTrue(os.path.exists(filepath))
        df_read = pd.read_csv(filepath)
        self.assertEqual(len(df_read), 2)
        # Check if sorted correctly (descending by date)
        self.assertEqual(df_read.iloc[0]['Fund'], 'F2')


    def tearDown(self):
        """
        Clean up the temporary database directory.
        This runs after each test.
        """
        shutil.rmtree(self.test_db_folder)
        self.patcher.stop()


if __name__ == '__main__':
    unittest.main()
