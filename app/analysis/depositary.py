"""
Restating a 13D/G share count into the units of the US-listed security.

A 13D/G reports ownership of the class, so for a foreign issuer its count is in
ordinary shares while the listed line -- and every 13F -- is in depositary
receipts. The filing reports the stake twice, as a count and as a percentage of
the class, which against the listed shares outstanding gives the ratio.
"""

import math

from app.utils.numbers import snap_to_simple_ratio

# Below this it is a rounded percentage, not a ratio.
_MIN_RATIO = 1.5

# Above this, neighbouring whole ratios sit closer than the quotient's error.
_MAX_CONFIRMABLE_RATIO = 10

_MAX_PLAUSIBLE_RATIO = 1000
_RATIO_TOLERANCE = 0.04


def listed_units(
    filed_shares: float, class_pct: float | None, shares_outstanding: int | None
) -> int | None:
    """
    Restates a filed share count into the units of the listed security, or None
    when the filing is already in those units or the ratio cannot be confirmed.
    """
    if not filed_shares or filed_shares <= 0 or not shares_outstanding or shares_outstanding <= 0:
        return None
    if class_pct is None or math.isnan(class_pct) or not 0 < class_pct <= 100:
        return None

    stake_in_listed_units = (class_pct / 100) * shares_outstanding
    ratio = filed_shares / stake_in_listed_units
    if not _MIN_RATIO <= ratio <= _MAX_PLAUSIBLE_RATIO:
        return None

    if ratio <= _MAX_CONFIRMABLE_RATIO:
        confirmed = snap_to_simple_ratio(ratio, tolerance=_RATIO_TOLERANCE, max_denominator=1)
        if confirmed != ratio:
            return int(round(filed_shares / confirmed))

    units = int(round(stake_in_listed_units))
    return units if 0 < units <= shares_outstanding else None
