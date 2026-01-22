from app.stocks.libraries.yfinance import YFinance
from datetime import date
import unittest
from unittest.mock import MagicMock, patch


class TestYFinance(unittest.TestCase):
    def test_get_ticker(self):
        """
        Tests the get_ticker method for known CUSIPs.
        """
        # Test for a known CUSIP (Apple)
        aapl_ticker = YFinance.get_ticker('037833100')
        self.assertEqual(aapl_ticker, 'AAPL')


    def test_get_company(self):
        """
        Tests the get_company method for known tickers.
        """
        # Test for a known ticker (Apple)
        aapl_company = YFinance.get_company('037833100', ticker='AAPL')
        self.assertIsNotNone(aapl_company)
        self.assertIn('Apple', aapl_company)


    def test_get_current_price(self):
        """
        Tests the get_current_price method for a known ticker.
        """
        # Test for a known ticker (Apple)
        aapl_price = YFinance.get_current_price('AAPL')
        self.assertIsNotNone(aapl_price)
        self.assertIsInstance(aapl_price, float)
        self.assertGreater(aapl_price, 0)


    def test_get_avg_price(self):
        """
        Tests the get_avg_price method for a known ticker and date.
        """
        # Test for a known ticker (Apple) on a specific date
        test_date = date(2024, 1, 15)
        aapl_price = YFinance.get_avg_price('AAPL', test_date)
        self.assertIsNotNone(aapl_price)
        self.assertIsInstance(aapl_price, float)
        self.assertGreater(aapl_price, 0)


    def test_get_stocks_info(self):
        """
        Tests the get_stocks_info method for multiple tickers.
        """
        # Test for known tickers
        tickers = ['AAPL', 'MSFT', 'GOOGL']
        stocks_info = YFinance.get_stocks_info(tickers)
        
        self.assertIsNotNone(stocks_info)
        self.assertIsInstance(stocks_info, dict)
        self.assertGreater(len(stocks_info), 0)
        
        # Check structure for at least one ticker
        if 'AAPL' in stocks_info:
            self.assertIn('price', stocks_info['AAPL'])
            self.assertIn('sector', stocks_info['AAPL'])
            self.assertIsInstance(stocks_info['AAPL']['price'], float)
            self.assertGreater(stocks_info['AAPL']['price'], 0)


    def test_get_stocks_info_empty_list(self):
        """
        Tests the get_stocks_info method with an empty list.
        """
        stocks_info = YFinance.get_stocks_info([])
        self.assertEqual(stocks_info, {})


    def test_get_sector_tickers(self):
        """
        Tests the get_sector_tickers method for a valid sector.
        """
        # Test for technology sector
        tech_companies = YFinance.get_sector_tickers('technology', limit=10)
        
        self.assertIsNotNone(tech_companies)
        self.assertIsInstance(tech_companies, list)
        self.assertGreater(len(tech_companies), 0)
        self.assertLessEqual(len(tech_companies), 10)
        
        # Check structure of first company
        if len(tech_companies) > 0:
            company = tech_companies[0]
            self.assertIn('symbol', company)
            self.assertIn('name', company)
            self.assertIsInstance(company['symbol'], str)
            self.assertIsInstance(company['name'], str)


    def test_get_sector_tickers_invalid_sector(self):
        """
        Tests the get_sector_tickers method with an invalid sector.
        """
        # Test with an invalid sector key
        companies = YFinance.get_sector_tickers('invalid-sector-key')
        self.assertIsInstance(companies, list)
        # Should return empty list for invalid sector
        self.assertEqual(len(companies), 0)


    def test_get_sector_tickers_all_sectors(self):
        """
        Tests the get_sector_tickers method for all sectors derived from hierarchy.csv.
        Verifies that each sector returns at least some companies from yfinance.
        """
        from app.utils.gics import load_yf_sectors
        
        sectors_df = load_yf_sectors()        
        failed_sectors = []
        
        for _, row in sectors_df.iterrows():
            sector_key = row['Key']
            sector_name = row['Name']
            
            companies = YFinance.get_sector_tickers(sector_key, limit=3)
            
            if len(companies) == 0:
                failed_sectors.append(f"{sector_name} ({sector_key})")
        
        self.assertEqual(len(failed_sectors), 0, f"The following sectors returned no companies from yfinance: {', '.join(failed_sectors)}")


if __name__ == '__main__':
    unittest.main()
