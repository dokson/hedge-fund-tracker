"""
Generate database/strategy_performance.csv — the Avg Portfolio backtest artifact.

Runs the strategy's screen reconstruction and forward returns vs SPY over every
consolidated quarter, writing one row per window. The result is bundled into the
static GitHub Pages build and read directly by the frontend (no backend / price
fetching in the browser). Price lookups are cached under __pricecache__/ so a
re-run after changing the tracked-fund list completes near-instantly.

Regenerate:
    pipenv run python -X utf8 scripts/gen_strategy_performance.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.backtest.report import rebuild_strategy_performance  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    """
    Rebuild the strategy-performance CSV from the available quarters.
    """
    logger.progress("Rebuilding strategy performance (Avg Portfolio)...")
    path = rebuild_strategy_performance()
    logger.success("Strategy performance written to %s", path)


if __name__ == "__main__":
    main()
