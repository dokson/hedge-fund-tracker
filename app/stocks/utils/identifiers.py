"""
Helpers for working with security identifiers (CUSIP, ISIN, FIGI, ...).

Pure functions, no I/O.
"""

import re

_BOND_TRAILING_DIGITS = re.compile(r"^([A-Z][A-Z0-9.\-/]*?)\d{3,}$")


def _to_numeric(body: str) -> str:
    """
    Converts an alphanumeric identifier body to a digit string per ISO 6166:
    digits map to themselves; letters map to (ord - 'A' + 10), producing two digits each.
    """
    out: list[str] = []
    for ch in body:
        if ch.isdigit():
            out.append(ch)
        else:
            out.append(str(ord(ch) - ord("A") + 10))
    return "".join(out)


def cusip_to_isin(cusip: str) -> str:
    """
    Converts a 9-character US CUSIP into a 12-character ISIN by prepending "US"
    and appending the ISO 6166 Luhn mod-10 check digit.

    Raises ValueError if the input is not exactly 9 alphanumeric characters.
    """
    normalised = cusip.strip().upper()
    if len(normalised) != 9 or not normalised.isalnum():
        raise ValueError(f"Invalid CUSIP: {cusip!r}")

    body = "US" + normalised
    digits = _to_numeric(body)

    # Luhn mod-10: rightmost body digit gets multiplier 2, alternating to 1 going left.
    # Equivalent to: after appending the (×1) check digit, the alternation from the right is 1,2,1,2,...
    total = 0
    for index, ch in enumerate(reversed(digits)):
        value = int(ch)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value

    check_digit = (10 - total % 10) % 10
    return f"{body}{check_digit}"


def normalize_ticker(raw: str) -> str:
    """
    Collapses bond-style or derivative-style ticker strings to the underlying
    equity ticker.

    Examples:
        "INFN 2.5 03/01/27" → "INFN"   (OpenFIGI bond descriptor)
        "INFN5636215"       → "INFN"   (TradingView bond identifier)
        "AAPL"              → "AAPL"   (plain equity, unchanged)
        "BRK.A"             → "BRK.A"  (share-class, unchanged)

    The heuristic: take the first whitespace-separated token, then strip a
    trailing run of 3+ digits if it follows an alphabetic prefix. Tickers
    shorter than that or with share-class punctuation pass through untouched.
    """
    head = raw.strip().split(maxsplit=1)[0] if raw.strip() else ""
    # Collapse SEC-style suffix separators ("GME/WS" → "GMEWS", "BRK/A" → "BRKA").
    head = head.replace("/", "")
    match = _BOND_TRAILING_DIGITS.match(head)
    return match.group(1) if match else head
