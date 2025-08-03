def format_percentage(value, show_sign=False, decimal_places=1):
    """
    Formats a numeric value as a percentage string:
    - Returns '<.01%' for values between 0 and 0.01 (exclusive).
    - Rounds to specified decimal_places and trims unnecessary zeros.
    - Optionally prepends sign when show_sign is True.

    Args:
        value (float): The percentage value to format.
        show_sign (bool, optional): Whether to prepend sign. Default is False.
        decimal_places (int, optional): Number of decimal places to show. Default is 1.

    Returns:
        str: Formatted percentage string.
    """
    sign = '+' if show_sign else ''

    if 0 < value < 0.01 and not show_sign:
        return '<.01%'
    else:
        formatted = f'{value:{sign}.{decimal_places}f}'.rstrip('0').rstrip('.')
        return f'{formatted}%'


def format_value(value: int) -> str:
    """
    Formats a numeric value into a human-readable short scale string, up to 2 decimal places (e.g., 1.23B, 45.67M, 8.9K).

    Args:
        value (int): The numeric value to format.

    Returns:
        str: Formatted string.
    """
    abs_value = abs(value)

    if abs_value >= 1_000_000_000_000:
        formatted = f'{value / 1_000_000_000_000:.2f}'
        suffix = 'T'
    elif abs_value >= 1_000_000_000:
        formatted = f'{value / 1_000_000_000:.2f}'
        suffix = 'B'
    elif abs_value >= 1_000_000:
        formatted = f'{value / 1_000_000:.2f}'
        suffix = 'M'
    elif abs_value >= 1_000:
        formatted = f'{value / 1_000:.2f}'
        suffix = 'K'
    else:
        formatted = f'{value:.2f}'
        suffix = ''

    return formatted.rstrip('0').rstrip('.') + suffix


def get_numeric(formatted_value: str) -> int:
    """
    Parses a formatted value string (e.g., '1.23B', '45.67M', '8.9K') back into a numeric value.

    Args:
        formatted_value (str): The formatted value string to parse.

    Returns:
        int: The number represented by the formatted string.
    """

    units = {
        'T': 1_000_000_000_000,
        'B': 1_000_000_000,
        'M': 1_000_000,
        'K': 1_000
    }

    unit = formatted_value[-1]

    if unit in units:
        number = formatted_value[:-1]
        multiplier = units[unit]
    else:
        number = formatted_value
        multiplier = 1

    return int(float(number) * multiplier)


def get_quarter(date_str):
    """
    Converts a date string (YYYY-MM-DD) into a quarter string (YYYYQQ)
    based on the filing date, without using the datetime module.
    
    Logic:
    - Apr 1 to Jun 30 -> YearQ1
    - Jul 1 to Sep 30 -> YearQ2
    - Oct 1 to Dec 31 -> YearQ3
    - Jan 1 to Mar 31 -> PreviousYearQ4

    Args:
        date_str (str): The date string in 'YYYY-MM-DD' format.

    Returns:
        str: The formatted quarter string 'YYYYQQ'.
    """
    year, month, _ = map(int, date_str.split('-'))

    if 3 <= month <= 5:
        return f"{year}Q1"
    elif 6 <= month <= 8:
        return f"{year}Q2"
    elif 9 <= month <= 11:
        return f"{year}Q3"
    else:
        return f"{year - 1}Q4"
