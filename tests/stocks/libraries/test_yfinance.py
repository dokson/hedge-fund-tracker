import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

from app.stocks.libraries.yfinance import YFinance


class TestYFinance(unittest.TestCase):
    @patch("app.stocks.libraries.yfinance.requests.get")
    def test_get_ticker(self, mock_get):
        """
        Tests the get_ticker method using mocks.
        """
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {"quotes": [{"symbol": "AAPL"}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        ticker = YFinance.get_ticker("037833100")
        self.assertEqual(ticker, "AAPL")
        mock_get.assert_called_once_with(
            "https://query1.finance.yahoo.com/v1/finance/search?q=037833100",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    @patch("app.stocks.libraries.yfinance.YFinance.get_ticker")
    def test_get_company(self, mock_get_ticker, mock_yf_ticker):
        """
        Tests the get_company method using mocks.
        """
        # Mock yf.Ticker object
        mock_instance = MagicMock()
        mock_instance.info = {"longName": "Apple Inc."}
        mock_yf_ticker.return_value = mock_instance

        # Test with ticker provided
        company = YFinance.get_company("037833100", ticker="AAPL")
        self.assertEqual(company, "Apple Inc")
        mock_yf_ticker.assert_called_with("AAPL")

        # Test with ticker not provided (should call get_ticker)
        mock_get_ticker.return_value = "MSFT"
        mock_instance.info = {"shortName": "Microsoft"}
        company = YFinance.get_company("some_cusip")
        self.assertEqual(company, "Microsoft")
        mock_get_ticker.assert_called_with("some_cusip")
        mock_yf_ticker.assert_called_with("MSFT")

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    @patch("app.stocks.libraries.yfinance.YFinance.get_ticker")
    def test_get_company_returns_none_when_ticker_cannot_be_resolved(
        self, mock_get_ticker, mock_yf_ticker
    ):
        """
        Returns None (without invoking yf.Ticker) when no ticker is provided and
        get_ticker cannot resolve the CUSIP. Previously this path crashed with
        AttributeError: 'NoneType' object has no attribute 'upper' inside yfinance.
        """
        mock_get_ticker.return_value = None

        company = YFinance.get_company("unknown_cusip")

        self.assertIsNone(company)
        mock_yf_ticker.assert_not_called()

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_classification_returns_sector_and_industry(self, mock_yf_ticker):
        """
        Returns a dict {sector, industry} built from yf.Ticker(ticker).info.
        """
        mock_instance = MagicMock()
        mock_instance.info = {"sector": "Technology", "industry": "Consumer Electronics"}
        mock_yf_ticker.return_value = mock_instance

        classification = YFinance.get_classification("AAPL")

        self.assertEqual(
            classification,
            {"sector": "Technology", "industry": "Consumer Electronics"},
        )
        mock_yf_ticker.assert_called_with("AAPL")

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_classification_sanitizes_share_class_ticker(self, mock_yf_ticker):
        """
        Replaces the dot in share-class tickers (BRK.B -> BRK-B) before querying
        yfinance, matching the convention used elsewhere in this client.
        """
        mock_instance = MagicMock()
        mock_instance.info = {"sector": "Financial Services", "industry": "Insurance—Diversified"}
        mock_yf_ticker.return_value = mock_instance

        YFinance.get_classification("BRK.B")

        mock_yf_ticker.assert_called_with("BRK-B")

    def test_get_classification_returns_none_for_empty_ticker(self):
        """
        Returns None without invoking yf.Ticker when the input is empty or None.
        """
        self.assertIsNone(YFinance.get_classification(""))
        self.assertIsNone(YFinance.get_classification(None))  # type: ignore[arg-type]

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_classification_returns_none_when_both_fields_missing(self, mock_yf_ticker):
        """
        Returns None when the info payload exposes neither sector nor industry and
        the ticker is not an ETF — avoids writing empty-string placeholders into
        stocks.csv.
        """
        mock_instance = MagicMock()
        mock_instance.info = {"quoteType": "EQUITY"}
        mock_yf_ticker.return_value = mock_instance

        self.assertIsNone(YFinance.get_classification("ZZZZ"))

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_classification_buckets_etfs_into_synthetic_etf_category(self, mock_yf_ticker):
        """
        ETFs do not carry a sector classification in Yahoo's data (no sector/industry
        fields), so we group them under a synthetic 'ETF' category for both
        sector and industry. Detected via quoteType == 'ETF'.
        """
        mock_instance = MagicMock()
        mock_instance.info = {"quoteType": "ETF", "longName": "SPDR S&P 500 ETF Trust"}
        mock_yf_ticker.return_value = mock_instance

        self.assertEqual(
            YFinance.get_classification("SPY"),
            {"sector": "ETF", "industry": "ETF"},
        )

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_classification_partial_fields(self, mock_yf_ticker):
        """
        When only one of {sector, industry} is present, returns a dict where the
        missing field is None and the present one is the original string.
        """
        mock_instance = MagicMock()
        mock_instance.info = {"sector": "Energy"}
        mock_yf_ticker.return_value = mock_instance

        self.assertEqual(
            YFinance.get_classification("XOM"),
            {"sector": "Energy", "industry": None},
        )

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_classification_returns_none_on_exception(self, mock_yf_ticker):
        """
        Returns None when yfinance raises (e.g. ticker not found, network error).
        """
        mock_yf_ticker.side_effect = Exception("Yahoo unreachable")

        self.assertIsNone(YFinance.get_classification("AAPL"))

    @patch("app.stocks.libraries.yfinance.requests.get")
    def test_get_ticker_returns_none_when_quote_symbol_is_empty(self, mock_get):
        """
        Returns None when the Yahoo search response includes a quote whose
        'symbol' field is empty or missing — previously such quotes leaked an
        empty string into stocks.csv.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {"quotes": [{"symbol": ""}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        ticker = YFinance.get_ticker("037833100")

        self.assertIsNone(ticker)

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_current_price(self, mock_yf_ticker):
        """
        Tests the get_current_price method using mocks.
        """
        mock_instance = MagicMock()
        mock_instance.info = {"currentPrice": 150.0}
        mock_yf_ticker.return_value = mock_instance

        price = YFinance.get_current_price("AAPL")
        self.assertEqual(price, 150.0)
        mock_yf_ticker.assert_called_once_with("AAPL")

    @patch("app.stocks.libraries.yfinance.yf.download")
    @patch("app.stocks.libraries.yfinance.YFinance.get_current_price")
    def test_get_avg_price(self, mock_get_current, mock_download):
        """
        Tests the get_avg_price method using mocks.
        """
        # Mock successful download
        df = pd.DataFrame({"High": [110.0], "Low": [90.0]}, index=[pd.Timestamp("2024-01-15")])
        mock_download.return_value = df

        test_date = date(2024, 1, 15)
        price = YFinance.get_avg_price("AAPL", test_date)
        self.assertEqual(price, 100.0)  # (110 + 90) / 2
        mock_download.assert_called_once()

        # When no historical data exists in the window, the price must not be
        # silently substituted with today's current price (that made the stored
        # value drift between runs); it returns None so the fallback chain continues.
        mock_download.return_value = pd.DataFrame()
        price = YFinance.get_avg_price("AAPL", test_date)
        self.assertIsNone(price)
        mock_get_current.assert_not_called()

    @patch("app.stocks.libraries.yfinance.yf.download")
    @patch("app.stocks.libraries.yfinance.YFinance.get_current_price")
    def test_get_avg_price_uses_last_trading_day_for_non_trading_date(
        self, mock_get_current, mock_download
    ):
        """
        For a non-trading date (weekend/holiday), returns the price of the most
        recent trading day at or before that date, never today's current price.
        """
        # Requested date is a Sunday; the window returns bars up to the prior Friday.
        df = pd.DataFrame(
            {"High": [110.0, 120.0], "Low": [90.0, 100.0]},
            index=[pd.Timestamp("2024-01-11"), pd.Timestamp("2024-01-12")],
        )
        mock_download.return_value = df

        sunday = date(2024, 1, 14)
        price = YFinance.get_avg_price("AAPL", sunday)

        self.assertEqual(price, 110.0)  # (120 + 100) / 2 from the last (Friday) bar
        mock_get_current.assert_not_called()

        # The download window must look back before the requested date.
        _, kwargs = mock_download.call_args
        self.assertLess(kwargs["start"], sunday)
        self.assertEqual(kwargs["end"], sunday + timedelta(days=1))

    @patch("app.stocks.libraries.yfinance.yf.download")
    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_stocks_info(self, mock_yf_ticker, mock_download):
        """
        Tests the get_stocks_info method using mocks.
        """
        # Mock download results
        # For multiple tickers, yfinance returns columns like ('AAPL', 'Close')
        columns = pd.MultiIndex.from_tuples([("AAPL", "Close"), ("MSFT", "Close")])
        df = pd.DataFrame([[150.0, 300.0]], columns=columns)
        mock_download.return_value = df

        # Mock individual Ticker info calls for sectors
        mock_aapl = MagicMock()
        mock_aapl.info = {"sector": "Technology"}
        mock_msft = MagicMock()
        mock_msft.info = {"industry": "Software"}

        def ticker_side_effect(symbol):
            if symbol == "AAPL":
                return mock_aapl
            if symbol == "MSFT":
                return mock_msft
            return MagicMock()

        mock_yf_ticker.side_effect = ticker_side_effect

        tickers = ["AAPL", "MSFT"]
        stocks_info = YFinance.get_stocks_info(tickers)

        self.assertEqual(stocks_info["AAPL"]["price"], 150.0)
        self.assertEqual(stocks_info["AAPL"]["sector"], "Technology")
        self.assertEqual(stocks_info["MSFT"]["price"], 300.0)
        self.assertEqual(stocks_info["MSFT"]["sector"], "Software")

    def test_get_stocks_info_empty_list(self):
        """
        Tests the get_stocks_info method with an empty list.
        """
        stocks_info = YFinance.get_stocks_info([])
        self.assertEqual(stocks_info, {})

    @patch("app.stocks.libraries.yfinance.yf.download")
    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_stocks_info_rate_limit_propagates_for_backoff(self, mock_ticker, mock_download):
        """
        A rate-limit error must escape the per-ticker loop so the outer retry
        backs off, instead of silently recording every remaining ticker as a
        data gap. (__wrapped__ bypasses the tenacity decorator for speed.)
        """
        from yfinance.exceptions import YFRateLimitError

        mock_download.return_value = pd.DataFrame({"Close": [10.0]})
        mock_ticker.side_effect = YFRateLimitError()

        with self.assertRaises(YFRateLimitError):
            YFinance.get_stocks_info.__wrapped__(["AAA"])

    @patch("app.stocks.libraries.yfinance.yf.download")
    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    def test_get_stocks_info_per_ticker_error_keeps_partial_results(
        self, mock_ticker, mock_download
    ):
        """
        A non-rate-limit failure on one ticker's info lookup must not lose the
        prices already fetched for the batch.
        """
        mock_download.return_value = pd.DataFrame({"Close": [10.0]})
        mock_ticker.side_effect = ValueError("bad payload")

        stocks_info = YFinance.get_stocks_info.__wrapped__(["AAA"])

        self.assertEqual(stocks_info, {"AAA": {"price": 10.0, "sector": None}})

    @patch("app.stocks.libraries.yfinance.yf.Sector")
    def test_get_sector_tickers(self, mock_yf_sector):
        """
        Tests the get_sector_tickers method using mocks.
        """
        mock_sector_instance = MagicMock()
        mock_sector_instance.top_companies = pd.DataFrame(
            [
                {"symbol": "AAPL", "name": "Apple Inc.", "weight": 0.1},
                {"symbol": "MSFT", "name": "Microsoft Corp.", "weight": 0.08},
            ]
        )
        mock_yf_sector.return_value = mock_sector_instance

        companies = YFinance.get_sector_tickers("technology", limit=1)
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["symbol"], "AAPL")

    @patch("app.stocks.libraries.yfinance.yf.Sector")
    def test_get_sector_tickers_invalid_sector(self, mock_yf_sector):
        """
        Tests the get_sector_tickers method with retry logic on failure.
        """
        mock_yf_sector.return_value.top_companies = None

        from tenacity import RetryError

        with self.assertRaises(RetryError):
            YFinance.get_sector_tickers("invalid-sector-key")

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    @patch("app.stocks.libraries.yfinance.yf.download")
    def test_ticker_sanitization(self, mock_download, mock_yf_ticker):
        """
        Tests that tickers with dots are correctly sanitized to dashes
        when passed to yfinance library.
        """
        # Test current price: BRK.B -> BRK-B
        mock_instance = MagicMock()
        mock_instance.info = {"currentPrice": 500.0}
        mock_yf_ticker.return_value = mock_instance

        YFinance.get_current_price("BRK.B")
        mock_yf_ticker.assert_called_with("BRK-B")

        # Test avg price: BRK.B -> BRK-B
        df = pd.DataFrame({"High": [510.0], "Low": [490.0]}, index=[pd.Timestamp("2024-01-15")])
        mock_download.return_value = df
        YFinance.get_avg_price("BRK.B", date(2024, 1, 15))
        # download is called with tickers='BRK-B'
        args, kwargs = mock_download.call_args
        self.assertEqual(kwargs["tickers"], "BRK-B")

        # Test get_stocks_info mapping
        columns = pd.MultiIndex.from_tuples([("BRK-B", "Close"), ("AAPL", "Close")])
        df_multi = pd.DataFrame([[500.0, 200.0]], columns=columns)
        mock_download.return_value = df_multi

        # Reset mocks for sector calls
        mock_yf_ticker.reset_mock()
        mock_yf_ticker.return_value.info = {"sector": "Finance"}

        info = YFinance.get_stocks_info(["BRK.B", "AAPL"])

        # Verify result keys are original
        self.assertIn("BRK.B", info)
        self.assertIn("AAPL", info)
        # Verify internal calls used sanitized
        mock_yf_ticker.assert_any_call("BRK-B")

    @patch("app.stocks.libraries.yfinance.yf.Ticker")
    @patch("app.stocks.libraries.yfinance.yf.download")
    def test_fallback_recursion_prevention(self, mock_download, mock_yf_ticker):
        """
        Tests that international fallback logic stops after one level
        and doesn't recurse infinitely (e.g., SYMBOL-TO-TO-TO).
        """
        # Mock download to always return empty (triggering fallbacks)
        mock_download.return_value = pd.DataFrame()

        # Mock Ticker info to always return None
        mock_instance = MagicMock()
        mock_instance.info = {}
        mock_yf_ticker.return_value = mock_instance

        # This should try AAPL, then AAPL.TO, then AAPL.V, then stop.
        # It should NOT result in AAPL-TO-TO...
        result = YFinance.get_avg_price("AAPL", date(2024, 1, 15))
        self.assertIsNone(result)

        # Check that download wasn't called with a ridiculous number of suffixes
        # The longest call should be AAPL-TO or AAPL-V (after sanitization)
        for call in mock_download.call_args_list:
            tickers = call.kwargs.get("tickers", "")
            self.assertLessEqual(tickers.count("-TO"), 1)
            self.assertLessEqual(tickers.count("-V"), 1)


if __name__ == "__main__":
    unittest.main()
