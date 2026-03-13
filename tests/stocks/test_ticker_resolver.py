import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from app.stocks.ticker_resolver import TickerResolver


def _empty_stocks():
    """
    Returns an empty stocks DataFrame with the correct CUSIP index structure.
    """
    df = pd.DataFrame(columns=['Ticker', 'Company'])
    df.index.name = 'CUSIP'
    return df


def _cached_stocks(cusip, ticker, company):
    """
    Returns a single-row stocks DataFrame simulating a cached CUSIP entry.
    """
    df = pd.DataFrame({'Ticker': [ticker], 'Company': [company]}, index=[cusip])
    df.index.name = 'CUSIP'
    return df


class TestTickerResolverGetLibraries(unittest.TestCase):

    def test_get_libraries_returns_four_libraries(self):
        """
        Returns exactly four libraries in the resolution fallback chain.
        """
        libraries = TickerResolver.get_libraries()

        self.assertEqual(len(libraries), 4)

    def test_get_libraries_priority_order(self):
        """
        Returns libraries in priority order: YFinance → Finnhub → FinanceDatabase → TradingView.
        """
        libraries = TickerResolver.get_libraries()

        self.assertEqual(libraries[0].__name__, 'YFinance')
        self.assertEqual(libraries[1].__name__, 'Finnhub')
        self.assertEqual(libraries[2].__name__, 'FinanceDatabase')
        self.assertEqual(libraries[3].__name__, 'TradingView')


class TestTickerResolverResolveTicker(unittest.TestCase):

    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_uses_cached_ticker_when_cusip_in_database(self, mock_load):
        """
        Uses the locally cached ticker without calling any library when the CUSIP is already known.
        """
        mock_load.return_value = _cached_stocks('037833100', 'AAPL', 'Apple Inc')
        df = pd.DataFrame({'CUSIP': ['037833100'], 'Company': ['Apple Inc']})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, 'Ticker'], 'AAPL')

    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.YFinance.get_company')
    @patch('app.stocks.ticker_resolver.YFinance.get_ticker')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_resolves_via_first_library_when_cusip_unknown(self, mock_load, mock_get_ticker, mock_get_company, mock_save):
        """
        Resolves CUSIP and company via YFinance and saves result to the local database.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_ticker.return_value = 'AAPL'
        mock_get_company.return_value = 'Apple Inc'
        df = pd.DataFrame({'CUSIP': ['037833100'], 'Company': ['Apple Inc']})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, 'Ticker'], 'AAPL')
        self.assertEqual(result.loc[0, 'Company'], 'Apple Inc')
        mock_save.assert_called_once()

    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.Finnhub.get_company')
    @patch('app.stocks.ticker_resolver.Finnhub.get_ticker')
    @patch('app.stocks.ticker_resolver.YFinance.get_ticker')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_falls_back_to_second_library_when_first_returns_none(self, mock_load, mock_yf_ticker, mock_fh_ticker, mock_fh_company, mock_save):
        """
        Falls back to Finnhub when YFinance cannot resolve the CUSIP.
        """
        mock_load.return_value = _empty_stocks()
        mock_yf_ticker.return_value = None
        mock_fh_ticker.return_value = 'AAPL'
        mock_fh_company.return_value = 'Apple Inc'
        df = pd.DataFrame({'CUSIP': ['037833100'], 'Company': ['Apple Inc']})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, 'Ticker'], 'AAPL')
        mock_save.assert_called_once()

    @patch('app.stocks.ticker_resolver.open_issue')
    @patch('app.stocks.ticker_resolver.TradingView.get_ticker')
    @patch('app.stocks.ticker_resolver.FinanceDatabase.get_ticker')
    @patch('app.stocks.ticker_resolver.Finnhub.get_ticker')
    @patch('app.stocks.ticker_resolver.YFinance.get_ticker')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_opens_github_issue_when_no_library_resolves_ticker(self, mock_load, mock_yf, mock_fh, mock_fd, mock_tv, mock_issue):
        """
        Opens a GitHub issue when all libraries fail to resolve the CUSIP to a ticker.
        """
        mock_load.return_value = _empty_stocks()
        mock_yf.return_value = None
        mock_fh.return_value = None
        mock_fd.return_value = None
        mock_tv.return_value = None
        df = pd.DataFrame({'CUSIP': ['999999999'], 'Company': ['Unknown Corp']})

        TickerResolver.resolve_ticker(df)

        mock_issue.assert_called_once()
        subject = mock_issue.call_args[0][0]
        self.assertIn('Ticker not found', subject)

    @patch('app.stocks.ticker_resolver.open_issue')
    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.TradingView.get_company')
    @patch('app.stocks.ticker_resolver.FinanceDatabase.get_company')
    @patch('app.stocks.ticker_resolver.Finnhub.get_company')
    @patch('app.stocks.ticker_resolver.YFinance.get_company')
    @patch('app.stocks.ticker_resolver.YFinance.get_ticker')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_opens_github_issue_when_company_not_found_and_original_is_empty(self, mock_load, mock_ticker, mock_yf_co, mock_fh_co, mock_fd_co, mock_tv_co, mock_save, mock_issue):
        """
        Opens a GitHub issue when ticker is found but no library can resolve the company name
        and the original company field in the DataFrame is also empty.
        """
        mock_load.return_value = _empty_stocks()
        mock_ticker.return_value = 'AAPL'
        mock_yf_co.return_value = None
        mock_fh_co.return_value = None
        mock_fd_co.return_value = None
        mock_tv_co.return_value = None
        df = pd.DataFrame({'CUSIP': ['037833100'], 'Company': ['']})

        TickerResolver.resolve_ticker(df)

        mock_issue.assert_called_once()
        subject = mock_issue.call_args[0][0]
        self.assertIn('Company not found', subject)

    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_fills_empty_company_from_database(self, mock_load):
        """
        Fills an empty company field in the input DataFrame from the cached database value.
        """
        mock_load.return_value = _cached_stocks('037833100', 'AAPL', 'Apple Inc')
        df = pd.DataFrame({'CUSIP': ['037833100'], 'Company': [''], 'Ticker': ['AAPL']})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, 'Company'], 'Apple Inc')

    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.YFinance.get_company')
    @patch('app.stocks.ticker_resolver.YFinance.get_ticker')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_resolves_multiple_cusips_independently(self, mock_load, mock_ticker, mock_company, mock_save):
        """
        Resolves each row in the DataFrame independently, saving each resolved ticker.
        """
        mock_load.return_value = _empty_stocks()
        mock_ticker.side_effect = ['AAPL', 'JNJ']
        mock_company.side_effect = ['Apple Inc', 'Johnson & Johnson']
        df = pd.DataFrame({
            'CUSIP': ['037833100', '478160104'],
            'Company': ['Apple Inc', 'Johnson & Johnson']
        })

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, 'Ticker'], 'AAPL')
        self.assertEqual(result.loc[1, 'Ticker'], 'JNJ')
        self.assertEqual(mock_save.call_count, 2)

    @patch('app.stocks.ticker_resolver.open_issue')
    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.TradingView.get_company')
    @patch('app.stocks.ticker_resolver.FinanceDatabase.get_company')
    @patch('app.stocks.ticker_resolver.Finnhub.get_company')
    @patch('app.stocks.ticker_resolver.YFinance.get_company')
    @patch('app.stocks.ticker_resolver.YFinance.get_ticker')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_uses_original_company_name_when_libraries_return_none(self, mock_load, mock_ticker, mock_yf_co, mock_fh_co, mock_fd_co, mock_tv_co, mock_save, mock_issue):
        """
        Falls back to the original company name from the input DataFrame when all libraries
        fail to return a company name (avoids opening a false issue if the name is already known).
        """
        mock_load.return_value = _empty_stocks()
        mock_ticker.return_value = 'AAPL'
        mock_yf_co.return_value = None
        mock_fh_co.return_value = None
        mock_fd_co.return_value = None
        mock_tv_co.return_value = None
        df = pd.DataFrame({'CUSIP': ['037833100'], 'Company': ['Apple Inc']})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, 'Company'], 'Apple Inc')
        mock_issue.assert_not_called()


class TestTickerResolverAssignCUSIP(unittest.TestCase):

    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_maps_known_ticker_to_cusip_from_cache(self, mock_load):
        """
        Returns the cached CUSIP for a ticker already present in the local database.
        """
        mock_load.return_value = _cached_stocks('037833100', 'AAPL', 'Apple Inc')
        df = pd.DataFrame({'Ticker': ['AAPL'], 'Company': ['Apple Inc']})

        result = TickerResolver.assign_cusip(df)

        self.assertEqual(result.loc[0, 'CUSIP'], '037833100')

    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.FinanceDatabase.get_cusip')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_fetches_and_saves_cusip_for_new_ticker(self, mock_load, mock_get_cusip, mock_save):
        """
        Queries FinanceDatabase and saves the result for tickers not found in the local database.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_cusip.return_value = '037833100'
        df = pd.DataFrame({'Ticker': ['AAPL'], 'Company': ['Apple Inc']})

        result = TickerResolver.assign_cusip(df)

        self.assertEqual(result.loc[0, 'CUSIP'], '037833100')
        mock_save.assert_called_once()

    @patch('app.stocks.ticker_resolver.FinanceDatabase.get_cusip')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_leaves_cusip_null_when_fetch_raises(self, mock_load, mock_get_cusip):
        """
        Leaves the CUSIP as NaN when FinanceDatabase raises an exception for the ticker.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_cusip.side_effect = Exception("API error")
        df = pd.DataFrame({'Ticker': ['AAPL'], 'Company': ['Apple Inc']})

        result = TickerResolver.assign_cusip(df)

        self.assertTrue(pd.isna(result.loc[0, 'CUSIP']))

    @patch('app.stocks.ticker_resolver.save_stock')
    @patch('app.stocks.ticker_resolver.FinanceDatabase.get_cusip')
    @patch('app.stocks.ticker_resolver.load_stocks')
    def test_handles_mixed_cached_and_new_tickers(self, mock_load, mock_get_cusip, mock_save):
        """
        Handles a DataFrame where some tickers are cached and others require a remote fetch.
        """
        mock_load.return_value = _cached_stocks('037833100', 'AAPL', 'Apple Inc')
        mock_get_cusip.return_value = '594918104'
        df = pd.DataFrame({
            'Ticker': ['AAPL', 'JNJ'],
            'Company': ['Apple Inc', 'Johnson & Johnson']
        })

        result = TickerResolver.assign_cusip(df)

        self.assertEqual(result.loc[0, 'CUSIP'], '037833100')
        self.assertEqual(result.loc[1, 'CUSIP'], '594918104')


if __name__ == '__main__':
    unittest.main()
