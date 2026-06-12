"""
Regression + equivalence guard for the stock-level analysis.

Asserts the Python chain reproduces the shared golden fixture
(tests/fixtures/analysis_golden.json). The TypeScript twin
(analysisEquivalence.test.ts) asserts the same file, so the two
implementations are pinned to identical output and cannot silently diverge.
Regenerate the fixture with scripts/gen_analysis_golden.py after an
intentional analysis-logic change.
"""

import json
import math
import unittest
from pathlib import Path

import pandas as pd

from app.analysis.stocks import (
    _aggregate_stock_data,
    _calculate_derived_metrics,
    _calculate_fund_level_flags,
)

_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "analysis_golden.json"

# Stock-level output column -> golden-fixture key.
_COLUMN_MAP = {
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


class TestAnalysisEquivalence(unittest.TestCase):
    def setUp(self):
        """
        Load the shared golden fixture and run the Python analysis chain.
        """
        data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        self.expected = data["expected"]
        df = pd.DataFrame(data["input"])
        result = _calculate_derived_metrics(_aggregate_stock_data(_calculate_fund_level_flags(df)))
        self.by_ticker = {row["Ticker"]: row for _, row in result.iterrows()}

    def test_tickers_match(self):
        """The chain emits exactly the fixture's tickers."""
        self.assertEqual(sorted(self.by_ticker), sorted(self.expected))

    def test_metrics_match_golden(self):
        """Every stock-level metric matches the golden value."""
        for ticker, expected in self.expected.items():
            row = self.by_ticker[ticker]
            for py_col, key in _COLUMN_MAP.items():
                with self.subTest(ticker=ticker, metric=key):
                    actual = row[py_col]
                    if expected[key] == "Infinity":
                        self.assertTrue(math.isinf(actual))
                    else:
                        self.assertAlmostEqual(float(actual), expected[key], places=4)


if __name__ == "__main__":
    unittest.main()
