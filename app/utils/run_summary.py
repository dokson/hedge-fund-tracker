"""
Markdown run summary for the scheduled filings fetch, written to the GitHub Actions job page.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")


@dataclass(frozen=True)
class FetchRunSummary:
    """
    Outcome of one filings-fetch run.
    """

    funds: int
    reports_saved: int
    nq_rows_saved: int
    nq_failed_funds: tuple[str, ...] = ()
    nq_saved: bool = True
    alerts: tuple[str, ...] = ()


def markdown_safe(value: str) -> str:
    """
    Sanitize an external string into inert single-line Markdown.
    """
    return _MARKDOWN_SPECIAL.sub(r"\\\1", log_safe(value, max_len=200))


def render_markdown(summary: FetchRunSummary) -> str:
    """
    Render the run summary as a Markdown table plus the failed funds and alerts.
    """
    failed = sorted(summary.nq_failed_funds)
    alerts = list(dict.fromkeys(summary.alerts))
    lines = [
        "## Filings fetch",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Funds processed | {summary.funds} |",
        f"| 13F comparisons written | {summary.reports_saved} |",
        f"| Non-quarterly filing rows saved | {summary.nq_rows_saved} |",
        f"| Non-quarterly fetches failed (existing rows kept) | {len(failed)} |",
        f"| Unidentified filers / unresolved identifiers | {len(alerts)} |",
    ]
    if not summary.nq_saved:
        lines += [
            "",
            "> **Warning:** non_quarterly.csv was not saved; the existing file is unchanged.",
        ]
    if failed:
        lines += ["", "### Non-quarterly fetch failed (existing rows kept)", ""]
        lines += [f"- {markdown_safe(name)}" for name in failed]
    if alerts:
        lines += ["", "### Unidentified filers / unresolved identifiers", ""]
        lines += [f"- {markdown_safe(alert)}" for alert in alerts]
    return "\n".join(lines)


def render_missing_quarters_markdown(missing: Mapping[str, list[str]]) -> str:
    """
    The run-summary section listing tracked funds with no 13F saved for some quarter.
    """
    lines = ["## Missing quarters", ""]
    if not missing:
        return "\n".join([*lines, "Every tracked fund has every quarter."])
    lines += ["| Fund | Missing |", "|---|---|"]
    lines += [f"| {markdown_safe(fund)} | {', '.join(missing[fund])} |" for fund in sorted(missing)]
    return "\n".join(lines)


def write_step_summary(markdown: str, env: Mapping[str, str] | None = None) -> bool:
    """
    Append ``markdown`` to the GitHub Actions step summary; a no-op outside Actions.

    Returns True when written. A write failure is logged, never raised, so the
    summary can't fail the fetch it describes.
    """
    path = (os.environ if env is None else env).get("GITHUB_STEP_SUMMARY")
    if not path:
        return False
    try:
        with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown + "\n")
    except OSError:
        logger.warning("Could not write the GitHub step summary", exc_info=True)
        return False
    return True
