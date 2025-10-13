from app.tickers.libraries.finance_database import FinanceDatabase
import unittest
from unittest.mock import patch


class TestFinanceDatabase(unittest.TestCase):

    @patch('app.tickers.libraries.finance_database.open_issue')
    def test_get_ticker(self, mock_open_issue):
        """
        Tests the get_ticker method for known CUSIPs.
        """
        # Test for a known CUSIP (Tesla)
        tsla_ticker = FinanceDatabase.get_ticker('88160R101')
        self.assertEqual(tsla_ticker, 'TSLA')

        # Test for a non-existent CUSIP
        invalid_ticker = FinanceDatabase.get_ticker('A01234567Z')
        self.assertIsNone(invalid_ticker)


    @patch('app.tickers.libraries.finance_database.open_issue')
    def test_get_company(self, mock_open_issue):
        """
        Tests the get_company method for known CUSIPs.
        """
        # Test for a known CUSIP (Tesla)
        tsla_company = FinanceDatabase.get_company('88160R101')
        self.assertEqual(tsla_company, 'Tesla, Inc.')

        # Test for a non-existent CUSIP
        invalid_company = FinanceDatabase.get_company('A01234567Z')
        self.assertIsNone(invalid_company)


    @patch('app.tickers.libraries.finance_database.open_issue')
    def test_get_cusip(self, mock_open_issue):
        """
        Tests the get_cusip method both for valid and invalid tickers.
        """
        # Test for a known ticker (Tesla)
        tsla_cusip = FinanceDatabase.get_cusip('TSLA')
        self.assertEqual(tsla_cusip, '88160R101')

        # Test for a non-existent ticker
        invalid_cusip = FinanceDatabase.get_cusip('TICKER')
        self.assertTrue(invalid_cusip.startswith('N/A '))


if __name__ == '__main__':
    unittest.main()
