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


# Security-type descriptor providers append to the issuer name. Stripped only
# from the end, so a share class ("... Class A Common Stock") keeps its class.
_SECURITY_DESCRIPTOR = re.compile(
    r"\s+(?:(?:american|global)\s+)?(?:depositary|depository)\s+(?:shares|receipts)$"
    r"|\s+(?:common|ordinary)\s+(?:stock|shares)$",
    re.IGNORECASE,
)

# Legal-entity suffix tokens, possibly chained ("S.A.B. de C.V.", "SAPI de CV").
_LEGAL_SUFFIX_TOKEN = (
    r"(?:Inc|Incorporated|Corp|Corporation|Co|Ltd|Limited|LLC|L\.L\.C|LP|L\.P|LLP|PLC|P\.L\.C"
    r"|N\.V|NV|B\.V|BV|S\.A\.B|S\.A|SAB|SAPI|SA|C\.V|CV|GmbH|AG|SE|AB|ASA|AS|OYJ|S\.p\.A|SpA"
    r"|Trust|de)\.?"
)
# Anchored at end-of-string so commas inside firm names, descriptive lists and
# dates ("Tweedy, Browne", "Gold, Natural Resources", "February 17, 2045") stay.
_COMMA_BEFORE_LEGAL_SUFFIX = re.compile(
    rf",(\s+{_LEGAL_SUFFIX_TOKEN}(?:\s+{_LEGAL_SUFFIX_TOKEN})*)$",
    re.IGNORECASE,
)


# Only a one-word abbreviation ("Inc.", "Corp.", "Co."): requiring whitespace
# before the token leaves multi-dot forms ("L.P.", "S.A.B. de C.V.") intact,
# since their final token is preceded by a period rather than a space.
_TRAILING_ABBREVIATION_PERIOD = re.compile(r"\s([A-Za-z]{2,})\.$")


def normalize_company_name(raw: str) -> str:
    """
    Normalizes a provider-supplied company name for storage in stocks.csv.

    Three cleanups, all driven by how providers pad names: the trailing
    security-type descriptor is dropped (the CUSIP already identifies the
    security, so "Common Stock" / "Ordinary Shares" / "American Depositary
    Shares" carry nothing), the comma before a legal-entity suffix is removed,
    and a trailing period is dropped from a one-word abbreviation. The last two
    follow the convention the file already overwhelmingly uses.

    Examples:
        "Grandstand Limited Ordinary Shares"  → "Grandstand Limited"
        "PowerCompute, Inc. Common Stock"     → "PowerCompute Inc"
        "Ridgeline Compute Class A Common Stock" → "Ridgeline Compute Class A"
        "Orbital Rocket L.P."                → unchanged (multi-dot abbreviation)
        "Tweedy, Browne Insider + Value ETF"  → unchanged (semantic comma)
    """
    name = " ".join(raw.split())
    while (stripped := _SECURITY_DESCRIPTOR.sub("", name)) != name:
        name = stripped
    name = _COMMA_BEFORE_LEGAL_SUFFIX.sub(r"\1", name)
    return _TRAILING_ABBREVIATION_PERIOD.sub(r" \1", name).strip()
