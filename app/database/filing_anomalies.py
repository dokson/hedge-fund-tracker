"""
The filing review register (``filing_anomalies.csv``): price anomalies found in
the saved 13F filings and what was done about each, in one committed file.

Status values:

- ``open``: detected, no safe correction found;
- ``auto-corrected``: corrected by the detector, see ``Kind``; a ``value`` or
  ``shares`` restatement is recomputed on every scan;
- ``corrected``: the same, decided by hand;
- ``carried``: the next filing's delta after a share restatement, rebuilt on
  every scan;
- ``dismissed``: not an error (set by hand), never reported again.

``Kind`` says where a correction applies. ``cusip``: the parser books the row
under ``CUSIP`` on every fetch and regeneration, so the saved CSV carries it.
``value``, ``shares`` and ``carried``: the saved CSV stays as filed and the
analysis loaders read the row with the register's ``Shares``, ``Value``,
``Delta_Shares``, ``Delta_Value`` and ``Delta`` instead
(``apply_restatements``), re-weighting the filing's ``Portfolio%``. The
register is the only place these figures are computed; the TypeScript loader
applies the same columns.

A scan merges into the register and never rewrites a decided row: once a CUSIP
correction is applied the row stops looking anomalous, and dropping it would
undo the correction on the next regeneration. Automatic restatements are not
decided: the saved CSV keeps the filed figures, so every scan finds them again
and recomputes them with the current detector. The file carries no timestamps
and is written in a fixed order, so it only changes when its content does.
"""

import csv

import pandas as pd

import app.database as _db
from app.analysis.filing_anomalies import CusipAnomaly, scan_database
from app.database import FILING_ANOMALIES_FILE
from app.utils.logger import get_logger
from app.utils.pd import atomic_to_csv, get_numeric_series
from app.utils.strings import format_percentage, format_value

logger = get_logger(__name__)

__all__ = [
    "COLUMNS",
    "apply_restatements",
    "check_filings",
    "corrections_for",
    "merge_anomalies",
    "save_filing_anomalies",
]

COLUMNS = [
    "Quarter",
    "Fund",
    "Filed_CUSIP",
    "Filed_Company",
    "Filed_Price",
    "Reference_Price",
    "Status",
    "Kind",
    "CUSIP",
    "Shares",
    "Value",
    "Delta_Shares",
    "Delta_Value",
    "Delta",
    "Note",
]
_KEY = ["Quarter", "Fund", "Filed_CUSIP", "Filed_Company"]
_CORRECTED = frozenset({"auto-corrected", "corrected"})
_DECIDED = _CORRECTED | {"dismissed"}
_APPLIED = _CORRECTED | {"carried"}
_RESTATED_KINDS = frozenset({"value", "shares", "carried"})
_DRIFT_TOLERANCE = 0.01


def _load_register() -> pd.DataFrame:
    """
    The register as stored, empty with every column when absent or unreadable.
    """
    filepath = _db._safe_db_join(FILING_ANOMALIES_FILE)
    if not filepath.is_file():
        return pd.DataFrame(columns=COLUMNS)
    try:
        frame = pd.read_csv(filepath, dtype=str, keep_default_na=False)
    except OSError, pd.errors.ParserError, pd.errors.EmptyDataError:
        logger.error("while reading '%s'", FILING_ANOMALIES_FILE, exc_info=True)
        return pd.DataFrame(columns=COLUMNS)
    return _with_kind(frame)


def _with_kind(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Every column present; a CUSIP correction written without a ``Kind`` reads as one.
    """
    frame = frame.reindex(columns=COLUMNS, fill_value="").astype(str)
    untyped = (frame["Kind"] == "") & (frame["CUSIP"] != "")
    frame.loc[untyped, "Kind"] = "cusip"
    return frame


def _row(anomaly: CusipAnomaly) -> dict[str, str]:
    """
    A register row for a fresh finding.
    """
    status = (
        "carried" if anomaly.kind == "carried" else "auto-corrected" if anomaly.kind else "open"
    )
    figures = anomaly.restated
    return {
        "Quarter": anomaly.quarter,
        "Fund": anomaly.fund,
        "Filed_CUSIP": anomaly.cusip,
        "Filed_Company": anomaly.filed_company,
        "Filed_Price": f"{anomaly.filed_price:.4f}",
        "Reference_Price": f"{anomaly.reference_price:.4f}",
        "Status": status,
        "Kind": anomaly.kind,
        "CUSIP": anomaly.correct_cusip or "",
        "Shares": str(figures.shares) if figures else "",
        "Value": f"{figures.value:.0f}" if figures else "",
        "Delta_Shares": str(figures.delta_shares) if figures else "",
        "Delta_Value": f"{figures.delta_value:.0f}" if figures else "",
        "Delta": figures.delta if figures else "",
        "Note": anomaly.note,
    }


def merge_anomalies(
    register: pd.DataFrame, anomalies: list[CusipAnomaly], tracked: set[str] | None = None
) -> pd.DataFrame:
    """
    Fold a scan into the register: decided rows are kept untouched (detected or
    not), findings are added or refreshed as open or auto-corrected, and open
    rows, automatic restatements and carried rows the scan no longer finds are
    dropped. A refreshed restatement whose figures moved less than
    ``_DRIFT_TOLERANCE`` keeps its written row, so a late filing that nudges the
    funds' median does not rewrite the file. With a non-empty ``tracked`` set,
    rows of funds outside it go too, decided ones included; an empty set (an
    unreadable fund list) drops nothing.
    """
    register = _with_kind(register)
    if tracked:
        register = register[register["Fund"].isin(tracked)]
        anomalies = [a for a in anomalies if a.fund in tracked]
    automatic = (register["Status"] == "auto-corrected") & register["Kind"].isin(
        {"value", "shares"}
    )
    decided = register[register["Status"].isin(_DECIDED) & ~automatic]
    decided_keys = set(map(tuple, decided[_KEY].to_numpy()))
    written = {
        tuple(row[k] for k in _KEY): row
        for row in register[automatic | (register["Status"] == "carried")].to_dict("records")
    }
    fresh = []
    for row in map(_row, anomalies):
        key = tuple(row[k] for k in _KEY)
        if key in decided_keys:
            continue
        previous = written.get(key)
        fresh.append(previous if previous and _drifted_only(previous, row) else row)
    merged = pd.concat([decided, pd.DataFrame(fresh, columns=COLUMNS)], ignore_index=True)
    merged = merged.drop_duplicates(subset=_KEY, keep="first")
    return merged.sort_values(_KEY, kind="stable").reset_index(drop=True)


def _drifted_only(previous: dict, fresh: dict) -> bool:
    """
    Whether a rescan restates a row the same way, its figures within
    ``_DRIFT_TOLERANCE`` of the written ones.
    """
    if any(previous[c] != fresh[c] for c in ("Status", "Kind", "CUSIP")):
        return False
    for column in ("Shares", "Value", "Delta_Shares", "Delta_Value"):
        old, new = previous[column], fresh[column]
        if old == new:
            continue
        try:
            a, b = float(old), float(new)
        except ValueError:
            return False
        if abs(a - b) > _DRIFT_TOLERANCE * max(abs(a), abs(b)):
            return False
    return True


def save_filing_anomalies(anomalies: list[CusipAnomaly]) -> pd.DataFrame:
    """
    Merge a scan into the register on disk, keeping only the funds in
    hedge_funds.csv, and return the saved register.
    """
    from app.database.quarters import load_hedge_funds

    tracked = {str(fund["Fund"]) for fund in load_hedge_funds()}
    merged = merge_anomalies(_load_register(), anomalies, tracked)
    atomic_to_csv(
        merged, _db._safe_db_join(FILING_ANOMALIES_FILE), index=False, quoting=csv.QUOTE_ALL
    )
    return merged


def check_filings() -> list[CusipAnomaly]:
    """
    Scan every saved filing, fold the findings into the register and return them.
    A new CUSIP correction takes effect when the filing is next parsed
    (``pipenv run regenerate <fund>``); a restatement on the next load.
    """
    anomalies = scan_database()
    save_filing_anomalies(anomalies)
    logger.info(
        "Filing check: %d anomalies; %d CUSIP corrections (applied on regenerate), %d restated in the analysis, %d left open",
        len(anomalies),
        sum(1 for a in anomalies if a.kind == "cusip"),
        sum(1 for a in anomalies if a.kind in {"value", "shares", "carried"}),
        sum(1 for a in anomalies if not a.kind),
    )
    return anomalies


def corrections_for(fund: str, quarter: str) -> dict[tuple[str, str], str]:
    """
    The corrected rows (automatic or by hand) of one filing as (filed CUSIP, upper-cased filed
    name) -> CUSIP to book the row under; empty when there are none.
    """
    register = _load_register()
    rows = register[
        (register["Fund"] == fund)
        & (register["Quarter"] == quarter)
        & (register["Status"].isin(_CORRECTED))
        & (register["CUSIP"] != "")
    ]
    return {
        (str(cusip).upper(), str(company).strip().upper()): str(correct).upper()
        for cusip, company, correct in zip(
            rows["Filed_CUSIP"], rows["Filed_Company"], rows["CUSIP"], strict=True
        )
    }


def apply_restatements(
    holdings: pd.DataFrame, quarter: str, register: pd.DataFrame | None = None
) -> pd.DataFrame:
    """
    Read one quarter's holdings (one filing or many, with a ``Fund`` column)
    with the register's restated figures, re-weighting the ``Portfolio%`` of
    every filing that changed. The saved CSVs are never touched.
    """
    register = _load_register() if register is None else _with_kind(register)
    restated = register[
        (register["Quarter"] == quarter)
        & register["Status"].isin(_APPLIED)
        & register["Kind"].isin(_RESTATED_KINDS)
    ]
    if restated.empty or holdings.empty:
        return holdings
    out = holdings.copy()
    changed: set[str] = set()
    for _, fix in restated.iterrows():
        rows = (out["Fund"] == fix["Fund"]) & (out["CUSIP"].astype(str) == fix["Filed_CUSIP"])
        if not rows.any():
            continue
        for column in ("Shares", "Delta_Shares"):
            count = int(fix[column])
            numeric = pd.api.types.is_numeric_dtype(out[column])
            out.loc[rows, column] = count if numeric else str(count)
        for column in ("Value", "Delta_Value"):
            amount = float(fix[column])
            numeric = pd.api.types.is_numeric_dtype(out[column])
            out.loc[rows, column] = round(amount) if numeric else format_value(amount)
        out.loc[rows, "Delta"] = fix["Delta"]
        changed.add(fix["Fund"])
    for fund in changed:
        rows = out["Fund"] == fund
        values = get_numeric_series(out.loc[rows, "Value"]).fillna(0)
        total = values.sum()
        if total > 0:
            out.loc[rows, "Portfolio%"] = [_weight(v / total * 100) for v in values]
    return out


def _weight(pct: float) -> str:
    """
    A Portfolio% cell as the comparison writes it.
    """
    return format_percentage(pct, decimal_places=2) if 0.01 <= pct < 1 else format_percentage(pct)
