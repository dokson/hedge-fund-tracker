import unittest
from unittest.mock import patch, MagicMock
from app.stocks.libraries.finnhub import Finnhub


def _make_lookup_response(symbol='AAPL', description='Apple Inc', stock_type='Common Stock'):
    """
    Creates a minimal Finnhub symbol_lookup response.
    """
    return {
        'result': [{'symbol': symbol, 'description': description, 'type': stock_type}]
    }


class TestFinnhubGetTicker(unittest.TestCase):

    def setUp(self):
        """
        Patches time.sleep to avoid the 1-second rate-limit pause in _ticker_lookup.
        """
        # Patch time.sleep to avoid the 1-second rate-limit pause in _ticker_lookup
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()

    def tearDown(self):
        """
        Stops the sleep patcher started in setUp.
        """
        self.sleep_patcher.stop()

    def test_returns_none_when_client_not_configured(self):
        """
        Returns None immediately when no FINNHUB_API_KEY is configured (CLIENT is None).
        """
        with patch.object(Finnhub, 'CLIENT', None):
            result = Finnhub.get_ticker('037833100', company_name='Apple Inc')

        self.assertIsNone(result)

    def test_resolves_ticker_via_cusip(self):
        """
        Returns the ticker symbol when the CUSIP resolves via the Finnhub API.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = _make_lookup_response(symbol='AAPL')

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('037833100')

        self.assertEqual(result, 'AAPL')

    def test_falls_back_to_company_first_word_when_cusip_fails(self):
        """
        Falls back to searching by the first significant word of the company name when CUSIP lookup fails.
        """
        mock_client = MagicMock()

        def symbol_lookup_side_effect(query):
            """
            Returns no result for CUSIP but finds ticker via company first word.
            """
            if query == '037833100':
                return {'result': []}  # CUSIP not found
            if query == 'Apple':
                return _make_lookup_response(symbol='AAPL')
            return {'result': []}

        mock_client.symbol_lookup.side_effect = symbol_lookup_side_effect

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('037833100', company_name='Apple Inc')

        self.assertEqual(result, 'AAPL')

    def test_does_not_use_common_words_as_fallback_query(self):
        """
        Does not attempt a company name fallback when the first word is a common word (e.g. 'The', 'Inc').
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {'result': []}

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('037833100', company_name='Corp Holdings Ltd')

        self.assertIsNone(result)
        # Only called once (with CUSIP), not with 'Corp' since it's in COMMON_COMPANY_WORDS
        self.assertEqual(mock_client.symbol_lookup.call_count, 1)

    def test_returns_none_when_all_lookups_fail(self):
        """
        Returns None when neither the CUSIP nor the company name lookup finds a match.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {'result': []}

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('000000000', company_name='Unknown Company')

        self.assertIsNone(result)

    def test_skips_fallback_when_no_company_name_provided(self):
        """
        Does not attempt a company name fallback if company_name is not provided.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {'result': []}

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('000000000')

        self.assertIsNone(result)
        self.assertEqual(mock_client.symbol_lookup.call_count, 1)


class TestFinnhubGetCompany(unittest.TestCase):

    def setUp(self):
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()

    def tearDown(self):
        """
        Stops the sleep patcher started in setUp.
        """
        self.sleep_patcher.stop()

    def test_returns_formatted_company_name(self):
        """
        Returns the company description formatted as title case.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = _make_lookup_response(
            symbol='AAPL', description='APPLE INC'
        )

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_company('037833100')

        self.assertEqual(result, 'Apple Inc')

    def test_returns_none_when_no_match_found(self):
        """
        Returns None when no match is found via the CUSIP lookup.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {'result': []}

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_company('000000000')

        self.assertIsNone(result)

    def test_returns_none_when_client_not_configured(self):
        """
        Returns None when the Finnhub client is not configured.
        """
        with patch.object(Finnhub, 'CLIENT', None):
            result = Finnhub.get_company('037833100')

        self.assertIsNone(result)


class TestFinnhubLookup(unittest.TestCase):

    def setUp(self):
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()

    def tearDown(self):
        """
        Stops the sleep patcher started in setUp.
        """
        self.sleep_patcher.stop()

    def test_prioritizes_common_stock_type_over_other_types(self):
        """
        Returns the Common Stock entry even if other result types appear first.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {
            'result': [
                {'symbol': 'AAPL.W', 'description': 'Apple Warrant', 'type': 'Warrant'},
                {'symbol': 'AAPL', 'description': 'Apple Inc', 'type': 'Common Stock'},
            ]
        }

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('037833100')

        self.assertEqual(result, 'AAPL')

    def test_falls_back_to_first_result_when_no_common_stock(self):
        """
        Returns the first result when no Common Stock type is present.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {
            'result': [
                {'symbol': 'AAPL.W', 'description': 'Apple Warrant', 'type': 'Warrant'},
                {'symbol': 'AAPL.P', 'description': 'Apple Preferred', 'type': 'Preferred'},
            ]
        }

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub.get_ticker('037833100')

        self.assertEqual(result, 'AAPL.W')

    def test_returns_none_when_result_list_is_empty(self):
        """
        Returns None when the API returns an empty result list.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {'result': []}

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub._lookup('037833100')

        self.assertIsNone(result)

    def test_returns_none_when_response_has_no_result_key(self):
        """
        Returns None when the API response is missing the 'result' key.
        """
        mock_client = MagicMock()
        mock_client.symbol_lookup.return_value = {}

        with patch.object(Finnhub, 'CLIENT', mock_client):
            result = Finnhub._lookup('037833100')

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
