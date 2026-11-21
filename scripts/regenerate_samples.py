"""
Regenerates the static sample JSON files served by the GH Pages build.

Outputs:
- app/frontend/src/data/sampleRanking.json (top promising stocks for the latest quarter)
- app/frontend/src/data/sampleDueDiligence.json (full AI due diligence for the ranking's top stock)

Both samples are regenerated with the default provider/model from
database/models.csv (Google Gemini) and include a `generated_at` ISO date
for display in the UI.

Run locally with the project's .env loaded:
    pipenv run python -X utf8 scripts/regenerate_samples.py
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

import contextlib  # noqa: E402

from app.ai.agent import AnalystAgent  # noqa: E402
from app.ai.clients.google_client import GoogleAIClient  # noqa: E402
from app.database import get_last_quarter, get_most_recent_quarter  # noqa: E402
from app.stocks.price_fetcher import PriceFetcher  # noqa: E402

RANKING_TOP_N = 10
MODEL_ID = GoogleAIClient.DEFAULT_MODEL

SAMPLE_RANKING_PATH = ROOT / "app/frontend/src/data/sampleRanking.json"
SAMPLE_DD_PATH = ROOT / "app/frontend/src/data/sampleDueDiligence.json"


def _coerce(value):
    """
    Convert pandas/numpy scalars to JSON-serializable Python primitives.
    """
    if value is None:
        return None
    if hasattr(value, "item"):
        with contextlib.suppress(ValueError, AttributeError):
            value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def regenerate_ranking() -> None:
    """
    Build the sample ranking JSON for the latest quarter using the default model.
    """
    quarter = get_last_quarter()
    print(f"\n=== Regenerating ranking sample for {quarter} ===")
    agent = AnalystAgent(quarter, ai_client=GoogleAIClient(model=MODEL_ID))
    df = agent.generate_scored_list(RANKING_TOP_N)
    if df.empty:
        raise RuntimeError("Empty ranking result; aborting.")

    fields = [
        "Ticker",
        "Company",
        "Promise_Score",
        "Momentum_Score",
        "Low_Volatility_Score",
        "Risk_Score",
        "Growth_Score",
        "Total_Value",
        "Holder_Count",
        "Net_Buyers",
        "High_Conviction_Count",
    ]
    stocks = [
        {f: _coerce(row.get(f)) for f in fields if f in row.index} for _, row in df.iterrows()
    ]

    payload = {
        "quarter": quarter,
        "generated_at": date.today().isoformat(),
        "stocks": stocks,
    }
    SAMPLE_RANKING_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    print(f"✅ Wrote {SAMPLE_RANKING_PATH.relative_to(ROOT)} ({len(stocks)} stocks)")


def top_ranked_ticker() -> str:
    """
    Return the ticker with the highest Promise Score in the saved sample ranking, so
    the due-diligence sample covers the stock the ranking page puts first.
    """
    ranking = json.loads(SAMPLE_RANKING_PATH.read_text(encoding="utf-8"))
    return max(ranking["stocks"], key=lambda s: s["Promise_Score"])["Ticker"]


def regenerate_due_diligence(ticker: str) -> None:
    """
    Build the sample due-diligence JSON for the given ticker using the default model.
    """
    quarter = get_most_recent_quarter(ticker) or get_last_quarter()
    print(f"\n=== Regenerating due-diligence sample for {ticker} ({quarter}) ===")
    agent = AnalystAgent(quarter, ai_client=GoogleAIClient(model=MODEL_ID))
    analysis = agent.run_stock_due_diligence(ticker)
    if not analysis:
        raise RuntimeError(f"No analysis produced for {ticker}.")

    # The chart on the sample page has no backend to call, so the 5y weekly
    # OHLC series is baked in from the same fetcher the /history endpoint uses.
    price_history = PriceFetcher.get_history(ticker, "5y")
    if not price_history:
        raise RuntimeError(f"No price history for {ticker}.")

    payload = {
        "quarter": quarter,
        "generated_at": date.today().isoformat(),
        **analysis,
        "price_history": price_history,
    }
    SAMPLE_DD_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    print(f"✅ Wrote {SAMPLE_DD_PATH.relative_to(ROOT)} ({analysis.get('ticker')})")


if __name__ == "__main__":
    regenerate_ranking()
    regenerate_due_diligence(top_ranked_ticker())
    print("\nDone.")
