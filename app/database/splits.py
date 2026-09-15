"""
Persistence for the detected stock-split registry (``splits.csv``).

The registry is small and hand-inspectable on purpose: a split restates every
holder's share count for a quarter, so a wrong entry is worth catching by eye,
and a missed one is worth adding by hand.
"""

import pandas as pd

import app.database as _db
from app.database import SPLITS_FILE
from app.utils.logger import get_logger
from app.utils.pd import atomic_to_csv

logger = get_logger(__name__)

__all__ = [
    "load_split_factors",
    "save_split_factors",
]

_COLUMNS = ["Quarter", "Date", "CUSIP", "Ticker", "Factor"]


def _load_registry() -> pd.DataFrame:
    """
    Reads the split registry as stored, empty when it is absent or unreadable.
    """
    filepath = _db._safe_db_join(SPLITS_FILE)
    if not filepath.is_file():
        return pd.DataFrame(columns=_COLUMNS)

    try:
        return pd.read_csv(filepath, dtype={"Quarter": str, "CUSIP": str, "Ticker": str})
    except OSError, pd.errors.ParserError, pd.errors.EmptyDataError:
        logger.error("while reading the split registry '%s'", SPLITS_FILE, exc_info=True)
        return pd.DataFrame(columns=_COLUMNS)


def load_split_factors() -> dict[str, dict[str, float]]:
    """
    Loads the split registry as quarter -> CUSIP -> factor, empty when no
    registry has been generated yet.
    """
    registry = _load_registry()
    if registry.empty:
        return {}

    factors: dict[str, dict[str, float]] = {}
    for quarter, cusip, factor in zip(
        registry["Quarter"], registry["CUSIP"], registry["Factor"], strict=True
    ):
        factors.setdefault(str(quarter), {})[str(cusip)] = float(factor)
    return factors


def save_split_factors(
    splits: list[dict[str, object]], replacing: list[str] | None = None
) -> None:
    """
    Writes the split registry, ordered by quarter then CUSIP so regenerating it
    leaves the committed file's history append-only.

    ``replacing`` names the quarters this call rescanned: their rows are
    dropped and every other quarter is carried over. Omit it to rewrite all.
    """
    fresh = pd.DataFrame(splits, columns=_COLUMNS)

    if replacing is not None:
        kept = _load_registry()
        if not kept.empty:
            kept = kept[~kept["Quarter"].isin(replacing)]
            fresh = pd.concat([kept, fresh], ignore_index=True)

    registry = fresh.sort_values(["Quarter", "CUSIP"], kind="stable")
    atomic_to_csv(registry, _db._safe_db_join(SPLITS_FILE), index=False)
