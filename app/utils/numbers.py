"""
Numeric helpers shared by the analysis layer.
"""

import math

# A corporate ratio -- a split factor, a depositary ratio -- is a ratio of small
# whole numbers. Bounding the numerator as well as the denominator is what keeps
# 249/50 from passing as "simple".
_MAX_NUMERATOR = 50
_MAX_DENOMINATOR = 10


def snap_to_simple_ratio(
    value: float,
    tolerance: float = 0.01,
    max_numerator: int = _MAX_NUMERATOR,
    max_denominator: int = _MAX_DENOMINATOR,
) -> float:
    """
    Rounds a measured ratio to the nearest simple rational, preferring the
    smallest denominator and returning it unchanged when none is within
    tolerance.
    """
    if value <= 0:
        return value

    limit = math.log(1 + tolerance)
    for denominator in range(1, max_denominator + 1):
        numerator = round(value * denominator)
        if not 1 <= numerator <= max_numerator:
            continue
        candidate = numerator / denominator
        if abs(math.log(candidate / value)) <= limit:
            return candidate
    return value
