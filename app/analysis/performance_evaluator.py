from typing import Any

from app.analysis.fund_performance import (
    EVAL_TOP_N_POSITIONS,
    FactorsFn,
    MarketReturnFn,
    UniversePricesFn,
    cached_market_return,
    holding_based_return,
    position_returns,
    quarter_end,
    registry_split_factors,
    tracked_universe_prices,
)
from app.database import load_fund_holdings
from app.utils.logger import get_logger
from app.utils.strings import get_previous_quarter

logger = get_logger(__name__)


class PerformanceEvaluator:
    """
    Evaluates fund performance by calculating price-based returns of holdings,
    isolating management skill from capital flows.

    The Holding-Based Return is an approximation reconstructed from quarterly
    13F snapshots, not an audited track record. See
    `calculate_quarterly_performance` for the specific methodological
    limitations before using the numbers for ranking or comparison.
    """

    @staticmethod
    def calculate_growth_score(pct_change: float) -> int:
        """
        Calculates a Growth Potential score (1-100) based on price performance.
        High Score = High Potential (price has dropped).
        Low Score = Low Potential (price has run up).
        """
        if pct_change <= -40:
            return 100
        if pct_change <= -15:
            # Drop 15% to 40% -> Score 75 to 90
            return int(75 + (abs(pct_change) - 15) / (40 - 15) * 15)
        if pct_change <= -2:
            # Drop 2% to 15% -> Score 66 to 74
            return int(66 + (abs(pct_change) - 2) / (15 - 2) * 8)
        if pct_change <= 2:
            # Stable / Flat -2% to +2% -> Score 55 to 65
            return int(55 + (pct_change + 2) / 4 * 10)
        if pct_change <= 15:
            # Growth 2% to 15% -> Score 40 to 54
            return int(54 - (pct_change - 2) / (15 - 2) * 14)
        if pct_change <= 40:
            # Growth 15% to 40% -> Score 11 to 39
            return int(39 - (pct_change - 15) / (40 - 15) * 28)
        return 1

    @classmethod
    def calculate_quarterly_performance(
        cls,
        fund_name: str,
        target_quarter: str,
        *,
        split_factors_fn: FactorsFn | None = None,
        universe_prices_fn: UniversePricesFn | None = None,
        market_return_fn: MarketReturnFn | None = None,
    ) -> dict[str, Any]:
        """
        Calculates the Holding-Based Return (HBR) for a fund for the specified quarter.
        HBR = Σ (Weight_i * Return_i) over the top EVAL_TOP_N_POSITIONS positions held
        at the start of the quarter.

        The per-position math is ``app.analysis.fund_performance.position_returns``,
        the same code that builds the published per-fund series, so the CLI and the
        site report one number: split-corrected, exits priced from other funds'
        quarter-end filings, then from the cached market source.

        Limitations (the result is an approximation, not an audited return):
        - Price-only: dividends are ignored, so total return is understated for
          dividend-paying holdings.
        - Start-of-quarter snapshot only: positions opened during the quarter
          don't contribute, and intra-quarter timing of a sale is not captured.
        - Survivorship bias: only funds currently in the curated database are
          evaluable; funds that stopped filing or were dropped are absent.
        - US long equity only (13F scope): shorts, options, non-US and
          non-equity exposure are not reflected.
        """
        prev_quarter = get_previous_quarter(target_quarter)

        df_prev = load_fund_holdings(fund_name, prev_quarter)
        if df_prev.empty:
            return {"error": f"Missing data for {fund_name} in {prev_quarter} (Start of quarter)."}
        df_target = load_fund_holdings(fund_name, target_quarter)

        factors = (split_factors_fn or registry_split_factors())(prev_quarter, target_quarter)
        universe = (universe_prices_fn or tracked_universe_prices(load_fund_holdings))(
            target_quarter
        )
        df_eval = position_returns(
            df_prev,
            df_target,
            factors,
            market_return_fn or cached_market_return(),
            start=quarter_end(prev_quarter),
            end=quarter_end(target_quarter),
            universe_prices=universe,
            top_n=EVAL_TOP_N_POSITIONS,
        )
        fraction = holding_based_return(df_eval)
        if fraction is None:
            return {
                "error": "Total start value is zero after filtering",
                "fund": fund_name,
                "quarter": target_quarter,
            }

        total_start_value = float(
            df_prev[df_prev["Value"] > 0]
            .sort_values(by="Value", ascending=False)
            .head(EVAL_TOP_N_POSITIONS)["Value"]
            .sum()
        )
        portfolio_return = fraction * 100
        total_end_value = total_start_value * (1 + fraction)
        df_eval["Return"] = df_eval["Return"] * 100
        df_eval["Weighted_Return"] = df_eval["Weight"] * df_eval["Return"]

        top_contributors = (
            df_eval.sort_values(by="Weighted_Return", ascending=False)
            .head(10)[["Ticker", "Company", "Weight", "Return", "Weighted_Return"]]
            .to_dict("records")
        )
        top_detractors = (
            df_eval.sort_values(by="Weighted_Return", ascending=True)
            .head(10)[["Ticker", "Company", "Weight", "Return", "Weighted_Return"]]
            .to_dict("records")
        )

        return {
            "fund": fund_name,
            "quarter": target_quarter,
            "portfolio_return": portfolio_return,
            "start_value": total_start_value,
            "end_value": total_end_value,
            "top_contributors": top_contributors,
            "top_detractors": top_detractors,
        }
