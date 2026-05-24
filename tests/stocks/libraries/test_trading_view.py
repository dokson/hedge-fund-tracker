import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from app.stocks.libraries.trading_view import TradingView


def _make_hist_df(close=152.5, high=155.0, low=145.0, date_str="2023-12-25"):
    """
    Creates a minimal DataFrame mimicking tvDatafeed output.
    """
    return pd.DataFrame(
        {"close": [close], "high": [high], "low": [low]}, index=pd.to_datetime([date_str])
    )


class TestTradingViewGetCurrentPrice(unittest.TestCase):
    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_price_from_first_successful_exchange(self, mock_tv_class):
        """
        Returns the last close price from the first exchange that returns data.
        """
        mock_tv_class.return_value.get_hist.return_value = _make_hist_df(close=152.5)

        price = TradingView.get_current_price("AAPL")

        self.assertEqual(price, 152.5)
        self.assertIsInstance(price, float)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_falls_back_to_next_exchange_when_first_returns_none(self, mock_tv_class):
        """
        Tries subsequent exchanges when an earlier one returns None.
        """

        def get_hist_side_effect(symbol, exchange, interval, n_bars):
            """
            Returns None for the first exchange, data for subsequent ones.
            """
            if exchange == TradingView.EXCHANGES[0]:
                return None
            return _make_hist_df(close=149.99)

        mock_tv_class.return_value.get_hist.side_effect = get_hist_side_effect

        price = TradingView.get_current_price("AAPL")

        self.assertEqual(price, 149.99)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_falls_back_when_exchange_raises_exception(self, mock_tv_class):
        """
        Skips exchanges that raise an exception and tries the next one.
        """

        def get_hist_side_effect(symbol, exchange, interval, n_bars):
            """
            Raises for the first exchange, returns data for subsequent ones.
            """
            if exchange == TradingView.EXCHANGES[0]:
                raise Exception("Exchange unavailable")
            return _make_hist_df(close=149.99)

        mock_tv_class.return_value.get_hist.side_effect = get_hist_side_effect

        price = TradingView.get_current_price("AAPL")

        self.assertEqual(price, 149.99)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_none_when_all_exchanges_return_none(self, mock_tv_class):
        """
        Returns None when no exchange can provide data for the ticker.
        """
        mock_tv_class.return_value.get_hist.return_value = None

        price = TradingView.get_current_price("UNKNOWN")

        self.assertIsNone(price)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_none_when_all_exchanges_raise(self, mock_tv_class):
        """
        Returns None (not an exception) when every exchange raises.
        """
        mock_tv_class.return_value.get_hist.side_effect = Exception("Network error")

        price = TradingView.get_current_price("AAPL")

        self.assertIsNone(price)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_none_when_dataframe_is_empty(self, mock_tv_class):
        """
        Returns None when an exchange returns an empty DataFrame.
        """
        mock_tv_class.return_value.get_hist.return_value = pd.DataFrame()

        price = TradingView.get_current_price("AAPL")

        self.assertIsNone(price)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_uses_injected_tv_session_instead_of_creating_new(self, mock_tv_class):
        """
        Uses a tv_session passed via kwargs instead of instantiating a new TvDatafeed.
        """
        mock_session = MagicMock()
        mock_session.get_hist.return_value = _make_hist_df(close=150.0)

        TradingView.get_current_price("AAPL", tv_session=mock_session)

        mock_tv_class.assert_not_called()
        mock_session.get_hist.assert_called()


class TestTradingViewGetAvgPrice(unittest.TestCase):
    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_high_low_average_for_matching_date(self, mock_tv_class):
        """
        Returns (high + low) / 2 for the specific date when data is available.
        """
        hist_df = _make_hist_df(high=160.0, low=140.0, date_str="2023-12-25")
        mock_tv_class.return_value.get_hist.return_value = hist_df

        price = TradingView.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, 150.0)  # (160 + 140) / 2

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_none_when_date_not_in_data(self, mock_tv_class):
        """
        Returns None when the requested date is not present in the historical data.
        """
        # Data only for 2023-12-24, not the requested 2023-12-25
        hist_df = _make_hist_df(date_str="2023-12-24")
        mock_tv_class.return_value.get_hist.return_value = hist_df

        price = TradingView.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertIsNone(price)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_returns_none_when_no_exchange_returns_data(self, mock_tv_class):
        """
        Returns None when all exchanges fail to return historical data.
        """
        mock_tv_class.return_value.get_hist.return_value = None

        price = TradingView.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertIsNone(price)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_falls_back_to_next_exchange_when_first_returns_none(self, mock_tv_class):
        """
        Falls back to a subsequent exchange when the first returns None.
        """
        hist_df = _make_hist_df(high=160.0, low=140.0, date_str="2023-12-25")

        def get_hist_side_effect(symbol, exchange, interval, n_bars):
            """
            Returns None for the first exchange, data for subsequent ones.
            """
            if exchange == TradingView.EXCHANGES[0]:
                return None
            return hist_df

        mock_tv_class.return_value.get_hist.side_effect = get_hist_side_effect

        price = TradingView.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, 150.0)

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_rounds_result_to_two_decimal_places(self, mock_tv_class):
        """
        Returns the average price rounded to 2 decimal places.
        """
        hist_df = _make_hist_df(high=100.1, low=100.0, date_str="2023-12-25")
        mock_tv_class.return_value.get_hist.return_value = hist_df

        price = TradingView.get_avg_price("AAPL", date(2023, 12, 25))

        self.assertEqual(price, round((100.1 + 100.0) / 2, 2))

    @patch("app.stocks.libraries.trading_view.TvDatafeed")
    def test_uses_injected_tv_session_instead_of_creating_new(self, mock_tv_class):
        """
        Uses a tv_session passed via kwargs instead of instantiating a new TvDatafeed.
        """
        mock_session = MagicMock()
        hist_df = _make_hist_df(date_str="2023-12-25")
        mock_session.get_hist.return_value = hist_df

        TradingView.get_avg_price("AAPL", date(2023, 12, 25), tv_session=mock_session)

        mock_tv_class.assert_not_called()


def _symbol_search_response(symbols):
    """
    Builds a mock requests.Response for the TradingView symbol_search endpoint.
    """
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {"symbols": symbols}
    return resp


class TestTradingViewIdentifierLookup(unittest.TestCase):
    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_returns_first_us_exchange_match(self, mock_get):
        """
        Converts CUSIP to ISIN, calls symbol_search, returns the ticker of the first US-listed match.
        """
        mock_get.return_value = _symbol_search_response(
            [
                {
                    "symbol": "1AAPL",
                    "description": "Apple Inc.",
                    "exchange": "MIL",
                    "type": "stock",
                },
                {
                    "symbol": "AAPL",
                    "description": "Apple Inc.",
                    "exchange": "NASDAQ",
                    "type": "stock",
                },
            ]
        )

        ticker = TradingView.get_ticker("037833100")

        self.assertEqual(ticker, "AAPL")
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["text"], "US0378331005")

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_returns_none_when_only_non_us_listings(self, mock_get):
        """
        Returns None when the ISIN search yields only non-US listings — picking a
        German/EU listing as if it were the US ticker would silently corrupt
        stocks.csv (real-world incident: Chronoscale ISIN matched only GETTEX).
        """
        mock_get.return_value = _symbol_search_response(
            [
                {
                    "symbol": "23E0",
                    "description": "CHRONOSCALE",
                    "exchange": "GETTEX",
                    "type": "stock",
                }
            ]
        )

        self.assertIsNone(TradingView.get_ticker("282644400"))

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_falls_back_to_non_us_description_when_isin_has_no_us_match(self, mock_get):
        """
        When the ISIN search returns only non-US listings, retries the search using
        the description of the first non-US match as the query — that description
        carries the *current* company name (which beats a possibly-stale name from
        the SEC 13F: e.g. Ekso Bionics was renamed to ChronoScale, but BlackRock's
        13F still lists 'EKSO BIONICS HLDGS INC').
        """
        # First call (ISIN): only non-US listings carrying the CURRENT company name.
        # Second call (description-based name search): NASDAQ match.
        mock_get.side_effect = [
            _symbol_search_response(
                [{"symbol": "23E0", "description": "CHRONOSCALE CORPORATION", "exchange": "GETTEX"}]
            ),
            _symbol_search_response(
                [
                    {
                        "symbol": "CHRN",
                        "description": "ChronoScale Corporation",
                        "exchange": "NASDAQ",
                    },
                    {"symbol": "0IFR", "description": "ChronoScale Corporation", "exchange": "LSE"},
                ]
            ),
        ]

        ticker = TradingView.get_ticker("282644400", company_name="EKSO BIONICS HLDGS INC")

        self.assertEqual(ticker, "CHRN")
        # The second call must query using the TV-provided description, NOT the
        # stale 13F company_name, to handle company renames correctly.
        second_call_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_call_params["text"], "CHRONOSCALE CORPORATION")

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_returns_none_when_no_us_listing_anywhere(self, mock_get):
        """
        Returns None when neither the ISIN search nor the description-based fallback
        yields a US-listed match.
        """
        mock_get.side_effect = [
            _symbol_search_response(
                [{"symbol": "23E0", "description": "OBSCURE CO", "exchange": "GETTEX"}]
            ),
            _symbol_search_response(
                [{"symbol": "OBSC", "description": "Obscure Co", "exchange": "LSE"}]
            ),
        ]

        self.assertIsNone(TradingView.get_ticker("282644400"))
        self.assertEqual(mock_get.call_count, 2)

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_strips_em_highlight_tags_from_results(self, mock_get):
        """
        TradingView wraps the matched substring with <em>...</em> tags in the
        description (and sometimes the symbol). Those tags must be stripped before
        the data lands in stocks.csv.
        """
        mock_get.return_value = _symbol_search_response(
            [
                {
                    "symbol": "CHRN",
                    "description": "<em>ChronoScale</em> <em>Corporation</em>",
                    "exchange": "NASDAQ",
                }
            ]
        )

        self.assertEqual(TradingView.get_company("282644301"), "ChronoScale Corporation")
        self.assertEqual(TradingView.get_ticker("282644301"), "CHRN")

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_skips_description_fallback_when_no_isin_results(self, mock_get):
        """
        When the ISIN search itself returns nothing, there is no description to fall
        back on — returns None without a second HTTP call.
        """
        mock_get.return_value = _symbol_search_response([])

        self.assertIsNone(TradingView.get_ticker("282644400"))
        self.assertEqual(mock_get.call_count, 1)

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_returns_none_when_no_symbols(self, mock_get):
        """
        Returns None when the endpoint reports zero matches.
        """
        mock_get.return_value = _symbol_search_response([])
        self.assertIsNone(TradingView.get_ticker("037833100"))

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_returns_none_on_invalid_cusip(self, mock_get):
        """
        Returns None when the CUSIP cannot be converted to an ISIN (skips the HTTP call).
        """
        self.assertIsNone(TradingView.get_ticker("BADCUSIP"))
        mock_get.assert_not_called()

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_ticker_returns_none_on_http_error(self, mock_get):
        """
        Returns None when the endpoint replies with a non-OK status.
        """
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 403
        mock_get.return_value = resp

        self.assertIsNone(TradingView.get_ticker("037833100"))

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_get_company_returns_formatted_description(self, mock_get):
        """
        Returns the description of the best match, run through format_string.
        """
        mock_get.return_value = _symbol_search_response(
            [
                {
                    "symbol": "AAPL",
                    "description": "APPLE INC",
                    "exchange": "NASDAQ",
                    "type": "stock",
                }
            ]
        )

        self.assertEqual(TradingView.get_company("037833100"), "Apple Inc")

    @patch("app.stocks.libraries.trading_view.requests.get")
    def test_sends_browser_headers(self, mock_get):
        """
        Sends Referer and Origin headers so TradingView does not reject the request with 403.
        """
        mock_get.return_value = _symbol_search_response(
            [{"symbol": "AAPL", "description": "Apple Inc.", "exchange": "NASDAQ"}]
        )

        TradingView.get_ticker("037833100")

        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers.get("Referer"), "https://www.tradingview.com/")
        self.assertEqual(headers.get("Origin"), "https://www.tradingview.com")
        self.assertIn("User-Agent", headers)


if __name__ == "__main__":
    unittest.main()
