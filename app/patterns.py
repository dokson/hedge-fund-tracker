"""
Centralised regular expressions for shared validation / domain formats.

Only patterns that represent a *shared concept* reused across modules live here,
so the canonical definition exists in exactly one place. Module-internal,
algorithm-specific regexes (TOON repair in app/ai/response_parser, XML/XXE
sanitising in app/scraper/xml_processor, identifier heuristics, HTML scraping)
intentionally stay next to their code for cohesion.
"""

import re

# A fiscal-quarter directory/label, e.g. "2025Q1".
QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$")

# Same shape with capture groups, for parsing the year/quarter out of a label.
QUARTER_CAPTURE_RE = re.compile(r"(\d{4})Q([1-4])")

# A stock ticker: upper-case alphanumerics, dot, hyphen; 1-10 chars.
TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")

# A 9-character CUSIP identifier.
CUSIP_RE = re.compile(r"^[A-Z0-9]{9}$")

# An environment-variable name (POSIX-ish: letter/underscore start).
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# A fund display name: printable, no shell/markup metacharacters; 1-200 chars.
FUND_NAME_RE = re.compile(r"^[^<>\"'`&\\]{1,200}$")
