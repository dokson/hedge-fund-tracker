from datetime import datetime, timedelta
from typing import Union
import numpy as np
import pandas as pd

VALUE_FORMAT_MAP = [
    (1_000_000_000_000, 'T'),
    (1_000_000_000, 'B'),
    (1_000_000, 'M'),
    (1_000, 'K'),
]


def add_days_to_yyyymmdd(yyyymmdd_str, days):
    """
    Adds (or subtracts) a number of days to a date string in 'YYYYMMDD' format.

    Parameters:
        yyyymmdd_str (str): A date string in 'YYYYMMDD' format.
        days (int): Number of days to add (use negative value to subtract).

    Returns:
        str: New date string in 'YYYYMMDD' format.
    """
    return (datetime.strptime(yyyymmdd_str, "%Y%m%d") + timedelta(days=days)).strftime("%Y%m%d")


def get_next_yyyymmdd_day(yyyymmdd_str):
    """
    Adds one day to a date string in 'YYYYMMDD' format and returns the result in the same format.
    """
    return add_days_to_yyyymmdd(yyyymmdd_str, 1)


def format_percentage(value: float, show_sign: bool = False, decimal_places: int = 1) -> str:
    """
    Formats a numeric value as a percentage string:
    - Returns 'N/A' for null/NaN values.
    - Returns '∞' for infinite values.
    - Returns '<.01%' for values between 0 and 0.01 (exclusive).
    - Rounds to specified decimal_places and trims unnecessary zeros.
    - Optionally prepends sign when show_sign is True.

    Args:
        value (float): The percentage value to format. Can be NaN.
        show_sign (bool): Whether to prepend sign. Default is False.
        decimal_places (int): Number of decimal places to show. Default is 1.

    Returns:
        str: Formatted percentage string.
    """
    if pd.isnull(value):
        return 'N/A'
    elif isinstance(value, str):
        if not value.isnumeric():
            return value

    sign = '+' if show_sign else ''

    if value == float('inf'):
        return f"{sign}∞"
    elif 0 < value < 0.01 and not show_sign:
        return "<.01%"
    else:
        formatted = f'{value:{sign}.{decimal_places}f}'.rstrip('0').rstrip('.')
        return f"{formatted}%"


def format_string(string: str) -> str:
    """
    Formats a string to title case only if it is entirely in uppercase.

    - If the string consists only of uppercase letters and whitespace,
      it is converted to title case (e.g., "ETSY INC" -> "Etsy Inc").
    - If the string contains any lowercase letters or is already in a mixed case,
      it is returned unchanged (e.g., "GE HealthCare" -> "GE HealthCare").

    Args:
        input_string (str): The string to process.

    Returns:
        str: The formatted string or the original string.
    """
    if string and string.isupper():
        return string.title()
    return string


def format_value(value: Union[int, float]) -> str:
    """
    Formats a numeric value into a human-readable short scale string, up to 2 decimal places (e.g., 1.23B, 45.67M, 8.9K).
    Handles NA/NaN values by returning 'N/A'.

    Args:
        value (int or float): The numeric value to format.

    Returns:
        str: Formatted string.
    """
    if pd.isnull(value):
        return 'N/A'

    if value == float('inf'):
        return '∞'

    for threshold, suffix in VALUE_FORMAT_MAP:
        if abs(value) >= threshold:
            formatted = f'{value / threshold:.2f}'.rstrip('0').rstrip('.')
            return f"{formatted}{suffix}"

    return f'{value:.2f}'.rstrip('0').rstrip('.')


def get_percentage_formatter():
    """
    Creates a formatter function for converting numbers to a percentage string with 2 decimal places.

    This is a factory function that returns a lambda. The lambda expects a numeric value
    and formats it using the `format_percentage` utility with a fixed precision of 2 decimal places.
    Useful for applying consistent percentage formatting to data columns.

    Returns:
        callable: A function that takes a numeric value and returns its formatted percentage string.
    """
    return lambda x: format_percentage(x, decimal_places=2)


def get_signed_perc_formatter():
    """
    Creates a formatter function for converting numbers to a percentage string with 2 decimal places.

    This is a factory function that returns a lambda. The lambda expects a numeric value
    and formats it using the `format_percentage` utility with a fixed precision of 2 decimal places.
    Useful for applying consistent percentage formatting to data columns.

    Returns:
        callable: A function that takes a numeric value and returns its formatted percentage string.
    """
    return lambda x: format_percentage(x, True)


def get_string_formatter():
    """
    Creates a formatter function that formats a string to title case only if it is entirely in uppercase.

    This is a factory function that returns a lambda. The lambda expects a string value
    and formats it using the `format_string` utility. Useful for applying consistent
    string formatting to data columns (e.g., in pandas).

    Returns:
        callable: A function that takes a string value and returns its formatted string representation.
    """
    return lambda x: format_string(x)


def get_value_formatter():
    """
    Creates a formatter function for converting numbers to a short scale string (e.g., 1.2M).

    This is a factory function that returns a lambda. The lambda expects a value, and then formats it using the `format_value` utility.
    Useful for applying consistent formatting to data columns (e.g., in pandas).

    Returns:
        callable: A function that takes a numeric value and returns its formatted string representation.
    """
    return lambda x: format_value(x)


def get_numeric(formatted_value: str) -> int:
    """
    Parses a formatted value string (e.g., '1.23B', '45.67M', '8.9K') back into a numeric value.

    Args:
        formatted_value (str): The formatted value string to parse.

    Returns:
        int: The number represented by the formatted string.
    """
    if formatted_value == 'N/A':
        return np.nan

    # Create a dictionary from the rules for easy lookup
    units = {suffix: multiplier for multiplier, suffix in VALUE_FORMAT_MAP}

    suffix = formatted_value[-1]

    if suffix in units:
        number_part = formatted_value[:-1]
        multiplier = units[suffix]
        return int(float(number_part) * multiplier)
    
    return int(float(formatted_value))


def get_percentage_number(formatted_percentage: str) -> float:
    """
    Parses a formatted percentage string (e.g., '12.3%', '100%', '<.01%') back into a numeric float value.
    Handles 'N/A' by returning np.nan.

    Args:
        formatted_percentage (str): The formatted percentage string to parse.

    Returns:
        float: The numeric value of the percentage. Returns np.nan for 'N/A', 0.0 for '<.01%'.
    """
    if formatted_percentage == 'N/A':
        return np.nan
    elif formatted_percentage == '<.01%':
        return 0.0
    else:
        return float(formatted_percentage.replace('%', ''))


def get_quarter(date_str):
    """
    Converts a date string (YYYY-MM-DD) into a calendar quarter string (YYYYQQ).

    Logic:
    - Jan 1 to Mar 31 -> '<Year>Q1'
    - Apr 1 to Jun 30 -> '<Year>Q2'
    - Jul 1 to Sep 30 -> '<Year>Q3'
    - Oct 1 to Dec 31 -> '<Year>Q4'

    Args:
        date_str (str): The date string in 'YYYY-MM-DD' format.

    Returns:
        str: The formatted quarter string 'YYYYQQ'.
    """
    year, month, _ = map(int, date_str.split('-'))
    quarter = (month - 1) // 3 + 1
    return f"{year}Q{quarter}"


def get_quarter_date(quarter: str) -> str:
    """
    Converts a quarter string (e.g., '2024Q2') into its corresponding quarter-end date string.

    Args:
        quarter (str): The quarter string in 'YYYYQQ' format.

    Returns:
        str: The quarter-end date in 'YYYY-MM-DD' format (e.g., '2024-06-30')
    """
    year = int(quarter[:4])
    quarter = int(quarter[5])
    date_map = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    return f"{year}-{date_map[quarter]}"


def isin_to_cusip(isin: str) -> str | None:
    """
    Converts a 12-character ISIN to a 9-character CUSIP.

    This function checks if the identifier is a 12-character string. 
    If so, it assumes it's an ISIN and extracts the central 9-character National Securities Identifying Number (NSIN), which corresponds to the CUSIP for US/Canadian securities or CINS for others.
    If the input is not a 12-character string, it returns None.

    Args:
        isin (str): The security identifier, which could be an ISIN or a CUSIP.

    Returns:
        str | None: The 9-character CUSIP if the input is a valid ISIN, otherwise None.
    """
    if isin and len(isin) == 12:
        return isin[2:11]
    return None
