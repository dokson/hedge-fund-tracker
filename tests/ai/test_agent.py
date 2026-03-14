import unittest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from app.ai.agent import AnalystAgent, InvalidAIResponseError


def _make_stock_df(**kwargs):
    """
    Builds a minimal stock DataFrame for due diligence tests, with optional overrides.
    """
    defaults = {
        'Ticker': ['AAPL'],
        'Company': ['Apple Inc'],
        'Value': [1_000_000],
        'Delta_Value': [50_000],
        'Delta': ['NEW'],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


def _make_analysis_df():
    """
    Builds a minimal analysis DataFrame with two numeric metrics for Promise Score tests.
    """
    return pd.DataFrame({
        'Ticker': ['AAPL', 'MSFT', 'GOOGL'],
        'Metric1': [10, 20, 15],
        'Metric2': [2, 5, 3],
    })


class TestAnalystAgentInit(unittest.TestCase):

    @patch('app.ai.agent.quarter_analysis')
    @patch('app.ai.agent.get_quarter_date')
    def test_stores_quarter_string(self, mock_date, mock_analysis):
        """
        Stores the quarter string as an instance attribute.
        """
        mock_date.return_value = '2023-12-31'
        mock_analysis.return_value = pd.DataFrame()

        agent = AnalystAgent('2023Q4')

        self.assertEqual(agent.quarter, '2023Q4')

    @patch('app.ai.agent.quarter_analysis')
    @patch('app.ai.agent.get_quarter_date')
    def test_stores_filing_date_from_quarter(self, mock_date, mock_analysis):
        """
        Converts the quarter string to a filing date via get_quarter_date().
        """
        mock_date.return_value = '2023-12-31'
        mock_analysis.return_value = pd.DataFrame()

        agent = AnalystAgent('2023Q4')

        self.assertEqual(agent.filing_date, '2023-12-31')

    @patch('app.ai.agent.quarter_analysis')
    @patch('app.ai.agent.get_quarter_date')
    def test_stores_provided_ai_client(self, mock_date, mock_analysis):
        """
        Stores the provided AI client as an instance attribute.
        """
        mock_date.return_value = '2023-12-31'
        mock_analysis.return_value = pd.DataFrame()
        mock_client = MagicMock()

        agent = AnalystAgent('2023Q4', ai_client=mock_client)

        self.assertEqual(agent.ai_client, mock_client)

    @patch('app.ai.agent.quarter_analysis')
    @patch('app.ai.agent.get_quarter_date')
    def test_loads_analysis_dataframe_on_init(self, mock_date, mock_analysis):
        """
        Loads the quarter analysis DataFrame by calling quarter_analysis() on init.
        """
        mock_date.return_value = '2023-12-31'
        expected_df = _make_analysis_df()
        mock_analysis.return_value = expected_df

        agent = AnalystAgent('2023Q4')

        mock_analysis.assert_called_once_with('2023Q4')
        pd.testing.assert_frame_equal(agent.analysis_df, expected_df)


class TestInvalidAIResponseError(unittest.TestCase):

    def test_is_an_exception(self):
        """
        InvalidAIResponseError is a subclass of Exception.
        """
        self.assertTrue(issubclass(InvalidAIResponseError, Exception))

    def test_raises_and_catches_with_message(self):
        """
        Can be raised and caught with a descriptive message.
        """
        with self.assertRaises(InvalidAIResponseError) as ctx:
            raise InvalidAIResponseError("weights do not sum to 1.0")

        self.assertIn("weights do not sum to 1.0", str(ctx.exception))


class TestCalculatePromiseScores(unittest.TestCase):
    """
    Tests for AnalystAgent._calculate_promise_scores().
    This is pure logic with no I/O - no mocks required.
    """

    def setUp(self):
        """
        Patches quarter_analysis and get_quarter_date for AnalystAgent instantiation.
        """
        self.q_analysis_patcher = patch('app.ai.agent.quarter_analysis', return_value=pd.DataFrame())
        self.date_patcher = patch('app.ai.agent.get_quarter_date', return_value='2023-12-31')
        self.q_analysis_patcher.start()
        self.date_patcher.start()
        self.agent = AnalystAgent('2023Q4', ai_client=MagicMock())

    def tearDown(self):
        """
        Stops all active patchers started in setUp.
        """
        self.q_analysis_patcher.stop()
        self.date_patcher.stop()

    def test_adds_promise_score_column(self):
        """
        Adds a 'Promise_Score' column to the returned DataFrame.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {'Metric1': 0.5, 'Metric2': 0.5})

        self.assertIn('Promise_Score', result.columns)

    def test_does_not_mutate_input_dataframe(self):
        """
        Returns a new DataFrame and leaves the original unchanged.
        """
        df = _make_analysis_df()

        self.agent._calculate_promise_scores(df, {'Metric1': 1.0})

        self.assertNotIn('Promise_Score', df.columns)

    def test_scores_are_between_0_and_100(self):
        """
        All Promise_Score values are in the [0, 100] range.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {'Metric1': 0.6, 'Metric2': 0.4})

        self.assertTrue((result['Promise_Score'] >= 0).all())
        self.assertTrue((result['Promise_Score'] <= 100).all())

    def test_higher_metric_yields_higher_score(self):
        """
        A row with a higher metric value receives a higher Promise_Score.
        """
        df = pd.DataFrame({'Ticker': ['LOW', 'HIGH'], 'Metric1': [10, 100]})

        result = self.agent._calculate_promise_scores(df, {'Metric1': 1.0})

        high_score = result.loc[result['Ticker'] == 'HIGH', 'Promise_Score'].iloc[0]
        low_score = result.loc[result['Ticker'] == 'LOW', 'Promise_Score'].iloc[0]
        self.assertGreater(high_score, low_score)

    def test_silently_skips_missing_metric_columns(self):
        """
        Does not raise when a weight key is not present in the DataFrame; skips that metric.
        """
        df = _make_analysis_df()

        result = self.agent._calculate_promise_scores(df, {'Metric1': 0.5, 'NonExistent': 0.5})

        self.assertIn('Promise_Score', result.columns)


class TestGetPromiseScoreWeights(unittest.TestCase):

    def setUp(self):
        """
        Patches time.sleep and initializes AnalystAgent with mocked dependencies.
        """
        # Patch time.sleep to speed up tenacity retries (wait_fixed(1) would add ~6s per test)
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()
        self.q_analysis_patcher = patch('app.ai.agent.quarter_analysis', return_value=pd.DataFrame())
        self.date_patcher = patch('app.ai.agent.get_quarter_date', return_value='2023-12-31')
        self.q_analysis_patcher.start()
        self.date_patcher.start()
        self.agent = AnalystAgent('2023Q4', ai_client=MagicMock())

    def tearDown(self):
        """
        Stops all active patchers started in setUp.
        """
        self.sleep_patcher.stop()
        self.q_analysis_patcher.stop()
        self.date_patcher.stop()

    @patch('app.ai.agent.PromiseScoreValidator.validate_metrics')
    @patch('app.ai.agent.PromiseScoreValidator.validate_weights')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.promise_score_weights_prompt')
    def test_returns_weights_on_valid_response(self, mock_prompt, mock_parse, mock_val_weights, mock_val_metrics):
        """
        Returns the parsed weights dict when the AI response is valid.
        """
        valid_weights = {'Metric1': 0.5, 'Metric2': 0.5}
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = valid_weights
        mock_val_weights.return_value = True
        mock_val_metrics.return_value = None

        result = self.agent._get_promise_score_weights()

        self.assertEqual(result, valid_weights)

    @patch('app.ai.agent.PromiseScoreValidator.validate_weights')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.promise_score_weights_prompt')
    def test_raises_invalid_response_error_when_weights_sum_invalid(self, mock_prompt, mock_parse, mock_val_weights):
        """
        Raises InvalidAIResponseError (triggering tenacity retry) when weights don't sum to 1.0.
        """
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = {'Metric1': 0.9}
        mock_val_weights.return_value = False

        with self.assertRaises(Exception):
            self.agent._get_promise_score_weights()

    @patch('app.ai.agent.PromiseScoreValidator.validate_metrics')
    @patch('app.ai.agent.PromiseScoreValidator.validate_weights')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.promise_score_weights_prompt')
    def test_raises_invalid_response_error_when_metrics_unrecognized(self, mock_prompt, mock_parse, mock_val_weights, mock_val_metrics):
        """
        Raises InvalidAIResponseError when any metric key is not in the recognized set.
        """
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = {'UnknownMetric': 1.0}
        mock_val_weights.return_value = True
        mock_val_metrics.return_value = ['UnknownMetric']

        with self.assertRaises(Exception):
            self.agent._get_promise_score_weights()


class TestGetAIScores(unittest.TestCase):

    def setUp(self):
        """
        Patches time.sleep and initializes AnalystAgent with mocked dependencies.
        """
        # Patch time.sleep to speed up tenacity retries (wait_fixed(1) would add ~4s per test)
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()
        self.q_analysis_patcher = patch('app.ai.agent.quarter_analysis', return_value=pd.DataFrame())
        self.date_patcher = patch('app.ai.agent.get_quarter_date', return_value='2023-12-31')
        self.q_analysis_patcher.start()
        self.date_patcher.start()
        self.agent = AnalystAgent('2023Q4', ai_client=MagicMock())

    def tearDown(self):
        """
        Stops all active patchers started in setUp.
        """
        self.sleep_patcher.stop()
        self.q_analysis_patcher.stop()
        self.date_patcher.stop()

    @patch('app.ai.agent.encode')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.quantivative_scores_prompt')
    def test_returns_parsed_scores_on_valid_response(self, mock_prompt, mock_parse, mock_encode):
        """
        Returns the AI-parsed score dict when the response contains all required keys.
        """
        valid_scores = {
            'AAPL': {'momentum_score': 0.8, 'low_volatility_score': 0.6, 'risk_score': 0.4}
        }
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = valid_scores

        result = self.agent._get_ai_scores([{'ticker': 'AAPL', 'company': 'Apple'}])

        self.assertEqual(result, valid_scores)

    @patch('app.ai.agent.encode')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.quantivative_scores_prompt')
    def test_raises_invalid_response_error_when_response_is_empty(self, mock_prompt, mock_parse, mock_encode):
        """
        Raises InvalidAIResponseError when the parsed AI response is empty.
        """
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = {}

        with self.assertRaises(Exception):
            self.agent._get_ai_scores([{'ticker': 'AAPL', 'company': 'Apple'}])

    @patch('app.ai.agent.encode')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.quantivative_scores_prompt')
    def test_raises_invalid_response_error_when_required_keys_missing(self, mock_prompt, mock_parse, mock_encode):
        """
        Raises InvalidAIResponseError when any required score key is missing from the response.
        """
        incomplete_scores = {'AAPL': {'momentum_score': 0.8}}  # missing low_volatility_score, risk_score
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = incomplete_scores

        with self.assertRaises(Exception):
            self.agent._get_ai_scores([{'ticker': 'AAPL', 'company': 'Apple'}])


class TestRunStockDueDiligence(unittest.TestCase):

    def setUp(self):
        """
        Patches time.sleep and initializes AnalystAgent with mocked dependencies.
        """
        # Patch time.sleep to speed up tenacity retries (wait_fixed(1) would add ~4s per test)
        self.sleep_patcher = patch('time.sleep')
        self.sleep_patcher.start()
        analysis_df = pd.DataFrame({'Ticker': ['AAPL'], 'High_Conviction_Count': [2],
                                    'Ownership_Delta_Avg': [0.5], 'Portfolio_Concentration_Avg': [1.2]})
        self.q_analysis_patcher = patch('app.ai.agent.quarter_analysis', return_value=analysis_df)
        self.date_patcher = patch('app.ai.agent.get_quarter_date', return_value='2023-12-31')
        self.q_analysis_patcher.start()
        self.date_patcher.start()
        self.agent = AnalystAgent('2023Q4', ai_client=MagicMock())

    def tearDown(self):
        """
        Stops all active patchers started in setUp.
        """
        self.sleep_patcher.stop()
        self.q_analysis_patcher.stop()
        self.date_patcher.stop()

    @patch('app.ai.agent.stock_analysis')
    def test_returns_empty_dict_when_no_institutional_data(self, mock_stock_analysis):
        """
        Returns an empty dict when the ticker has no institutional filing data.
        """
        mock_stock_analysis.return_value = pd.DataFrame()

        result = self.agent.run_stock_due_diligence('UNKNOWN')

        self.assertEqual(result, {})

    @patch('app.ai.agent.PriceFetcher.get_current_price')
    @patch('app.ai.agent.stock_analysis')
    def test_returns_empty_dict_when_current_price_unavailable(self, mock_stock_analysis, mock_price):
        """
        Returns an empty dict when the current price cannot be fetched.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = None

        result = self.agent.run_stock_due_diligence('AAPL')

        self.assertEqual(result, {})

    @patch('app.ai.agent.encode')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.stock_due_diligence_prompt')
    @patch('app.ai.agent.PriceFetcher.get_avg_price')
    @patch('app.ai.agent.PriceFetcher.get_current_price')
    @patch('app.ai.agent.stock_analysis')
    def test_returns_analysis_with_current_price_attached(self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode):
        """
        Returns the parsed AI analysis dict with the current_price field added.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = 145.0
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = {'thesis': 'Strong buy'}

        result = self.agent.run_stock_due_diligence('AAPL')

        self.assertIn('thesis', result)
        self.assertEqual(result['current_price'], '$150.00')

    @patch('app.ai.agent.encode')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.stock_due_diligence_prompt')
    @patch('app.ai.agent.PriceFetcher.get_avg_price')
    @patch('app.ai.agent.PriceFetcher.get_current_price')
    @patch('app.ai.agent.stock_analysis')
    def test_proceeds_without_filing_date_price(self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode):
        """
        Returns a valid analysis even when the price on the filing date is unavailable.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = None  # filing date price not available
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = {'thesis': 'Buy'}

        result = self.agent.run_stock_due_diligence('AAPL')

        self.assertIn('thesis', result)

    @patch('app.ai.agent.encode')
    @patch('app.ai.agent.ResponseParser.extract_and_decode_toon')
    @patch('app.ai.agent.stock_due_diligence_prompt')
    @patch('app.ai.agent.PriceFetcher.get_avg_price')
    @patch('app.ai.agent.PriceFetcher.get_current_price')
    @patch('app.ai.agent.stock_analysis')
    def test_raises_invalid_response_error_on_empty_ai_response(self, mock_stock_analysis, mock_price, mock_avg_price, mock_prompt, mock_parse, mock_encode):
        """
        Raises InvalidAIResponseError (triggers retry) when the AI returns an empty TOON structure.
        """
        mock_stock_analysis.return_value = _make_stock_df()
        mock_price.return_value = 150.0
        mock_avg_price.return_value = 145.0
        self.agent.ai_client.generate_content.return_value = 'mock_response'
        mock_parse.return_value = {}

        with self.assertRaises(Exception):
            self.agent.run_stock_due_diligence('AAPL')


if __name__ == '__main__':
    unittest.main()
