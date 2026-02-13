from app.utils.database import (
    HEDGE_FUNDS_FILE, MODELS_FILE, STOCKS_FILE, LATEST_SCHEDULE_FILINGS_FILE, GICS_HIERARCHY_FILE,
    count_funds_in_quarter, get_all_quarters, get_last_quarter, get_last_quarter_for_fund, get_quarters_for_fund,
    load_stocks, load_fund_holdings, load_hedge_funds, load_models, load_non_quarterly_data, load_gics_hierarchy,
    save_stock, sort_stocks, find_cusips_for_ticker, update_ticker, delete_fund_from_database, get_most_recent_quarter
)
import pandas as pd
import os
import shutil
import unittest
import unittest.mock
import threading
import time


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
        
        with open(os.path.join(self.test_db_folder, '2025Q1', 'Fund_A.csv'), 'w', newline='') as f:
            f.write("CUSIP,Ticker,Value,Shares\n123,TICKA,100,10\nTotal,Total,100,10\n")
        with open(os.path.join(self.test_db_folder, '2025Q1', 'Fund_B.csv'), 'w', newline='') as f:
            f.write("CUSIP,Ticker,Value,Shares\n456,TICKB,200,20\n")
        with open(os.path.join(self.test_db_folder, '2024Q4', 'Fund_A.csv'), 'w', newline='') as f:
            f.write("CUSIP,Ticker,Value,Shares\n123,TICKA,80,10\n")

        # Create dummy main db files
        with open(os.path.join(self.test_db_folder, HEDGE_FUNDS_FILE), 'w', newline='') as f:
            f.write("CIK,Fund,Manager,Denomination,CIKs\n001,Fund A,Manager A,Denom A,\n")
        
        with open(os.path.join(self.test_db_folder, MODELS_FILE), 'w', newline='') as f:
            f.write("ID,Description,Client\nmodel-1,Google Model,Google\n")
        
        with open(os.path.join(self.test_db_folder, STOCKS_FILE), 'w', newline='') as f:
            f.write("CUSIP,Ticker,Company\n123,TICKA,Company A\n456,TICKB,Company B\n")
        
        with open(os.path.join(self.test_db_folder, LATEST_SCHEDULE_FILINGS_FILE), 'w', newline='') as f:
            f.write("Fund,Ticker,CUSIP,Date,Filing_Date\nFund A,TICKA,123,2025-01-01,2025-01-01\n")

        os.makedirs(os.path.join(self.test_db_folder, 'GICS'), exist_ok=True)
        with open(os.path.join(self.test_db_folder, GICS_HIERARCHY_FILE), 'w', newline='') as f:
            f.write("Sector,Industry\nTech,Software\n")

        # Patch the DB_FOLDER constant to use the test directory
        self.patcher = unittest.mock.patch('app.utils.database.DB_FOLDER', self.test_db_folder)
        self.patcher.start()


    def test_get_all_quarters(self):
        self.assertEqual(get_all_quarters(), ['2025Q1', '2024Q4'])


    def test_get_last_quarter(self):
        self.assertEqual(get_last_quarter(), '2025Q1')


    def test_count_funds_in_quarter(self):
        self.assertEqual(count_funds_in_quarter('2025Q1'), 2)
        self.assertEqual(count_funds_in_quarter('2023Q1'), 0)


    def test_get_last_quarter_for_fund(self):
        self.assertEqual(get_last_quarter_for_fund('Fund A'), '2025Q1')
        self.assertIsNone(get_last_quarter_for_fund('Fund C'))


    def test_get_quarters_for_fund(self):
        self.assertEqual(get_quarters_for_fund('Fund A'), ['2025Q1', '2024Q4'])
        self.assertEqual(get_quarters_for_fund('Fund B'), ['2025Q1'])
        self.assertEqual(get_quarters_for_fund('Fund C'), [])


    def test_get_most_recent_quarter(self):
        self.assertEqual(get_most_recent_quarter('TICKA'), '2025Q1')
        self.assertEqual(get_most_recent_quarter('TICKB'), '2025Q1')
        self.assertIsNone(get_most_recent_quarter('UNKNOWN'))


    def test_load_fund_holdings(self):
        df = load_fund_holdings('Fund A', '2025Q1')
        self.assertEqual(len(df), 1) # Total row excluded
        self.assertIn('Reported_Price', df.columns)
        self.assertEqual(df.iloc[0]['Reported_Price'], 10.0)


    def test_load_hedge_funds(self):
        funds = load_hedge_funds(f'./{self.test_db_folder}/{HEDGE_FUNDS_FILE}')
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]['Fund'], 'Fund A')


    def test_load_models(self):
        models = load_models(f'./{self.test_db_folder}/{MODELS_FILE}')
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]['ID'], 'model-1')


    def test_load_non_quarterly_data(self):
        df = load_non_quarterly_data(f'./{self.test_db_folder}/{LATEST_SCHEDULE_FILINGS_FILE}')
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['Ticker'], 'TICKA')


    def test_load_gics_hierarchy(self):
        df = load_gics_hierarchy(f'./{self.test_db_folder}/{GICS_HIERARCHY_FILE}')
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['Sector'], 'Tech')


    def test_save_stock_and_sort(self):
        save_stock('789', 'TICKC', 'Company C')
        sort_stocks(f'./{self.test_db_folder}/{STOCKS_FILE}')
        df = load_stocks(f'./{self.test_db_folder}/{STOCKS_FILE}')
        self.assertIn('789', df.index)
        self.assertEqual(df.loc['789', 'Ticker'], 'TICKC')


    def test_find_cusips_for_ticker(self):
        res = find_cusips_for_ticker('TICKA')
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['CUSIP'], '123')


    def test_update_ticker(self):
        # Update TICKA to TICKNEW
        update_ticker('TICKA', 'TICKNEW')
        
        # Check stocks.csv
        df_stocks = load_stocks(f'./{self.test_db_folder}/{STOCKS_FILE}')
        self.assertEqual(df_stocks.loc['123', 'Ticker'], 'TICKNEW')
        
        # Check quarterly filings
        df_q = load_fund_holdings('Fund A', '2025Q1')
        self.assertEqual(df_q.iloc[0]['Ticker'], 'TICKNEW')
        
        # Check non-quarterly
        df_nq = load_non_quarterly_data(f'./{self.test_db_folder}/{LATEST_SCHEDULE_FILINGS_FILE}')
        self.assertEqual(df_nq.iloc[0]['Ticker'], 'TICKNEW')


    def test_concurrent_save_stocks(self):
        num_threads = 10
        iterations = 20
        stocks_path = f'./{self.test_db_folder}/{STOCKS_FILE}'
        
        def worker(thread_idx):
            for i in range(iterations):
                cusip = f"C_{thread_idx}_{i}"
                ticker = f"T_{thread_idx}_{i}"
                company = f"Co_{thread_idx}_{i}"
                save_stock(cusip, ticker, company)
                
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        # Verify all records are present
        df = load_stocks(stocks_path)
        actual_count = len(df)
        # Initial 2 records + 200 new ones
        expected_count = 2 + (num_threads * iterations)
        self.assertEqual(actual_count, expected_count)


    def test_concurrent_save_and_sort(self):
        stocks_path = f'./{self.test_db_folder}/{STOCKS_FILE}'
        # One thread keeps saving, another keeps sorting
        stop_event = threading.Event()
        
        def saver():
            i = 0
            while not stop_event.is_set():
                save_stock(f"S_{i}", f"T_{i}", "Co")
                i += 1
                time.sleep(0.01)
                
        def sorter():
            while not stop_event.is_set():
                try:
                    sort_stocks(stocks_path)
                except Exception as e:
                    pass
                time.sleep(0.02)
                
        t1 = threading.Thread(target=saver)
        t2 = threading.Thread(target=sorter)
        
        t1.start()
        t2.start()
        
        time.sleep(1) # Run for 1 second is enough for this combined test
        stop_event.set()
        
        t1.join()
        t2.join()
        
        # Verify it didn't crash
        df = load_stocks(stocks_path)
        self.assertTrue(len(df) > 0)


    def test_delete_fund_from_database(self):
        fund_info = {'Fund': 'Fund B', 'CIK': '002'}
        # Create Fund B in hedge_funds.csv first
        with open(os.path.join(self.test_db_folder, HEDGE_FUNDS_FILE), 'a', newline='') as f:
            f.write("002,Fund B,Manager B,Denom B,\n")
            
        delete_fund_from_database(fund_info, "http://example.com")
        
        # Check file deleted
        self.assertFalse(os.path.exists(os.path.join(self.test_db_folder, '2025Q1', 'Fund_B.csv')))
        
        # Check removed from hedge_funds.csv
        funds = load_hedge_funds()
        self.assertTrue(all(f['Fund'] != 'Fund B' for f in funds))
        
        # Check added to excluded_hedge_funds.csv
        excluded_path = os.path.join(self.test_db_folder, 'excluded_hedge_funds.csv')
        self.assertTrue(os.path.exists(excluded_path))
        df_ex = pd.read_csv(excluded_path)
        self.assertIn('Fund B', df_ex['Fund'].values)
        self.assertIn('http://example.com', df_ex['URL'].values)


    def tearDown(self):
        """
        Clean up the temporary database directory.
        This runs after each test.
        """
        # Retry logic to handle Windows file locking issues
        for _ in range(5):
            try:
                shutil.rmtree(self.test_db_folder)
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            shutil.rmtree(self.test_db_folder)
        self.patcher.stop()


if __name__ == '__main__':
    unittest.main()
