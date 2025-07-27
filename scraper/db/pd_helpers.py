import pandas as pd

def coalesce(s: pd.Series, *series: pd.Series) -> pd.Series:
    """
    Returns the first non-null value at each position from a set of Series.
    It's an equivalent of SQL's COALESCE.
    """
    for other in series:
        s = s.fillna(other)
    return s
