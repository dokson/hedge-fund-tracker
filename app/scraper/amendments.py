"""
One 13F report per reporting period, with "NEW HOLDINGS" amendments merged in.

A 13F-HR/A is either a ``RESTATEMENT`` (it replaces the report) or ``NEW
HOLDINGS`` (it lists only the positions the report left out). Taking a partial
amendment as the whole report shrinks the fund's book to the added rows and
turns the next comparison into all-NEW positions, so its rows are merged into
the report it amends. Filers also use the ``NEW HOLDINGS`` label for complete
reports; an amendment worth at least ``FULL_REPORT_SHARE`` of the report it
amends is treated as a restatement.
"""

import re
from collections import defaultdict
from collections.abc import Iterable

NEW_HOLDINGS = "NEW HOLDINGS"
FULL_REPORT_SHARE = 0.5

_AMENDMENT_TYPE_RE = re.compile(rb"<(?:[\w.-]+:)?amendmentType>\s*([^<]*?)\s*<", re.IGNORECASE)
_INFO_TABLE_RE = re.compile(
    rb"<(?:[\w.-]+:)?infoTable\b.*?</(?:[\w.-]+:)?infoTable>", re.IGNORECASE | re.DOTALL
)
_TABLE_END_RE = re.compile(rb"</(?:[\w.-]+:)?informationTable>", re.IGNORECASE)
_VALUE_RE = re.compile(rb"<(?:[\w.-]+:)?value>\s*([\d.]+)\s*<", re.IGNORECASE)


def amendment_type(cover_xml: bytes) -> str:
    """
    The amendment kind a 13F cover page declares, upper-cased; empty for an original.
    """
    match = _AMENDMENT_TYPE_RE.search(cover_xml)
    return match.group(1).decode(errors="replace").upper() if match else ""


def holdings_value(table_xml: bytes) -> float:
    """
    The total value of an information table's rows, as filed.
    """
    return sum(
        float(v) for row in _INFO_TABLE_RE.findall(table_xml) for v in _VALUE_RE.findall(row)[:1]
    )


def merge_new_holdings(base_xml: bytes, added_xml: bytes) -> bytes:
    """
    The base information table with the added table's rows appended to it.
    """
    rows = b"".join(_INFO_TABLE_RE.findall(added_xml))
    ends = list(_TABLE_END_RE.finditer(base_xml))
    if not ends:
        return base_xml + rows
    cut = ends[-1].start()
    return base_xml[:cut] + rows + base_xml[cut:]


def _is_partial(amendment: dict, base: dict) -> bool:
    """
    Whether a NEW HOLDINGS amendment only adds to its report.
    """
    if amendment.get("amendment_type") != NEW_HOLDINGS:
        return False
    return holdings_value(amendment["xml_content"]) < FULL_REPORT_SHARE * holdings_value(
        base["xml_content"]
    )


def consolidate_period(filings: Iterable[dict]) -> list[dict]:
    """
    One filing per reporting period, newest period first, from filings listed
    newest-published first. Within a period the latest restatement wins and
    each later partial NEW HOLDINGS amendment is merged into it, keeping the
    amendment's metadata.
    """
    by_period: dict[str, list[dict]] = defaultdict(list)
    for filing in filings:
        if filing.get("reference_date"):
            by_period[filing["reference_date"]].append(filing)

    result: list[dict] = []
    for versions in by_period.values():
        current = versions[-1]
        for newer in reversed(versions[:-1]):
            if _is_partial(newer, current):
                merged = merge_new_holdings(current["xml_content"], newer["xml_content"])
                current = {**newer, "xml_content": merged}
            else:
                current = newer
        result.append(current)
    return sorted(result, key=lambda f: f["reference_date"], reverse=True)
