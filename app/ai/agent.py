from datetime import date

import pandas as pd
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from toon_format import encode

from app.ai.clients import AIClient
from app.ai.clients.base_client import InvalidAIResponseError
from app.ai.promise_score_validator import PromiseScoreValidator, normalize_weights
from app.ai.prompts import (
    DUE_DILIGENCE_SCHEMA,
    SCORES_SCHEMA,
    SENTIMENTS,
    WEIGHTS_SCHEMA,
    promise_score_weights_prompt,
    quantitative_scores_prompt,
    stock_due_diligence_prompt,
)
from app.ai.response_parser import ResponseParser
from app.analysis.performance_evaluator import PerformanceEvaluator
from app.analysis.price_scores import NEUTRAL_SCORE, compute_price_scores
from app.analysis.stocks import quarter_analysis, stock_analysis
from app.stocks.libraries import YFinance
from app.stocks.price_fetcher import PriceFetcher
from app.utils.logger import get_logger, log_safe
from app.utils.strings import get_quarter_date

logger = get_logger(__name__)


class AnalystAgent:
    """
    AI-powered analyst agent that interprets 13F data to generate strategic insights
    """

    def __init__(self, quarter: str, ai_client: AIClient | None = None):
        self.quarter = quarter
        self.ai_client = ai_client
        self.filing_date = get_quarter_date(quarter)
        self.analysis_df = quarter_analysis(self.quarter)

    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(7),
        before_sleep=lambda rs: logger.progress(
            "%s. Retrying in %.0fs...",
            log_safe(rs.outcome.exception(), max_len=300),  # type: ignore[union-attr]
            rs.next_action.sleep,  # type: ignore[union-attr]
        ),
    )
    def _get_promise_score_weights(self) -> dict:
        """
        Uses the LLM to determine the optimal weights for the Promise Score.
        Retries with tenacity if the weights or metrics are invalid.
        """
        assert self.ai_client is not None, "AnalystAgent requires an AIClient"
        logger.progress(
            "Sending request to AI (%s) for Promise Score weighting strategy...",
            self.ai_client.get_model_name(),
        )
        prompt = promise_score_weights_prompt(self.quarter)

        response_text = self.ai_client.generate_content(prompt, response_schema=WEIGHTS_SCHEMA)
        parsed_weights = self._weights_from_response(ResponseParser.parse_json(response_text))

        invalid_metrics = PromiseScoreValidator.validate_metrics(list(parsed_weights.keys()))
        if invalid_metrics:
            raise InvalidAIResponseError(f"AI returned invalid metrics: {invalid_metrics}")

        count_error = PromiseScoreValidator.validate_metric_count(parsed_weights)
        if count_error:
            raise InvalidAIResponseError(count_error)

        value_errors = PromiseScoreValidator.validate_weight_values(parsed_weights)
        if value_errors:
            raise InvalidAIResponseError(f"AI returned invalid weight values: {value_errors}")

        wrong_signs = PromiseScoreValidator.validate_weight_signs(parsed_weights)
        if wrong_signs:
            raise InvalidAIResponseError(f"AI returned wrongly signed weights: {wrong_signs}")

        normalized = normalize_weights(parsed_weights)
        weights_str = "\n\t" + "\n\t".join(
            f"{k:<28} raw = {v:7.3f}   normalized = {normalized[k]:6.3f}"
            for k, v in parsed_weights.items()
        )
        logger.success("AI Agent selected weights:%s", weights_str)
        return parsed_weights

    @staticmethod
    def _weights_from_response(response: dict) -> dict[str, float]:
        """
        Converts the ``weights`` list of {metric, weight} items into a metric->weight dict.

        Raises:
            InvalidAIResponseError: If the list is missing or malformed, a weight is
                not numeric, or a metric appears twice.
        """
        items = response.get("weights")
        if not isinstance(items, list) or not all(
            isinstance(item, dict) and "metric" in item and "weight" in item for item in items
        ):
            raise InvalidAIResponseError("AI response has no valid list of weights")

        weights: dict[str, float] = {}
        for item in items:
            metric = str(item["metric"])
            if metric in weights:
                raise InvalidAIResponseError(f"AI returned metric {metric} more than once")
            try:
                weights[metric] = float(item["weight"])
            except (TypeError, ValueError) as e:
                raise InvalidAIResponseError(f"AI returned non-numeric weight value: {e}") from e
        return weights

    @staticmethod
    def _scores_from_response(response: dict) -> dict[str, dict]:
        """
        Converts the ``stocks`` list into a dict keyed by ticker, without the ticker field.

        Raises:
            InvalidAIResponseError: If the list is missing, an entry is not an object
                with a ticker, or a ticker appears twice.
        """
        entries = response.get("stocks")
        if not isinstance(entries, list) or not entries:
            raise InvalidAIResponseError("AI returned no data")
        if not all(isinstance(entry, dict) and "ticker" in entry for entry in entries):
            raise InvalidAIResponseError("AI response entries are not key/value blocks")

        scores: dict[str, dict] = {}
        for entry in entries:
            fields = dict(entry)
            ticker = str(fields.pop("ticker"))
            if ticker in scores:
                raise InvalidAIResponseError(
                    f"AI returned ticker {log_safe(ticker)} more than once"
                )
            scores[ticker] = fields
        return scores

    @staticmethod
    def _validate_due_diligence(response: dict) -> None:
        """
        Checks the sections are objects and every sentiment is a known value or null.

        Raises:
            InvalidAIResponseError: On a non-object section or an unknown sentiment.
        """
        for section_name in ("analysis", "investment_thesis"):
            section = response.get(section_name)
            if section is None:
                continue
            if not isinstance(section, dict):
                raise InvalidAIResponseError(f"AI returned a non-object {section_name}")
            field_schemas = DUE_DILIGENCE_SCHEMA["properties"][section_name]["properties"]
            for key, value in section.items():
                is_sentiment = "enum" in field_schemas.get(key, {})
                if is_sentiment and value is not None and value not in SENTIMENTS:
                    raise InvalidAIResponseError(f"AI returned an invalid {key}: {log_safe(value)}")

    @staticmethod
    def _is_informative(values: pd.Series) -> bool:
        """
        Whether a metric separates stocks at all: it needs two or more distinct non-NaN values.
        """
        return values.dropna().nunique() > 1

    @staticmethod
    def _rank_column(values: pd.Series) -> pd.Series:
        """
        Maps a metric onto [0, 1] by min-rank, so the minimum and its ties get 0.

        NaN values and constant columns (including a single stock) rank as a neutral 0.5.
        """
        if not AnalystAgent._is_informative(values):
            return pd.Series(0.5, index=values.index)
        ranks = (values.rank(method="min") - 1) / (values.count() - 1)
        return ranks.fillna(0.5)

    def _calculate_promise_scores(self, df: pd.DataFrame, promise_weights: dict) -> pd.DataFrame:
        """
        Calculates the Promise Score on a 0-100 scale from rank-transformed metrics.

        Weights are normalized over the informative metrics present in the frame, i.e.
        excluding missing and constant columns. The score is
        100 * (sum_i w_i * r_i + sum of |w_j| over negative w_j), so the best possible stock
        scores 100 and the worst 0; with no informative metric every stock scores 50.

        Raises:
            ValueError: If none of the weighted metrics is present in the frame.
        """
        df = df.copy()
        present: dict[str, float] = {}
        for metric, weight in promise_weights.items():
            if metric in df.columns:
                present[metric] = weight
            else:
                logger.warning(
                    "Metric '%s' suggested by AI not found in analysis data. Skipping.",
                    log_safe(metric),
                )
        if not present:
            raise ValueError("None of the weighted metrics is present in the analysis data")

        informative: dict[str, float] = {}
        for metric, weight in present.items():
            df[f"{metric}_rank"] = self._rank_column(df[metric])
            if self._is_informative(df[metric]):
                informative[metric] = weight

        if not informative:
            df["Promise_Score"] = 50.0
            return df

        weights = normalize_weights(informative)
        score = sum(df[f"{m}_rank"] * w for m, w in weights.items())
        offset = sum(-w for w in weights.values() if w < 0)
        df["Promise_Score"] = 100 * (score + offset)
        return df

    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(5),
        before_sleep=lambda rs: logger.progress(
            "%s. Retrying in %.0fs...",
            log_safe(rs.outcome.exception(), max_len=300),  # type: ignore[union-attr]
            rs.next_action.sleep,  # type: ignore[union-attr]
        ),
    )
    def _get_ai_scores(self, stocks_context: list[dict]) -> dict:
        """
        Uses the LLM to classify each stock's industry and score its fundamental risk.
        Retries with tenacity if the response is invalid.
        """
        assert self.ai_client is not None, "AnalystAgent requires an AIClient"
        prompt = quantitative_scores_prompt(encode(stocks_context), self.filing_date)
        required_keys = ["risk_score"]

        logger.progress(
            "Sending request to AI (%s) for thematic scores...", self.ai_client.get_model_name()
        )
        response_text = self.ai_client.generate_content(prompt, response_schema=SCORES_SCHEMA)
        parsed_data = self._scores_from_response(ResponseParser.parse_json(response_text))

        if not all(all(key in data for key in required_keys) for data in parsed_data.values()):
            raise InvalidAIResponseError("AI response was missing required keys")

        for data in parsed_data.values():
            for key in required_keys:
                value = data[key]
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise InvalidAIResponseError(f"AI returned a non-numeric {key}")
                if not 1 <= value <= 100:
                    raise InvalidAIResponseError(f"AI returned an out-of-range {key}")

        # A truncated stream decodes to a valid prefix: without this check the
        # missing tickers would silently score 0 downstream.
        missing = {stock["ticker"] for stock in stocks_context} - parsed_data.keys()
        if missing:
            raise InvalidAIResponseError(f"AI response is missing {len(missing)} ticker(s)")

        logger.success("Successfully parsed AI scores for %d tickers", len(parsed_data))
        return parsed_data

    def _compute_autonomous_scores(self, tickers: list[str]) -> dict:
        """
        Compute the non-LLM half of the scored list: fetch programmatic data
        (YFinance industry/price) and derive the growth score per ticker.
        """
        logger.progress(
            "Fetching programmatic data for %d tickers from YFinance...", len(tickers), emoji="🔍"
        )
        stocks_info = YFinance.get_stocks_info(tickers)

        autonomous_scores = {}
        for ticker in tickers:
            info = stocks_info.get(ticker, {})
            current_price = info.get("price")
            # The prompt asks the LLM to refine this into a Yahoo Finance industry,
            # so hand it the industry when YFinance has one and the sector otherwise.
            industry = info.get("industry") or info.get("sector")
            filing_price: float | None = None
            pct_change: float | None = None
            growth_score: float | None = None

            if current_price:
                filing_price = PriceFetcher.get_avg_price(
                    ticker, date.fromisoformat(self.filing_date)
                )
                if filing_price:
                    pct_change = ((float(current_price) - filing_price) / filing_price) * 100
                    growth_score = PerformanceEvaluator.calculate_growth_score(pct_change)

            autonomous_scores[ticker] = {
                "Industry": industry or "N/A",
                "Growth_Score": growth_score if growth_score is not None else "N/A",
                "Current_Price": f"${current_price:,.2f}" if current_price else "N/A",
                "Filing_Price": f"${filing_price:,.2f}" if filing_price else "N/A",
                "Pct_Change": f"{pct_change:+.2f}%" if pct_change is not None else "N/A",
            }
        return autonomous_scores

    def _build_stocks_context(
        self, tickers: list[str], suggestions_df: pd.DataFrame, autonomous_scores: dict
    ) -> list[dict]:
        """
        Assemble the per-ticker context list handed to the LLM scorer.
        """
        return [
            {
                "ticker": ticker,
                "company": suggestions_df[suggestions_df["Ticker"] == ticker]["Company"].iloc[0],
                "industry": autonomous_scores[ticker]["Industry"],
                "filing_date": self.filing_date,
                "filing_price": autonomous_scores[ticker]["Filing_Price"],
                "current_price": autonomous_scores[ticker]["Current_Price"],
                "price_change_since_filing": autonomous_scores[ticker]["Pct_Change"],
            }
            for ticker in tickers
        ]

    def generate_scored_list(self, top_n: int) -> pd.DataFrame:
        """
        Generates a scored and ranked list of the most promising stocks based on a heuristic model
        """
        try:
            # Let the LLM define the weights for the Promise score
            promise_weights = self._get_promise_score_weights()
        except RetryError:
            logger.error(
                "Failed to get valid promise score weights after multiple attempts",
                exc_info=True,
            )
            return pd.DataFrame()

        try:
            df = self._calculate_promise_scores(self.analysis_df, promise_weights)
        except ValueError:
            logger.error("Failed to calculate promise scores", exc_info=True)
            return pd.DataFrame()
        suggestions_df = df.sort_values(by="Promise_Score", ascending=False).head(top_n)

        tickers = suggestions_df["Ticker"].tolist()
        if not tickers:
            return suggestions_df

        suggestions_df = suggestions_df.copy()
        autonomous_scores = self._compute_autonomous_scores(tickers)

        # The LLM overwrites Industry/Risk below; if it fails these seeded defaults remain.
        suggestions_df["Industry"] = suggestions_df["Ticker"].map(
            lambda t: autonomous_scores.get(t, {}).get("Industry", "N/A")
        )
        suggestions_df["Growth_Score"] = suggestions_df["Ticker"].map(
            lambda t: autonomous_scores.get(t, {}).get("Growth_Score", 0)
        )
        suggestions_df["Risk_Score"] = 0
        price_scores = compute_price_scores(tickers)
        for column in ("Momentum_Score", "Low_Volatility_Score"):
            suggestions_df[column] = [
                int(price_scores.get(t, {}).get(column, NEUTRAL_SCORE)) for t in tickers
            ]

        stocks_context = self._build_stocks_context(tickers, suggestions_df, autonomous_scores)
        try:
            ai_scores_data = self._get_ai_scores(stocks_context)
        except RetryError:
            logger.error("Failed to get valid AI scores after multiple attempts", exc_info=True)
            return suggestions_df

        suggestions_df["Industry"] = suggestions_df["Ticker"].map(
            lambda t: (
                ai_scores_data.get(t, {}).get("industry")
                or autonomous_scores.get(t, {}).get("Industry", "N/A")
            )
        )
        suggestions_df["Risk_Score"] = suggestions_df["Ticker"].map(
            lambda t: ai_scores_data.get(t, {}).get("risk_score", 0)
        )
        return suggestions_df

    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(5),
        before_sleep=lambda rs: logger.progress(
            "%s. Retrying in %.0fs...",
            log_safe(rs.outcome.exception(), max_len=300),  # type: ignore[union-attr]
            rs.next_action.sleep,  # type: ignore[union-attr]
        ),
    )
    def run_stock_due_diligence(self, ticker: str) -> dict:
        """
        Performs AI-powered due diligence on a single stock.

        Args:
            ticker (str): The stock ticker to analyze.

        Returns:
            dict: A dictionary containing the AI's analysis, or an empty dict if an error occurs.
        """
        assert self.ai_client is not None, "AnalystAgent requires an AIClient"

        stock_data = self._build_due_diligence_context(ticker)
        if stock_data is None:
            return {}

        stock_context_toon = encode(stock_data)
        logger.progress(
            "Sending request to AI (%s) for due diligence on %s...",
            self.ai_client.get_model_name(),
            log_safe(ticker),
        )
        prompt = stock_due_diligence_prompt(stock_context_toon)
        response_text = self.ai_client.generate_content(
            prompt, reasoning="medium", response_schema=DUE_DILIGENCE_SCHEMA
        )
        parsed_data = ResponseParser.parse_json(response_text)

        if not parsed_data:
            raise InvalidAIResponseError("AI returned an empty or invalid JSON object")
        self._validate_due_diligence(parsed_data)

        parsed_data["current_price"] = stock_data["current_price"]
        parsed_data["filing_date_price"] = stock_data["filing_date_price"]
        parsed_data["price_delta_percentage"] = stock_data["price_delta_percentage"]

        return parsed_data

    def _build_due_diligence_context(self, ticker: str) -> dict | None:
        """
        Gather the institutional + price context for one ticker, formatted for
        the LLM. Returns None (caller aborts) when the ticker has no filing data
        for the quarter or no current price can be fetched.
        """
        logger.progress(
            "Gathering institutional data for %s for quarter %s...", log_safe(ticker), self.quarter
        )
        stock_df = stock_analysis(ticker, self.quarter)

        if stock_df.empty:
            logger.error(
                "No data found for ticker %s in quarter %s.", log_safe(ticker), self.quarter
            )
            return None

        current_price = PriceFetcher.get_current_price(ticker)
        if current_price is None:
            logger.error(
                "Could not fetch current price for %s. Aborting due diligence.", log_safe(ticker)
            )
            return None
        logger.money("Current price for %s: $%s", log_safe(ticker), f"{current_price:,.2f}")

        filing_date_price = PriceFetcher.get_avg_price(ticker, date.fromisoformat(self.filing_date))
        price_delta_pct = None
        if filing_date_price:
            logger.info(
                "Price on filing date (%s): $%s",
                self.filing_date,
                f"{filing_date_price:,.2f}",
                emoji="💲",
            )
            price_delta_pct = ((current_price - filing_date_price) / filing_date_price) * 100
            logger.info(
                "Price change since filing: %s",
                f"{price_delta_pct:+.2f}%",
                emoji=("📈" if price_delta_pct >= 0 else "📉"),
            )

        total_value = stock_df["Value"].sum()
        total_delta_value = stock_df["Delta_Value"].sum()
        previous_total_value = total_value - total_delta_value
        delta_pct = (
            total_delta_value / previous_total_value * 100 if previous_total_value != 0 else 0
        )

        # Get summary metrics for this ticker
        summary_row = (
            self.analysis_df[self.analysis_df["Ticker"] == ticker].iloc[0]
            if not self.analysis_df[self.analysis_df["Ticker"] == ticker].empty
            else None
        )

        return {
            "ticker": ticker,
            "company": stock_df["Company"].iloc[0],
            "filing_date": self.filing_date,
            "current_date": date.today().isoformat(),
            "filing_date_price": f"${filing_date_price:,.2f}" if filing_date_price else "N/A",
            "current_price": f"${current_price:,.2f}",
            "price_delta_percentage": f"{price_delta_pct:+.2f}%"
            if price_delta_pct is not None
            else "N/A",
            "institutional_activity": {
                "total_value_held": f"${total_value:,.0f}",
                "net_change_in_value": f"${total_delta_value:,.0f}",
                "delta_percentage": f"{delta_pct:+.2f}%",
                "buyers": int((stock_df["Delta_Value"] > 0).sum()),
                "sellers": int((stock_df["Delta_Value"] < 0).sum()),
                "new_positions": int((stock_df["Delta"].str.startswith("NEW")).sum()),
                "closed_positions": int((stock_df["Delta"] == "CLOSE").sum()),
                "high_conviction_new_entries": int(summary_row["High_Conviction_Count"])
                if summary_row is not None
                else 0,
                "ownership_delta_avg": f"{summary_row['Ownership_Delta_Avg']:+.2f}%"
                if summary_row is not None
                else "0.00%",
                "portfolio_concentration_avg": f"{summary_row['Portfolio_Concentration_Avg']:.2f}%"
                if summary_row is not None
                else "0.00%",
            },
        }
