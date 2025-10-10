import pandas as pd


def coalesce(s: pd.Series, *series: pd.Series) -> pd.Series:
    """
    Returns the first non-null value at each position from a set of Series.
    It's an equivalent of SQL's COALESCE.
    """
    result = s.copy()
    for other in series:
        result = result.where(~result.isnull(), other)
    return result
