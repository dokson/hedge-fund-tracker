from app.utils.strings import VALUE_FORMAT_MAP
import numpy as np
import pandas as pd


def coalesce(*series: pd.Series) -> pd.Series:
    """
    Returns the first non-null value at each position from a set of Series.
    It's an equivalent of SQL's COALESCE.
    """
    result = series[0]
    for s in series[1:]:
        result = result.fillna(s)
    return result


def format_value_series(series: pd.Series) -> pd.Series:
    """
    Vectorized version of format_value.
    """
    # Base conditions for null and infinity
    conditions = [series.isnull(), series == float('inf')]
    choices = ['N/A', '∞']

    # Dynamically build conditions and choices from the rules
    for threshold, suffix in VALUE_FORMAT_MAP:
        conditions.append(series.abs() >= threshold)
        formatted_series = (series / threshold).map('{:.2f}'.format).str.rstrip('0').str.rstrip('.')
        choices.append(formatted_series + suffix)

    # The default choice is for numbers smaller than the lowest threshold
    result_array = np.select(conditions, choices, default=series.map('{:.2f}'.format).str.rstrip('0').str.rstrip('.'))
    return pd.Series(result_array, index=series.index)


def get_numeric_series(series: pd.Series) -> pd.Series:
    """
    Vectorized version of get_numeric.
    Parses a formatted value series (e.g., '1.23B', '45.67M') back into a numeric series.
    """
    # Ensure we are working with strings, and replace 'N/A' with NaN
    s = series.astype(str).str.strip().replace('N/A', np.nan)

    # Dynamically build conditions and multipliers from the rules
    conditions = []
    multipliers = []
    suffixes_to_strip = ''
    for multiplier, suffix in VALUE_FORMAT_MAP:
        conditions.append(s.str.endswith(suffix, na=False))
        multipliers.append(multiplier)
        suffixes_to_strip += suffix

    # Get the correct multiplier for each row, default is 1
    multiplier_series = np.select(conditions, multipliers, default=1)

    # Remove all possible suffixes, convert to numeric, and apply the multiplier
    numeric_part = pd.to_numeric(s.str.rstrip(suffixes_to_strip), errors='coerce')
    return numeric_part * multiplier_series


def get_percentage_number_series(series: pd.Series) -> pd.Series:
    """
    Vectorized version of get_percentage_number.
    Parses a formatted percentage string series (e.g., '12.3%', '<.01%') back into a numeric float series.
    """
    # Ensure we are working with strings and handle potential whitespace
    s = series.astype(str).str.strip()

    # Define conditions for special cases
    conditions = [s == 'N/A', s == '<.01%']
    choices = [np.nan, 0.0]

    # Default action: remove '%' and convert to numeric
    default = pd.to_numeric(s.str.replace('%', ''), errors='coerce')
    result_array = np.select(conditions, choices, default=default)
    return pd.Series(result_array, index=series.index)
