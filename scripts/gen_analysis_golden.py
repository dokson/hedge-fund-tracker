"""
Generate the shared golden fixture for the quarter-analysis equivalence tests.

The Python stock-level analysis is the source of truth. This script runs the
real chain (flags -> aggregate -> derived metrics) over a hand-built set of
per-(fund, ticker) holdings and writes input + expected output to
tests/fixtures/analysis_golden.json. Both the Python regression test and the
TypeScript equivalence test assert against this file, so a drift between the
two implementations fails CI.

Regenerate after an intentional analysis-logic change:
    pipenv run python -X utf8 scripts/gen_analysis_golden.py
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from app.analysis.stocks import (  # noqa: E402
    _aggregate_stock_data,
    _calculate_derived_metrics,
    _calculate_fund_level_flags,
)

FIXTURE = ROOT / "tests" / "fixtures" / "analysis_golden.json"

# Per-(fund, ticker) holdings: the input to the stock-level analysis after the
# CUSIP->ticker aggregation and per-fund rank/concentration assignment.
INPUT = [
    # AAA: a new high-conviction holder + an existing accumulating buyer.
    {
        "Fund": "FundX",
        "Ticker": "AAA",
        "Company": "Alpha",
        "Shares": 100,
        "Delta_Shares": 100,
        "Value": 1000,
        "Delta_Value": 1000,
        "Portfolio_Pct": 5.0,
        "Portfolio_Pct_Rank": 1,
        "Fund_Concentration_Ratio": 40.0,
        "Shares_Delta_Pct": 0.0,
    },
    {
        "Fund": "FundY",
        "Ticker": "AAA",
        "Company": "Alpha",
        "Shares": 200,
        "Delta_Shares": 50,
        "Value": 2000,
        "Delta_Value": 500,
        "Portfolio_Pct": 2.0,
        "Portfolio_Pct_Rank": 15,
        "Fund_Concentration_Ratio": 30.0,
        "Shares_Delta_Pct": 33.3333,
    },
    # BBB: a single fund fully closed the position (tests CLOSE + ratio=0 path).
    {
        "Fund": "FundX",
        "Ticker": "BBB",
        "Company": "Bravo",
        "Shares": 0,
        "Delta_Shares": -80,
        "Value": 0,
        "Delta_Value": -800,
        "Portfolio_Pct": 0.0,
        "Portfolio_Pct_Rank": 99,
        "Fund_Concentration_Ratio": 40.0,
        "Shares_Delta_Pct": 0.0,
    },
    # CCC: sole holder, brand-new (tests the all-new delta=Infinity branch).
    {
        "Fund": "FundZ",
        "Ticker": "CCC",
        "Company": "Charlie",
        "Shares": 50,
        "Delta_Shares": 50,
        "Value": 500,
        "Delta_Value": 500,
        "Portfolio_Pct": 10.0,
        "Portfolio_Pct_Rank": 2,
        "Fund_Concentration_Ratio": 50.0,
        "Shares_Delta_Pct": 0.0,
    },
]

# Stock-level output columns compared across implementations, mapped to the
# camelCase keys the TypeScript side produces.
COLUMN_MAP = {
    "Total_Value": "totalValue",
    "Total_Delta_Value": "totalDeltaValue",
    "Max_Portfolio_Pct": "maxPortfolioPct",
    "Avg_Portfolio_Pct": "avgPortfolioPct",
    "Buyer_Count": "buyerCount",
    "Seller_Count": "sellerCount",
    "Holder_Count": "holderCount",
    "New_Holder_Count": "newHolderCount",
    "Close_Count": "closeCount",
    "High_Conviction_Count": "highConvictionCount",
    "Net_Buyers": "netBuyers",
    "Buyer_Seller_Ratio": "buyerSellerRatio",
    "Ownership_Delta_Avg": "ownershipDeltaAvg",
    "Avg_Fund_Concentration": "fundConcentrationAvg",
    "Delta": "delta",
}


def _jsonable(value: float) -> object:
    """
    Round floats to 4 dp and render non-finite values as the string the test
    harness maps back to Infinity (JSON has no Infinity literal).
    """
    if isinstance(value, (int, float)) and not math.isfinite(value):
        return "Infinity"
    return round(float(value), 4)


def main() -> None:
    """
    Build the golden fixture from the Python analysis chain.
    """
    df = pd.DataFrame(INPUT)
    result = _calculate_derived_metrics(_aggregate_stock_data(_calculate_fund_level_flags(df)))

    expected = {}
    for _, row in result.iterrows():
        expected[row["Ticker"]] = {
            camel: _jsonable(row[py_col]) for py_col, camel in COLUMN_MAP.items()
        }

    FIXTURE.write_text(
        json.dumps({"input": INPUT, "expected": expected}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {FIXTURE} ({len(expected)} tickers)")


if __name__ == "__main__":
    main()
