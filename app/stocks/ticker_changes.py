"""
Service layer for applying NASDAQ ticker (symbol) changes to the database.

Kept separate from the HTTP handlers in app/server.py so the orchestration is
unit-testable without FastAPI and reusable from the CLI.
"""

import re
from difflib import SequenceMatcher
from typing import TypedDict

from app.database import find_cusips_for_ticker, load_stocks, update_ticker
from app.stocks.libraries.nasdaq import Nasdaq
from app.stocks.libraries.openfigi import OpenFIGI
from app.stocks.libraries.yfinance import YFinance
from app.stocks.utils.identifiers import normalize_ticker
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)


class TickerChange(TypedDict):
    """
    A NASDAQ symbol change whose old symbol is tracked in stocks.csv.
    """

    oldSymbol: str
    newSymbol: str
    companyName: str
    cusips: list[str]
    trackedCompanies: list[str]


class SkippedChange(TickerChange):
    """
    A tracked symbol change that failed verification, with the reason.
    """

    reason: str


class TickerChangeReport(TypedDict):
    """
    Result of the NASDAQ symbol-change detection pass.
    """

    total_changes: int
    applicable: list[TickerChange]
    skipped: list[SkippedChange]


class AppliedChange(TypedDict):
    """
    A ticker change that was written to the database.
    """

    old: str
    new: str
    companyName: str


class ApplyReport(TypedDict):
    """
    Result of applying the verified NASDAQ symbol changes.
    """

    applied: list[AppliedChange]
    skipped: list[SkippedChange]
    message: str


class StaleTicker(TypedDict):
    """
    A stocks.csv row whose CUSIP now maps to a different US symbol for the
    same company on OpenFIGI.
    """

    cusip: str
    oldTicker: str
    newTicker: str
    company: str
    figiName: str


class StaleTickerReport(TypedDict):
    """
    Result of the full-database OpenFIGI reconciliation.
    """

    checked: int
    resolved: int
    candidates: list[StaleTicker]


# Legal-form and share-class boilerplate carries no identity signal.
_GENERIC_NAME_TOKENS = frozenset(
    {
        "a",
        "and",
        "b",
        "c",
        "class",
        "co",
        "common",
        "company",
        "corp",
        "corporation",
        "etf",
        "group",
        "holding",
        "holdings",
        "inc",
        "incorporated",
        "limited",
        "llc",
        "lp",
        "ltd",
        "new",
        "of",
        "ordinary",
        "plc",
        "share",
        "shares",
        "stock",
        "the",
        "trust",
    }
)
_NAME_MATCH_THRESHOLD = 0.6


def _name_tokens(name: str) -> list[str]:
    """
    Lowercases a company name and splits it into alphanumeric tokens.
    """
    return re.findall(r"[a-z0-9]+", name.lower())


def company_names_match(first: str, second: str) -> bool:
    """
    Heuristically decides whether two company names refer to the same company.

    Guards against ticker collisions: a symbol change reported for a security
    that merely reuses a ticker already assigned to a different company in
    stocks.csv must never be treated as applicable.
    """
    tokens_first, tokens_second = _name_tokens(first), _name_tokens(second)
    if not tokens_first or not tokens_second:
        return False
    if tokens_first == tokens_second:
        return True
    significant = sorted(
        (set(tokens_first) - _GENERIC_NAME_TOKENS, set(tokens_second) - _GENERIC_NAME_TOKENS),
        key=len,
    )
    if len(significant[0]) >= 2 and significant[0] <= significant[1]:
        return True
    ratio = SequenceMatcher(None, " ".join(tokens_first), " ".join(tokens_second)).ratio()
    return ratio >= _NAME_MATCH_THRESHOLD


def _norm_symbol(symbol: str) -> str:
    """
    Normalizes a ticker symbol for comparison across providers, which disagree
    on share-class separators.
    """
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def _verify_change(entry: TickerChange, matching: list[dict]) -> str | None:
    """
    Verifies a candidate ticker change against OpenFIGI (CUSIP identity) with
    the company-name guard as fallback. Returns None when the change is
    verified, otherwise the reason it must be skipped.

    OpenFIGI mapping the tracked CUSIP to the new symbol confirms the change
    even when the company was renamed; a mapping to any third symbol rejects
    it. When OpenFIGI is unavailable or still reports the old symbol (it can
    lag a fresh change), the decision falls back to the name guard.
    """
    old_norm, new_norm = _norm_symbol(entry["oldSymbol"]), _norm_symbol(entry["newSymbol"])
    figi_symbols = {
        _norm_symbol(ticker)
        for stock in matching
        if (ticker := OpenFIGI.get_ticker(stock["CUSIP"]))
    }
    if new_norm in figi_symbols:
        return None
    if figi_symbols - {old_norm, new_norm}:
        return "OpenFIGI maps the tracked CUSIP to a different ticker"
    if any(company_names_match(s["Company"], entry["companyName"]) for s in matching):
        return None
    return "NASDAQ company name does not match the tracked company"


def _classify_changes(changes: list[dict]) -> tuple[list[TickerChange], list[SkippedChange]]:
    """
    Splits NASDAQ symbol changes into (applicable, skipped) against stocks.csv.

    A change is applicable when its old symbol is tracked AND it passes
    verification (OpenFIGI CUSIP identity, then company-name guard); tracked
    tickers that fail verification are skipped (likely ticker collision).
    """
    applicable: list[TickerChange] = []
    skipped: list[SkippedChange] = []
    for change in changes:
        old_symbol = change.get("oldSymbol", "")
        matching = find_cusips_for_ticker(old_symbol)
        if not matching:
            continue
        entry: TickerChange = {
            "oldSymbol": old_symbol,
            "newSymbol": change.get("newSymbol", ""),
            "companyName": change.get("companyName", ""),
            "cusips": [s["CUSIP"] for s in matching],
            "trackedCompanies": [s["Company"] for s in matching],
        }
        reason = _verify_change(entry, matching)
        if reason is None:
            applicable.append(entry)
        else:
            skipped.append({**entry, "reason": reason})
            logger.warning(
                "Skipping ticker change %s → %s (%s): NASDAQ company '%s', tracked '%s'",
                log_safe(entry["oldSymbol"]),
                log_safe(entry["newSymbol"]),
                reason,
                log_safe(entry["companyName"]),
                log_safe(", ".join(entry["trackedCompanies"])),
            )
    return applicable, skipped


def detect_applicable_ticker_changes() -> TickerChangeReport:
    """
    Fetch recent NASDAQ symbol changes and return those whose old symbol maps to
    one or more CUSIPs already tracked in stocks.csv.

    Shape: ``{"total_changes": int, "applicable": [{"oldSymbol", "newSymbol",
    "companyName", "cusips", "trackedCompanies"}, ...], "skipped": [...]}``
    where skipped entries are tracked tickers whose NASDAQ company name did not
    match the tracked company (ticker collision — needs manual review).
    """
    changes = Nasdaq.get_symbol_changes()
    applicable, skipped = _classify_changes(changes)
    return {"total_changes": len(changes), "applicable": applicable, "skipped": skipped}


def _is_cosmetic_variant(db_symbol: str, figi_symbol: str) -> bool:
    """
    Detects provider-convention differences that are the same security:
    FIGI's X-wrapped aliases for listed funds and W/WS warrant suffixes.
    """
    if (
        figi_symbol.strip("X") in (db_symbol, db_symbol.strip("X"))
        or figi_symbol == f"X{db_symbol}"
    ):
        return True

    def stem(symbol: str) -> str:
        """
        Strips a trailing warrant suffix (W or WS) from a symbol.
        """
        return symbol.removesuffix("WS") if symbol.endswith("WS") else symbol.removesuffix("W")

    return stem(db_symbol) == stem(figi_symbol)


def detect_stale_tickers() -> StaleTickerReport:
    """
    Reconciles every stocks.csv row against OpenFIGI's current US listing for
    its CUSIP.

    Complements ``detect_applicable_ticker_changes``: the NASDAQ feed only
    covers its own recent window, so older renames never appear there. A row
    is a candidate only when OpenFIGI maps the CUSIP to a different symbol
    AND the FIGI record names the same company (a reused CUSIP with a new
    issuer is never proposed).

    Shape: ``{"checked": int, "resolved": int, "candidates": [{"cusip",
    "oldTicker", "newTicker", "company", "figiName"}, ...]}``.
    """
    stocks = load_stocks()
    # Plain per-CUSIP dicts: repeated scalar .loc would go quadratic on 10k+
    # rows and returns a Series (not a value) if the index ever has dupes.
    tickers = stocks["Ticker"].astype(str).to_dict()
    companies = stocks["Company"].astype(str).to_dict()
    records = OpenFIGI.map_cusips([str(cusip) for cusip in stocks.index])
    candidates: list[StaleTicker] = []
    for cusip, record in records.items():
        figi_ticker = normalize_ticker(record.get("ticker") or "")
        if not figi_ticker:
            continue
        db_ticker = tickers.get(cusip, "")
        figi_norm, db_norm = _norm_symbol(figi_ticker), _norm_symbol(normalize_ticker(db_ticker))
        if figi_norm == db_norm or _is_cosmetic_variant(db_norm, figi_norm):
            continue
        company = companies.get(cusip, "")
        figi_name = record.get("name") or ""
        if not company_names_match(company, figi_name):
            continue
        candidates.append(
            {
                "cusip": cusip,
                "oldTicker": db_ticker,
                "newTicker": figi_ticker,
                "company": company,
                "figiName": figi_name,
            }
        )
    return {"checked": len(stocks), "resolved": len(records), "candidates": candidates}


def apply_ticker_changes() -> ApplyReport:
    """
    Detect applicable NASDAQ ticker changes and apply each across the database,
    enriching the new company name from YFinance when available.

    Shape: ``{"applied": [{"old", "new", "companyName"}, ...],
    "skipped": [...], "message": str}``.
    """
    changes = Nasdaq.get_symbol_changes()
    applicable, skipped = _classify_changes(changes)
    applied: list[AppliedChange] = []
    for change in applicable:
        company = YFinance.get_company("", ticker=change["newSymbol"]) or change["companyName"]
        update_ticker(change["oldSymbol"], change["newSymbol"], new_company=company)
        applied.append(
            {"old": change["oldSymbol"], "new": change["newSymbol"], "companyName": company}
        )

    if not applied:
        message = "No applicable ticker changes found on NASDAQ."
    else:
        lines = [f"{a['old']} → {a['new']} ({a['companyName']})" for a in applied]
        message = f"Applied {len(applied)} ticker change(s):\n" + "\n".join(lines)
    if skipped:
        lines = [
            f"{s['oldSymbol']} → {s['newSymbol']} ({s['companyName']}): {s['reason']}"
            for s in skipped
        ]
        message += f"\nSkipped {len(skipped)} unverified change(s):\n" + "\n".join(lines)
    return {"applied": applied, "skipped": skipped, "message": message}
