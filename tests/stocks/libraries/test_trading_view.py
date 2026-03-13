import unittest
from unittest.mock import patch, MagicMock, call
from datetime import date
import pandas as pd
from app.stocks.libraries.trading_view import TradingView


def _make_hist_df(close=152.5, high=155.0, low=145.0, date_str='2023-12-25'):
    """
    Creates a minimal DataFrame mimicking tvDatafeed output.
    """
    return pd.DataFrame(
        {'close': [close], 'high': [high], 'low': [low]},
        index=pd.to_datetime([date_str])
    )


class TestTradingViewGetTicker(unittest.TestCase):

    def test_get_ticker_always_returns_none(self):
        """
        TradingView does not support CUSIP-to-ticker resolution; always returns None.
        """
        result = TradingView.get_ticker('037833100')

        self.assertIsNone(result)


class TestTradingViewGetCompany(unittest.TestCase):

    def test_get_company_always_returns_none(self):
        """
        TradingView does not support company lookup; always returns None.
        """
        result = TradingView.get_company('037833100')

        self.assertIsNone(result)


class TestTradingViewGetCurrentPrice(unittest.TestCase):

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_price_from_first_successful_exchange(self, mock_tv_class):
        """
        Returns the last close price from the first exchange that returns data.
        """
        mock_tv_class.return_value.get_hist.return_value = _make_hist_df(close=152.5)

        price = TradingView.get_current_price('AAPL')

        self.assertEqual(price, 152.5)
        self.assertIsInstance(price, float)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
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

        price = TradingView.get_current_price('AAPL')

        self.assertEqual(price, 149.99)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
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

        price = TradingView.get_current_price('AAPL')

        self.assertEqual(price, 149.99)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_none_when_all_exchanges_return_none(self, mock_tv_class):
        """
        Returns None when no exchange can provide data for the ticker.
        """
        mock_tv_class.return_value.get_hist.return_value = None

        price = TradingView.get_current_price('UNKNOWN')

        self.assertIsNone(price)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_none_when_all_exchanges_raise(self, mock_tv_class):
        """
        Returns None (not an exception) when every exchange raises.
        """
        mock_tv_class.return_value.get_hist.side_effect = Exception("Network error")

        price = TradingView.get_current_price('AAPL')

        self.assertIsNone(price)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_none_when_dataframe_is_empty(self, mock_tv_class):
        """
        Returns None when an exchange returns an empty DataFrame.
        """
        mock_tv_class.return_value.get_hist.return_value = pd.DataFrame()

        price = TradingView.get_current_price('AAPL')

        self.assertIsNone(price)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_uses_injected_tv_session_instead_of_creating_new(self, mock_tv_class):
        """
        Uses a tv_session passed via kwargs instead of instantiating a new TvDatafeed.
        """
        mock_session = MagicMock()
        mock_session.get_hist.return_value = _make_hist_df(close=150.0)

        TradingView.get_current_price('AAPL', tv_session=mock_session)

        mock_tv_class.assert_not_called()
        mock_session.get_hist.assert_called()


class TestTradingViewGetAvgPrice(unittest.TestCase):

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_high_low_average_for_matching_date(self, mock_tv_class):
        """
        Returns (high + low) / 2 for the specific date when data is available.
        """
        hist_df = _make_hist_df(high=160.0, low=140.0, date_str='2023-12-25')
        mock_tv_class.return_value.get_hist.return_value = hist_df

        price = TradingView.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, 150.0)  # (160 + 140) / 2

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_none_when_date_not_in_data(self, mock_tv_class):
        """
        Returns None when the requested date is not present in the historical data.
        """
        # Data only for 2023-12-24, not the requested 2023-12-25
        hist_df = _make_hist_df(date_str='2023-12-24')
        mock_tv_class.return_value.get_hist.return_value = hist_df

        price = TradingView.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertIsNone(price)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_returns_none_when_no_exchange_returns_data(self, mock_tv_class):
        """
        Returns None when all exchanges fail to return historical data.
        """
        mock_tv_class.return_value.get_hist.return_value = None

        price = TradingView.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertIsNone(price)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_falls_back_to_next_exchange_when_first_returns_none(self, mock_tv_class):
        """
        Falls back to a subsequent exchange when the first returns None.
        """
        hist_df = _make_hist_df(high=160.0, low=140.0, date_str='2023-12-25')

        def get_hist_side_effect(symbol, exchange, interval, n_bars):
            """
            Returns None for the first exchange, data for subsequent ones.
            """
            if exchange == TradingView.EXCHANGES[0]:
                return None
            return hist_df

        mock_tv_class.return_value.get_hist.side_effect = get_hist_side_effect

        price = TradingView.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, 150.0)

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_rounds_result_to_two_decimal_places(self, mock_tv_class):
        """
        Returns the average price rounded to 2 decimal places.
        """
        hist_df = _make_hist_df(high=100.1, low=100.0, date_str='2023-12-25')
        mock_tv_class.return_value.get_hist.return_value = hist_df

        price = TradingView.get_avg_price('AAPL', date(2023, 12, 25))

        self.assertEqual(price, round((100.1 + 100.0) / 2, 2))

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_uses_injected_tv_session_instead_of_creating_new(self, mock_tv_class):
        """
        Uses a tv_session passed via kwargs instead of instantiating a new TvDatafeed.
        """
        mock_session = MagicMock()
        hist_df = _make_hist_df(date_str='2023-12-25')
        mock_session.get_hist.return_value = hist_df

        TradingView.get_avg_price('AAPL', date(2023, 12, 25), tv_session=mock_session)

        mock_tv_class.assert_not_called()


if __name__ == '__main__':
    unittest.main()
