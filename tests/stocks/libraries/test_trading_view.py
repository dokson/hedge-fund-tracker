from app.stocks.libraries.trading_view import TradingView
import pandas as pd
import unittest
from unittest.mock import MagicMock, patch


class TestTradingView(unittest.TestCase):

    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_get_current_price_success(self, mock_tv_class):
        """
        Test fetching current price using TvDatafeed.
        """
        mock_tv_instance = mock_tv_class.return_value
        
        # Mock dataframe response
        data = {
            'close': [150.0, 152.5]
        }
        df = pd.DataFrame(data)
        mock_tv_instance.get_hist.return_value = df
        
        price = TradingView.get_current_price("AAPL")
        
        assert price == 152.5
        assert isinstance(price, float)


    @patch('app.stocks.libraries.trading_view.TvDatafeed')
    def test_get_current_price_failure(self, mock_tv_class):
        """
        Test failure to fetch current price.
        """
        mock_tv_instance = mock_tv_class.return_value
        mock_tv_instance.get_hist.return_value = None # or empty df
        
        price = TradingView.get_current_price("INVALID")
        assert price is None


if __name__ == '__main__':
    unittest.main()
