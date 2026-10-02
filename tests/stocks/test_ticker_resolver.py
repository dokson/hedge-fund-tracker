import unittest
from unittest.mock import patch

import pandas as pd

from app.stocks.ticker_resolver import TickerResolver


def _empty_stocks():
    """
    Returns an empty stocks DataFrame with the correct CUSIP index structure.
    """
    df = pd.DataFrame(columns=["Ticker", "Company"])
    df.index.name = "CUSIP"
    return df


def _cached_stocks(cusip, ticker, company):
    """
    Returns a single-row stocks DataFrame simulating a cached CUSIP entry.
    """
    df = pd.DataFrame({"Ticker": [ticker], "Company": [company]}, index=[cusip])
    df.index.name = "CUSIP"
    return df


class TestTickerResolverGetLibraries(unittest.TestCase):
    def test_get_libraries_priority_order(self):
        """
        Returns exactly the resolution chain in priority order: YFinance → OpenFIGI → TradingView.
        """
        names = [library.__name__ for library in TickerResolver.get_libraries()]

        self.assertEqual(names, ["YFinance", "OpenFIGI", "TradingView"])


class TestTickerResolverResolveTicker(unittest.TestCase):
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_uses_cached_ticker_when_cusip_in_database(self, mock_load):
        """
        Uses the locally cached ticker without calling any library when the CUSIP is already known.
        """
        mock_load.return_value = _cached_stocks("037833100", "AAPL", "Apple Inc")
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": ["Apple Inc"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Ticker"], "AAPL")

    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_resolves_via_first_library_when_cusip_unknown(
        self, mock_load, mock_get_ticker, mock_get_company, mock_save
    ):
        """
        Resolves CUSIP and company via YFinance and saves result to the local database.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_ticker.return_value = "AAPL"
        mock_get_company.return_value = "Apple Inc"
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": ["Apple Inc"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Ticker"], "AAPL")
        self.assertEqual(result.loc[0, "Company"], "Apple Inc")
        mock_save.assert_called_once()

    @patch("app.stocks.ticker_resolver.resolve_industry")
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_resolve_ticker_passes_industry_to_save_stock(
        self,
        mock_load,
        mock_get_ticker,
        mock_get_company,
        mock_save,
        mock_resolve_industry,
    ):
        """
        After CUSIP→ticker resolution, the chain must classify the resulting
        ticker via resolve_industry and forward the result as the `industry`
        kwarg to save_stock — otherwise stocks.csv ends up with empty Industry
        for every newly added row.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_ticker.return_value = "AAPL"
        mock_get_company.return_value = "Apple Inc"
        mock_resolve_industry.return_value = "Consumer Electronics"
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": ["Apple Inc"]})

        TickerResolver.resolve_ticker(df)

        mock_resolve_industry.assert_called_once_with("AAPL", "Apple Inc")
        call_kwargs = mock_save.call_args.kwargs
        self.assertEqual(call_kwargs["industry"], "Consumer Electronics")

    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_company")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_ticker")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_falls_back_to_second_library_when_first_returns_none(
        self, mock_load, mock_yf_ticker, mock_of_ticker, mock_of_company, mock_save
    ):
        """
        Falls back to OpenFIGI when YFinance cannot resolve the CUSIP.
        """
        mock_load.return_value = _empty_stocks()
        mock_yf_ticker.return_value = None
        mock_of_ticker.return_value = "AAPL"
        mock_of_company.return_value = "Apple Inc"
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": ["Apple Inc"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Ticker"], "AAPL")
        mock_save.assert_called_once()

    @patch("app.stocks.ticker_resolver.open_issue")
    @patch("app.stocks.ticker_resolver.TradingView.get_ticker")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_ticker")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_opens_github_issue_when_no_library_resolves_ticker(
        self, mock_load, mock_yf, mock_of, mock_tv, mock_issue
    ):
        """
        Opens a GitHub issue when all libraries fail to resolve the CUSIP to a ticker.
        """
        mock_load.return_value = _empty_stocks()
        mock_yf.return_value = None
        mock_of.return_value = None
        mock_tv.return_value = None
        df = pd.DataFrame({"CUSIP": ["999999999"], "Company": ["Unknown Corp"]})

        TickerResolver.resolve_ticker(df)

        mock_issue.assert_called_once()
        subject = mock_issue.call_args[0][0]
        self.assertIn("Ticker not found", subject)

    @patch("app.stocks.ticker_resolver.open_issue")
    @patch("app.stocks.ticker_resolver.TradingView.get_ticker")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_ticker")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_unresolved_cusip_with_empty_company_does_not_raise(
        self, mock_load, mock_yf, mock_of, mock_tv, _mock_issue
    ):
        """
        An unresolvable CUSIP filed without a company name leaves both fields blank.
        """
        mock_load.return_value = _empty_stocks()
        mock_yf.return_value = None
        mock_of.return_value = None
        mock_tv.return_value = None
        df = pd.DataFrame({"CUSIP": ["000000000"], "Company": [""]})

        result = TickerResolver.resolve_ticker(df)

        self.assertIsNone(result.loc[0, "Ticker"])
        self.assertEqual(result.loc[0, "Company"], "")

    @patch("app.stocks.ticker_resolver.open_issue")
    @patch("app.stocks.ticker_resolver.TradingView.get_ticker")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_ticker")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_no_issue_when_a_lookup_failed_transiently(
        self, mock_load, mock_yf, mock_of, mock_tv, mock_issue
    ):
        """
        A rate-limited or unreachable provider makes the miss inconclusive, so no issue is opened.
        """
        from app.stocks.libraries.openfigi import OpenFIGIUnavailableError

        mock_load.return_value = _empty_stocks()
        mock_yf.return_value = None
        mock_of.side_effect = OpenFIGIUnavailableError("rate limited")
        mock_tv.return_value = None
        df = pd.DataFrame({"CUSIP": ["000000000"], "Company": ["Unknown Corp"]})

        TickerResolver.resolve_ticker(df)

        mock_of.assert_called_once_with(
            "000000000", company_name="Unknown Corp", raise_unavailable=True
        )
        mock_issue.assert_not_called()

    @patch("app.stocks.ticker_resolver.open_issue")
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.TradingView.get_company")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_opens_github_issue_when_company_not_found_and_original_is_empty(
        self,
        mock_load,
        mock_ticker,
        mock_yf_co,
        mock_of_co,
        mock_tv_co,
        mock_save,
        mock_issue,
    ):
        """
        Opens a GitHub issue when ticker is found but no library can resolve the company name
        and the original company field in the DataFrame is also empty.
        """
        mock_load.return_value = _empty_stocks()
        mock_ticker.return_value = "AAPL"
        mock_yf_co.return_value = None
        mock_of_co.return_value = None
        mock_tv_co.return_value = None
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": [""]})

        TickerResolver.resolve_ticker(df)

        mock_issue.assert_called_once()
        subject = mock_issue.call_args[0][0]
        self.assertIn("Company not found", subject)

    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_fills_empty_company_from_database(self, mock_load):
        """
        Fills an empty company field in the input DataFrame from the cached database value.
        """
        mock_load.return_value = _cached_stocks("037833100", "AAPL", "Apple Inc")
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": [""], "Ticker": ["AAPL"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Company"], "Apple Inc")

    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_fills_empty_company_when_cusip_is_duplicated_in_database(self, mock_load):
        """
        Fills an empty company field with a scalar when the cached CUSIP appears on several rows.
        """
        stocks = pd.DataFrame(
            {"Ticker": ["AAPL", "AAPL"], "Company": ["Apple Inc", "Apple Inc"]},
            index=["037833100", "037833100"],
        )
        stocks.index.name = "CUSIP"
        mock_load.return_value = stocks
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": [""], "Ticker": ["AAPL"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Company"], "Apple Inc")

    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_resolves_multiple_cusips_independently(
        self, mock_load, mock_ticker, mock_company, mock_save
    ):
        """
        Resolves each row in the DataFrame independently, saving each resolved ticker.
        """
        mock_load.return_value = _empty_stocks()
        mock_ticker.side_effect = ["AAPL", "JNJ"]
        mock_company.side_effect = ["Apple Inc", "Johnson & Johnson"]
        df = pd.DataFrame(
            {"CUSIP": ["037833100", "478160104"], "Company": ["Apple Inc", "Johnson & Johnson"]}
        )

        result = TickerResolver.resolve_ticker(df)

        for idx, expected in [(0, "AAPL"), (1, "JNJ")]:
            with self.subTest(row=idx):
                self.assertEqual(result.loc[idx, "Ticker"], expected)
        self.assertEqual(mock_save.call_count, 2)

    @patch("app.stocks.ticker_resolver.resolve_industry")
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_new_cusip_for_known_ticker_inherits_company_and_industry(
        self,
        mock_load,
        mock_get_ticker,
        mock_get_company,
        mock_save,
        mock_resolve_industry,
    ):
        """
        A new CUSIP resolving to a known ticker inherits the existing Company
        and Industry instead of re-resolving them (ticker→company uniqueness).
        """
        stocks = pd.DataFrame(
            {"Ticker": ["ACME"], "Company": ["Acme Corp"], "Industry": ["Widgets"]},
            index=["111111111"],
        )
        stocks.index.name = "CUSIP"
        mock_load.return_value = stocks
        mock_get_ticker.return_value = "ACME"
        mock_get_company.return_value = "ACME CORPORATION"
        df = pd.DataFrame({"CUSIP": ["222222222"], "Company": ["Acme Corporation"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Ticker"], "ACME")
        mock_save.assert_called_once_with("222222222", "ACME", "Acme Corp", industry="Widgets")
        mock_get_company.assert_not_called()
        mock_resolve_industry.assert_not_called()

    @patch("app.stocks.ticker_resolver.resolve_industry")
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_new_cusip_for_known_ticker_defaults_missing_industry_to_empty(
        self,
        mock_load,
        mock_get_ticker,
        mock_get_company,
        mock_save,
        mock_resolve_industry,
    ):
        """
        Inheriting from a row without an Industry saves an empty string, not NaN.
        """
        mock_load.return_value = _cached_stocks("111111111", "ACME", "Acme Corp")
        mock_get_ticker.return_value = "ACME"
        mock_get_company.return_value = "ACME CORPORATION"
        df = pd.DataFrame({"CUSIP": ["222222222"], "Company": ["Acme Corporation"]})

        TickerResolver.resolve_ticker(df)

        mock_save.assert_called_once_with("222222222", "ACME", "Acme Corp", industry="")
        mock_resolve_industry.assert_not_called()

    @patch("app.stocks.ticker_resolver.open_issue")
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.TradingView.get_company")
    @patch("app.stocks.ticker_resolver.OpenFIGI.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_company")
    @patch("app.stocks.ticker_resolver.YFinance.get_ticker")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_uses_original_company_name_when_libraries_return_none(
        self,
        mock_load,
        mock_ticker,
        mock_yf_co,
        mock_of_co,
        mock_tv_co,
        mock_save,
        mock_issue,
    ):
        """
        Falls back to the original company name from the input DataFrame when all libraries
        fail to return a company name (avoids opening a false issue if the name is already known).
        """
        mock_load.return_value = _empty_stocks()
        mock_ticker.return_value = "AAPL"
        mock_yf_co.return_value = None
        mock_of_co.return_value = None
        mock_tv_co.return_value = None
        df = pd.DataFrame({"CUSIP": ["037833100"], "Company": ["Apple Inc"]})

        result = TickerResolver.resolve_ticker(df)

        self.assertEqual(result.loc[0, "Company"], "Apple Inc")
        mock_issue.assert_not_called()


class TestTickerResolverAssignCUSIP(unittest.TestCase):
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.FMP.get_cusip")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_fetches_and_saves_cusip_for_new_ticker(self, mock_load, mock_get_cusip, mock_save):
        """
        Queries FMP and saves the result for tickers not found in the local database.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_cusip.return_value = "037833100"
        df = pd.DataFrame({"Ticker": ["AAPL"], "Company": ["Apple Inc"]})

        result = TickerResolver.assign_cusip(df)

        self.assertEqual(result.loc[0, "CUSIP"], "037833100")
        mock_save.assert_called_once()

    @patch("app.stocks.ticker_resolver.open_issue")
    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.FMP.get_cusip")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_opens_issue_and_leaves_cusip_null_when_fmp_misses(
        self, mock_load, mock_get_cusip, mock_save, mock_issue
    ):
        """
        Opens a GitHub issue and leaves the CUSIP as NaN when FMP cannot resolve the
        ticker. No synthetic placeholder is written so stocks.csv only ever contains
        real CUSIPs.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_cusip.return_value = None
        df = pd.DataFrame({"Ticker": ["NEWX"], "Company": ["New Co"]})

        result = TickerResolver.assign_cusip(df)

        self.assertTrue(pd.isna(result.loc[0, "CUSIP"]))
        mock_save.assert_not_called()
        mock_issue.assert_called_once()

    @patch("app.stocks.ticker_resolver.FMP.get_cusip")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_leaves_cusip_null_when_fetch_raises(self, mock_load, mock_get_cusip):
        """
        Leaves the CUSIP as NaN when FMP raises an exception for the ticker.
        """
        mock_load.return_value = _empty_stocks()
        mock_get_cusip.side_effect = Exception("API error")
        df = pd.DataFrame({"Ticker": ["AAPL"], "Company": ["Apple Inc"]})

        result = TickerResolver.assign_cusip(df)

        self.assertTrue(pd.isna(result.loc[0, "CUSIP"]))

    @patch("app.stocks.ticker_resolver.save_stock")
    @patch("app.stocks.ticker_resolver.FMP.get_cusip")
    @patch("app.stocks.ticker_resolver.load_stocks")
    def test_handles_mixed_cached_and_new_tickers(self, mock_load, mock_get_cusip, mock_save):
        """
        Handles a DataFrame where some tickers are cached and others require a remote fetch.
        """
        mock_load.return_value = _cached_stocks("037833100", "AAPL", "Apple Inc")
        mock_get_cusip.return_value = "594918104"
        df = pd.DataFrame(
            {"Ticker": ["AAPL", "JNJ"], "Company": ["Apple Inc", "Johnson & Johnson"]}
        )

        result = TickerResolver.assign_cusip(df)

        self.assertEqual(result.loc[0, "CUSIP"], "037833100")
        self.assertEqual(result.loc[1, "CUSIP"], "594918104")


if __name__ == "__main__":
    unittest.main()
