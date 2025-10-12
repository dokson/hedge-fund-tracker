from app.tickers.libraries.finance_database import FinanceDatabase
import unittest


class TestFinanceDatabase(unittest.TestCase):

    def test_get_cusip(self):
        """
        Tests the get_cusip method both for valid and invalid tickers.
        """
        # Test for a known ticker (Tesla)
        tsla_cusip = FinanceDatabase.get_cusip('TSLA')
        self.assertEqual(tsla_cusip, '88160R101')

        # Test for a non-existent ticker
        invalid_cusip = FinanceDatabase.get_cusip('NONEXISTENTTICKERXYZ')
        self.assertTrue(invalid_cusip.startswith('N/A '))


if __name__ == '__main__':
    unittest.main()
