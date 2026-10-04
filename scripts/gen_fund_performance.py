"""
Generate database/fund_performance.csv — each tracked fund's quarterly
Holding-Based Return against the S&P 500.

The result is bundled into the static GitHub Pages build and drawn on every
fund page. Price lookups share the backtest's __pricecache__/, so a re-run after
a new quarter only fetches the new window's prices.

Regenerate:
    pipenv run gen-fund-performance
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.analysis.fund_performance import rebuild_fund_performance  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    """
    Rebuild the per-fund performance CSV from every available quarter.
    """
    logger.progress("Rebuilding per-fund quarterly performance...")
    path = rebuild_fund_performance()
    logger.success("Fund performance written to %s", path)


if __name__ == "__main__":
    main()
