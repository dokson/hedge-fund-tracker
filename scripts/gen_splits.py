"""
Generate database/splits.csv — the stock-split registry.

Records the securities whose filed share counts were restated by a split, so
comparisons can put both quarters on the same share basis (see
app/analysis/splits.py). The saved per-fund CSVs decide which securities are
worth a price-provider lookup; the provider decides whether a split happened.

Incremental by default: only the newest quarter is rescanned and the other
quarters keep their rows, because a provider sweep is paced and a full rebuild
costs hundreds of lookups.

    pipenv run gen-splits                  # newest quarter only
    pipenv run gen-splits 2026Q1 2026Q2    # named quarters
    pipenv run gen-splits --all            # every quarter on record
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.analysis.splits import (  # noqa: E402
    latest_scannable_quarter,
    rebuild_split_registry,
    scannable_quarters,
)
from app.database.splits import save_split_factors  # noqa: E402
from app.utils.logger import get_logger, log_safe  # noqa: E402

logger = get_logger(__name__)


def _requested_quarters(argv: list[str]) -> list[str] | None:
    """
    The quarters to scan: every one on record for --all, the named ones, or the
    newest by default. None means nothing is scannable.
    """
    if "--all" in argv:
        return scannable_quarters()

    named = [arg for arg in argv if not arg.startswith("-")]
    if named:
        return named

    latest = latest_scannable_quarter()
    return [latest] if latest else None


def main() -> None:
    """
    Rebuild the split registry for the requested quarters.
    """
    quarters = _requested_quarters(sys.argv[1:])
    if not quarters:
        logger.warning("No quarter has a predecessor on record; nothing to scan")
        return

    logger.progress("Scanning %s for splits...", log_safe(", ".join(quarters)))
    registry = rebuild_split_registry(quarters=quarters)
    save_split_factors(registry, replacing=quarters)
    logger.success(
        "Split registry updated: %s split(s) across %s quarter(s)", len(registry), len(quarters)
    )


if __name__ == "__main__":
    main()
