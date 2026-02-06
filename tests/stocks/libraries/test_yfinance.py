from app.stocks.libraries.yfinance import YFinance
from datetime import date
from unittest.mock import patch, MagicMock
import pandas as pd
import unittest


class TestYFinance(unittest.TestCase):

    @patch('app.stocks.libraries.yfinance.requests.get')
    def test_get_ticker(self, mock_get):
        """
        Tests the get_ticker method using mocks.
        """
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'quotes': [{'symbol': 'AAPL'}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        ticker = YFinance.get_ticker('037833100')
        self.assertEqual(ticker, 'AAPL')
        mock_get.assert_called_once_with(
            "https://query1.finance.yahoo.com/v1/finance/search?q=037833100",
            headers={'User-Agent': 'Mozilla/5.0'}
        )


    @patch('app.stocks.libraries.yfinance.yf.Ticker')
    @patch('app.stocks.libraries.yfinance.YFinance.get_ticker')
    def test_get_company(self, mock_get_ticker, mock_yf_ticker):
        """
        Tests the get_company method using mocks.
        """
        # Mock yf.Ticker object
        mock_instance = MagicMock()
        mock_instance.info = {'longName': 'Apple Inc.'}
        mock_yf_ticker.return_value = mock_instance

        # Test with ticker provided
        company = YFinance.get_company('037833100', ticker='AAPL')
        self.assertEqual(company, 'Apple Inc')
        mock_yf_ticker.assert_called_with('AAPL')

        # Test with ticker not provided (should call get_ticker)
        mock_get_ticker.return_value = 'MSFT'
        mock_instance.info = {'shortName': 'Microsoft'}
        company = YFinance.get_company('some_cusip')
        self.assertEqual(company, 'Microsoft')
        mock_get_ticker.assert_called_with('some_cusip')
        mock_yf_ticker.assert_called_with('MSFT')


    @patch('app.stocks.libraries.yfinance.yf.Ticker')
    def test_get_current_price(self, mock_yf_ticker):
        """
        Tests the get_current_price method using mocks.
        """
        mock_instance = MagicMock()
        mock_instance.info = {'currentPrice': 150.0}
        mock_yf_ticker.return_value = mock_instance

        price = YFinance.get_current_price('AAPL')
        self.assertEqual(price, 150.0)
        mock_yf_ticker.assert_called_once_with('AAPL')


    @patch('app.stocks.libraries.yfinance.yf.download')
    @patch('app.stocks.libraries.yfinance.YFinance.get_current_price')
    def test_get_avg_price(self, mock_get_current, mock_download):
        """
        Tests the get_avg_price method using mocks.
        """
        # Mock successful download
        df = pd.DataFrame({'High': [110.0], 'Low': [90.0]}, index=[pd.Timestamp('2024-01-15')])
        mock_download.return_value = df

        test_date = date(2024, 1, 15)
        price = YFinance.get_avg_price('AAPL', test_date)
        self.assertEqual(price, 100.0)  # (110 + 90) / 2
        mock_download.assert_called_once()

        # Mock empty download (fallback to current price)
        mock_download.return_value = pd.DataFrame()
        mock_get_current.return_value = 155.0
        price = YFinance.get_avg_price('AAPL', test_date)
        self.assertEqual(price, 155.0)
        mock_get_current.assert_called_once_with('AAPL')


    @patch('app.stocks.libraries.yfinance.yf.download')
    @patch('app.stocks.libraries.yfinance.yf.Ticker')
    def test_get_stocks_info(self, mock_yf_ticker, mock_download):
        """
        Tests the get_stocks_info method using mocks.
        """
        # Mock download results
        # For multiple tickers, yfinance returns columns like ('AAPL', 'Close')
        columns = pd.MultiIndex.from_tuples([('AAPL', 'Close'), ('MSFT', 'Close')])
        df = pd.DataFrame([[150.0, 300.0]], columns=columns)
        mock_download.return_value = df

        # Mock individual Ticker info calls for sectors
        mock_aapl = MagicMock()
        mock_aapl.info = {'sector': 'Technology'}
        mock_msft = MagicMock()
        mock_msft.info = {'industry': 'Software'}
        
        def ticker_side_effect(symbol):
            if symbol == 'AAPL': return mock_aapl
            if symbol == 'MSFT': return mock_msft
            return MagicMock()

        mock_yf_ticker.side_effect = ticker_side_effect

        tickers = ['AAPL', 'MSFT']
        stocks_info = YFinance.get_stocks_info(tickers)

        self.assertEqual(stocks_info['AAPL']['price'], 150.0)
        self.assertEqual(stocks_info['AAPL']['sector'], 'Technology')
        self.assertEqual(stocks_info['MSFT']['price'], 300.0)
        self.assertEqual(stocks_info['MSFT']['sector'], 'Software')


    def test_get_stocks_info_empty_list(self):
        """
        Tests the get_stocks_info method with an empty list.
        """
        stocks_info = YFinance.get_stocks_info([])
        self.assertEqual(stocks_info, {})


    @patch('app.stocks.libraries.yfinance.yf.Sector')
    def test_get_sector_tickers(self, mock_yf_sector):
        """
        Tests the get_sector_tickers method using mocks.
        """
        mock_sector_instance = MagicMock()
        mock_sector_instance.top_companies = pd.DataFrame([
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'weight': 0.1},
            {'symbol': 'MSFT', 'name': 'Microsoft Corp.', 'weight': 0.08}
        ])
        mock_yf_sector.return_value = mock_sector_instance

        companies = YFinance.get_sector_tickers('technology', limit=1)
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]['symbol'], 'AAPL')


    @patch('app.stocks.libraries.yfinance.yf.Sector')
    def test_get_sector_tickers_invalid_sector(self, mock_yf_sector):
        """
        Tests the get_sector_tickers method with retry logic on failure.
        """
        mock_yf_sector.return_value.top_companies = None
        
        from tenacity import RetryError
        with self.assertRaises(RetryError):
            YFinance.get_sector_tickers('invalid-sector-key')


    @patch('app.stocks.libraries.yfinance.yf.Ticker')
    @patch('app.stocks.libraries.yfinance.yf.download')
    def test_ticker_sanitization(self, mock_download, mock_yf_ticker):
        """
        Tests that tickers with dots are correctly sanitized to dashes
        when passed to yfinance library.
        """
        # Test current price: BRK.B -> BRK-B
        mock_instance = MagicMock()
        mock_instance.info = {'currentPrice': 500.0}
        mock_yf_ticker.return_value = mock_instance

        YFinance.get_current_price('BRK.B')
        mock_yf_ticker.assert_called_with('BRK-B')

        # Test avg price: BRK.B -> BRK-B
        df = pd.DataFrame({'High': [510.0], 'Low': [490.0]}, index=[pd.Timestamp('2024-01-15')])
        mock_download.return_value = df
        YFinance.get_avg_price('BRK.B', date(2024, 1, 15))
        # download is called with tickers='BRK-B'
        args, kwargs = mock_download.call_args
        self.assertEqual(kwargs['tickers'], 'BRK-B')

        # Test get_stocks_info mapping
        columns = pd.MultiIndex.from_tuples([('BRK-B', 'Close'), ('AAPL', 'Close')])
        df_multi = pd.DataFrame([[500.0, 200.0]], columns=columns)
        mock_download.return_value = df_multi
        
        # Reset mocks for sector calls
        mock_yf_ticker.reset_mock()
        mock_yf_ticker.return_value.info = {'sector': 'Finance'}

        info = YFinance.get_stocks_info(['BRK.B', 'AAPL'])
        
        # Verify result keys are original
        self.assertIn('BRK.B', info)
        self.assertIn('AAPL', info)
        # Verify internal calls used sanitized
        mock_yf_ticker.assert_any_call('BRK-B')


if __name__ == '__main__':
    unittest.main()
