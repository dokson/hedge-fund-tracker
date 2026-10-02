import csv
import os
import stat
import tempfile
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import TextIO

import numpy as np
import pandas as pd

from app.utils.strings import VALUE_FORMAT_MAP, escape_csv_formula

# Free-text columns that carry untrusted external strings (issuer/company names)
# and so need CSV-formula-injection escaping before being written to disk.
_CSV_TEXT_COLUMNS = ("Company", "Industry")


def escape_csv_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of `df` with free-text columns (Company / Industry) escaped
    against CSV formula injection. Numeric columns are left untouched.
    """
    df = df.copy()
    for col in _CSV_TEXT_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(lambda v: escape_csv_formula(v) if isinstance(v, str) else v)
    return df


def escape_csv_text_rows(rows: list[dict]) -> list[dict]:
    """
    Row-dict counterpart of ``escape_csv_text_columns``: formula-escapes the
    free-text fields (Company / Industry) and leaves every other field as is.
    """
    return [
        {
            key: escape_csv_formula(value)
            if key in _CSV_TEXT_COLUMNS and isinstance(value, str)
            else value
            for key, value in row.items()
        }
        for row in rows
    ]


def _match_target_mode(tmp: str, path: Path) -> None:
    """
    Gives the temp file the target's permissions (0644 for a new file), since
    mkstemp creates it 0600 and os.replace would otherwise narrow the target.
    """
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = 0o644
    Path(tmp).chmod(mode)


_REPLACE_ATTEMPTS = 5
_REPLACE_RETRY_DELAY = 0.1


def _replace_with_retry(src: str, dst: Path) -> None:
    """
    Swap ``src`` onto ``dst``, retrying a few times on PermissionError: on Windows
    ``os.replace`` fails while another handle has the target open for reading.
    """
    for attempt in range(1, _REPLACE_ATTEMPTS + 1):
        try:
            Path(src).replace(dst)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS:
                raise
            time.sleep(_REPLACE_RETRY_DELAY * attempt)


def _atomic_write(filepath: str | Path, write: Callable[[TextIO], object], encoding: str) -> None:
    """
    Shared temp-file writer behind every ``atomic_*`` helper.

    ``write`` fills a temp file in the target's directory, which then takes the
    target's permissions and is swapped in with ``os.replace()`` — so a crash
    mid-write can never truncate or corrupt the target file.
    """
    path = Path(filepath)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            write(f)
        _match_target_mode(tmp, path)
        _replace_with_retry(tmp, path)
    except BaseException:
        with suppress(OSError):
            Path(tmp).unlink()
        raise


def atomic_to_csv(df: pd.DataFrame, filepath: str | Path, **to_csv_kwargs) -> None:
    """
    Write ``df`` to ``filepath`` atomically.

    Args:
        df: The DataFrame to serialize.
        filepath: Destination CSV path.
        **to_csv_kwargs: Forwarded to ``DataFrame.to_csv`` (index, quoting, ...).
    """
    encoding = to_csv_kwargs.pop("encoding", "utf-8")
    _atomic_write(filepath, lambda f: df.to_csv(f, **to_csv_kwargs), encoding)


def atomic_write_rows(
    filepath: str | Path,
    fieldnames: Sequence[str],
    rows: list[dict],
    *,
    quote_all: bool = True,
) -> None:
    """
    Write CSV row dicts to ``filepath`` atomically.

    Args:
        filepath: Destination CSV path.
        fieldnames: DictWriter header order.
        rows: The records to write.
        quote_all: Quote every field (default); pass False for minimal quoting.
    """

    def write(f: TextIO) -> None:
        """
        Writes the header and the rows with the requested quoting.
        """
        # Pass the csv constant directly: a typed variable widens to int and trips the stub.
        if quote_all:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        else:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    _atomic_write(filepath, write, "utf-8")


def atomic_write_text(filepath: str | Path, text: str, encoding: str = "utf-8") -> None:
    """
    Write ``text`` to ``filepath`` atomically and verbatim (no newline translation).

    Args:
        filepath: Destination path.
        text: The full file contents.
        encoding: Text encoding for the file.
    """
    _atomic_write(filepath, lambda f: f.write(text), encoding)


def coalesce(*series: pd.Series | int | float | str) -> pd.Series:
    """
    Returns the first non-null value at each position from a set of Series.

    The first argument must be a Series; subsequent arguments may be Series
    or scalars (used as fillna defaults). Equivalent to SQL's COALESCE.
    """
    result = series[0]
    if not isinstance(result, pd.Series):
        # assert would be stripped under `python -O`; raise so the contract holds.
        raise TypeError("first coalesce argument must be a Series")
    for s in series[1:]:
        result = result.fillna(s)
    return result


def format_value_series(series: pd.Series) -> pd.Series:
    """
    Vectorized version of format_value.
    """
    # Base conditions for null and infinity
    conditions: list = [series.isnull(), series == float("inf")]
    choices: list = ["N/A", "∞"]

    # Dynamically build conditions and choices from the rules
    for threshold, suffix in VALUE_FORMAT_MAP:
        conditions.append(series.abs() >= threshold)
        formatted_series = (series / threshold).map("{:.2f}".format).str.rstrip("0").str.rstrip(".")
        choices.append(formatted_series + suffix)

    # The default choice is for numbers smaller than the lowest threshold
    result_array = np.select(
        conditions, choices, default=series.map("{:.2f}".format).str.rstrip("0").str.rstrip(".")
    )
    return pd.Series(result_array, index=series.index)


def get_numeric_series(series: pd.Series) -> pd.Series:
    """
    Vectorized version of get_numeric.
    Parses a formatted value series (e.g., '1.23B', '45.67M') back into a numeric series.
    """
    # Ensure we are working with strings, and replace 'N/A' with NaN
    s = series.astype(str).str.strip()
    s = s.mask(s == "N/A")

    # Dynamically build conditions and multipliers from the rules
    conditions = []
    multipliers = []
    suffixes_to_strip = ""
    for multiplier, suffix in VALUE_FORMAT_MAP:
        conditions.append(s.str.endswith(suffix, na=False))
        multipliers.append(multiplier)
        suffixes_to_strip += suffix

    # Get the correct multiplier for each row, default is 1
    multiplier_series = np.select(conditions, multipliers, default=1)

    # Remove all possible suffixes, convert to numeric, and apply the multiplier
    numeric_part = pd.to_numeric(s.str.rstrip(suffixes_to_strip), errors="coerce")
    return numeric_part * multiplier_series


def get_percentage_number_series(series: pd.Series) -> pd.Series:
    """
    Vectorized version of get_percentage_number.
    Parses a formatted percentage string series (e.g., '12.3%', '<.01%') back into a numeric float series.
    """
    # Ensure we are working with strings and handle potential whitespace
    s = series.astype(str).str.strip()

    # Define conditions for special cases
    conditions = [s == "N/A", s == "<.01%"]
    choices = [np.nan, 0.0]

    # Default action: remove '%' and convert to numeric
    default = pd.to_numeric(s.str.replace("%", ""), errors="coerce")
    result_array = np.select(conditions, choices, default=default)
    return pd.Series(result_array, index=series.index)
