from app.stocks.libraries.finance_database import FinanceDatabase
import pandas as pd
import unittest
from unittest.mock import patch


class TestFinanceDatabase(unittest.TestCase):

    @patch('app.stocks.libraries.finance_database.fd.Equities')
    def test_get_ticker(self, mock_equities):
        """
        Tests the get_ticker method using mocks.
        """
        # Prepare mock data
        mock_data = pd.DataFrame(
            {'name': ['Tesla, Inc.']},
            index=['TSLA']
        )
        mock_equities.return_value.search.return_value = mock_data

        # Test for a known CUSIP
        tsla_ticker = FinanceDatabase.get_ticker('88160R101')
        self.assertEqual(tsla_ticker, 'TSLA')
        mock_equities.return_value.search.assert_called_with(cusip='88160R101')

        # Test for a non-existent CUSIP
        mock_equities.return_value.search.return_value = pd.DataFrame()
        invalid_ticker = FinanceDatabase.get_ticker('INVALID')
        self.assertIsNone(invalid_ticker)


    @patch('app.stocks.libraries.finance_database.fd.Equities')
    def test_get_company(self, mock_equities):
        """
        Tests the get_company method using mocks.
        """
        mock_data = pd.DataFrame(
            {'name': ['TESLA INC']},
            index=['TSLA']
        )
        mock_equities.return_value.search.return_value = mock_data

        tsla_company = FinanceDatabase.get_company('88160R101')
        self.assertEqual(tsla_company, 'Tesla Inc') # format_string makes it title case


    @patch('app.stocks.libraries.finance_database.open_issue')
    @patch('app.stocks.libraries.finance_database.fd.Equities')
    def test_get_cusip(self, mock_equities, mock_open_issue):
        """
        Tests the get_cusip method using mocks.
        """
        mock_data = pd.DataFrame(
            {'cusip': ['88160R101']},
            index=['TSLA']
        )
        mock_equities.return_value.search.return_value = mock_data

        tsla_cusip = FinanceDatabase.get_cusip('TSLA')
        self.assertEqual(tsla_cusip, '88160R101')

        # Test for a non-existent ticker
        mock_equities.return_value.search.return_value = pd.DataFrame()
        invalid_cusip = FinanceDatabase.get_cusip('TICKER')
        self.assertTrue(invalid_cusip.startswith('N/A '))
        mock_open_issue.assert_called_once()


if __name__ == '__main__':
    unittest.main()
