"""
Detection of 13F rows whose implied price does not fit their CUSIP.

The CUSIP is the identifier; names are never compared, because filings keep
the name a company had when filed and renames make names misleading. The check
is the price a row implies (value / shares) against the median the other funds
report for the same CUSIP in the same quarter: every holder values a security
at one quarter-end price, so a row far from it was booked under another
issuer's CUSIP or with a mis-scaled value or share count. A security held by
fewer than ``min_reporters`` funds has no reference and is never judged; the
fund's own history is not one, because genuine moves look the same.

A flagged row whose price matches exactly one other CUSIP of the same filing
(another flagged row, or a position the filing closes) gets that CUSIP as its
correction. Findings go into the register ``filing_anomalies.csv``
(``app.database.filing_anomalies``), whose corrected rows the parser applies
on every fetch.
"""

import statistics
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace

import pandas as pd

from app.utils.pd import get_numeric_series
from app.utils.run_summary import markdown_safe
from app.utils.strings import format_percentage


@dataclass(frozen=True)
class FiledRow:
    """
    One position as a fund filed it. ``company`` is the filed name, carried for
    the report only.
    """

    quarter: str
    fund: str
    cusip: str
    company: str
    price: float
    shares: float
    delta_shares: float = 0.0
    delta: str = ""

    @property
    def value(self) -> float:
        """
        The filed position value.
        """
        return self.price * self.shares


@dataclass(frozen=True)
class Restatement:
    """
    The figures a row is analysed with instead of the filed ones.
    """

    shares: int
    value: float
    delta_shares: int
    delta_value: float
    delta: str


@dataclass(frozen=True)
class CusipAnomaly:
    """
    A filed row whose price does not fit its CUSIP: ``reference_price`` is the
    median the other funds reported for it.
    """

    quarter: str
    fund: str
    cusip: str
    filed_company: str
    filed_price: float
    reference_price: float
    correct_cusip: str | None = None
    note: str = ""
    # "cusip" (booked under its real CUSIP by the parser), "value" or "shares"
    # (restated at the funds' price), "carried" (the next filing's delta after a
    # share restatement), or "" when nothing could be done.
    kind: str = ""
    restated: Restatement | None = None


@dataclass(frozen=True)
class CusipAnomalyDetector:
    """
    Flags rows priced unlike their CUSIP.

    ``price_tolerance`` is the relative gap from the funds' median that counts
    as a different security; ``min_reporters`` is how many filings of a CUSIP in
    a quarter make that median trustworthy.

    A flagged row is corrected only on firm evidence: its price within
    ``match_tolerance`` of exactly one candidate's median, and either a closed
    cycle of flagged rows (a rotated CUSIP column) or, for a row NEW in the
    filing, a position the filing closes whose previous share count is within
    ``match_shares_tolerance`` of the row's. A position the fund already held
    under its CUSIP is never moved to a closed one: a filing that closes
    hundreds of positions always has one priced alike by chance.

    Any other flagged row is restated at the funds' price: its value, unless the
    price gap equals a split factor registered for the CUSIP (``split_factors``,
    within ``split_tolerance``), which puts the share count on the other basis.
    A share restatement also corrects the delta of the fund's next filing,
    compared against the wrong count across ``split_factors_fn(previous, current)``.
    """

    price_tolerance: float = 0.4
    min_reporters: int = 3
    match_tolerance: float = 0.05
    match_shares_tolerance: float = 0.5
    split_tolerance: float = 0.02
    split_factors: Mapping[str, Iterable[float]] = field(default_factory=dict)
    split_factors_fn: Callable[[str, str], Mapping[str, float]] | None = None

    def detect(
        self,
        rows: Iterable[FiledRow],
        closed: Mapping[tuple[str, str], Mapping[str, float]] | None = None,
    ) -> list[CusipAnomaly]:
        """
        Return the anomalous rows, ordered by quarter, fund and CUSIP, each with
        its correct CUSIP when the matcher finds one. ``closed`` maps (fund,
        quarter) to the CUSIPs that filing closes, with the share count held before.
        """
        priced = [r for r in rows if r.price > 0]
        reported: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in priced:
            reported[(r.quarter, r.cusip)].append(r.price)
        medians = {
            key: statistics.median(prices)
            for key, prices in reported.items()
            if len(prices) >= self.min_reporters
        }

        by_filing: dict[tuple[str, str], list[tuple[CusipAnomaly, FiledRow]]] = defaultdict(list)
        for r in priced:
            median = medians.get((r.quarter, r.cusip))
            if median and abs(r.price / median - 1) > self.price_tolerance:
                by_filing[(r.fund, r.quarter)].append((self._anomaly(r, median), r))

        filed = {(r.fund, r.quarter, r.cusip): r for r in priced}
        anomalies: list[CusipAnomaly] = []
        for (fund, quarter), flagged in by_filing.items():
            closing = (closed or {}).get((fund, quarter), {})
            for a in self._match(flagged, closing, lambda c, q=quarter: medians.get((q, c))):
                if a.correct_cusip:
                    anomalies.append(replace(a, kind="cusip"))
                else:
                    anomalies.append(self._restate(a, filed[(a.fund, a.quarter, a.cusip)]))

        fund_quarters: dict[str, set[str]] = defaultdict(set)
        for fund, quarter in [(r.fund, r.quarter) for r in priced] + list(closed or {}):
            fund_quarters[fund].add(quarter)
        anomalies += [
            carried
            for a in anomalies
            if a.kind == "shares"
            and (carried := self._carry(a, filed, closed or {}, fund_quarters[a.fund]))
        ]
        return sorted(anomalies, key=lambda a: (a.quarter, a.fund, a.cusip))

    def _restate(self, anomaly: CusipAnomaly, row: FiledRow) -> CusipAnomaly:
        """
        Restate a row at the funds' price: its share count when the gap is a
        registered split factor of the CUSIP, its value otherwise.
        """
        price = anomaly.reference_price
        ratio = row.price / price
        on_split_basis = any(
            abs(ratio * f - 1) <= self.split_tolerance or abs(ratio / f - 1) <= self.split_tolerance
            for f in self.split_factors.get(row.cusip, ())
        )
        if on_split_basis:
            shares = round(row.value / price)
            delta_shares = round(row.delta_shares + shares - row.shares)
            restated = Restatement(
                shares=shares,
                value=row.value,
                delta_shares=delta_shares,
                delta_value=delta_shares * price,
                delta=delta_label(shares, delta_shares),
            )
            return replace(anomaly, kind="shares", restated=restated)
        restated = Restatement(
            shares=round(row.shares),
            value=row.shares * price,
            delta_shares=round(row.delta_shares),
            delta_value=row.delta_shares * price,
            delta=row.delta,
        )
        return replace(anomaly, kind="value", restated=restated)

    def _carry(
        self,
        anomaly: CusipAnomaly,
        filed: Mapping[tuple[str, str, str], FiledRow],
        closed: Mapping[tuple[str, str], Mapping[str, float]],
        quarters: set[str],
    ) -> CusipAnomaly | None:
        """
        The fund's next filing of a share-restated CUSIP, its delta recomputed
        against the restated count; None when the fund filed nothing after it.
        """
        later = sorted(q for q in quarters if q > anomaly.quarter)
        if not later or anomaly.restated is None:
            return None
        quarter = later[0]
        factors = self.split_factors_fn(anomaly.quarter, quarter) if self.split_factors_fn else {}
        factor = factors.get(anomaly.cusip, 1.0)
        filed_row = filed[(anomaly.fund, anomaly.quarter, anomaly.cusip)]
        shift = round((anomaly.restated.shares - filed_row.shares) * factor)
        nxt = filed.get((anomaly.fund, quarter, anomaly.cusip))
        if nxt is not None:
            shares, delta_shares = round(nxt.shares), round(nxt.delta_shares) - shift
            value, delta_value = nxt.value, delta_shares * nxt.price
        elif anomaly.cusip in closed.get((anomaly.fund, quarter), {}):
            shares, value = 0, 0.0
            delta_shares = -round(anomaly.restated.shares * factor)
            delta_value = -anomaly.restated.value
        else:
            return None
        restated = Restatement(
            shares=shares,
            value=value,
            delta_shares=delta_shares,
            delta_value=delta_value,
            delta=delta_label(shares, delta_shares),
        )
        return CusipAnomaly(
            quarter=quarter,
            fund=anomaly.fund,
            cusip=anomaly.cusip,
            filed_company=anomaly.filed_company,
            filed_price=nxt.price if nxt else 0.0,
            reference_price=anomaly.reference_price,
            note=f"delta follows the {anomaly.quarter} share restatement",
            kind="carried",
            restated=restated,
        )

    def _match(
        self,
        flagged: list[tuple[CusipAnomaly, FiledRow]],
        closing: Mapping[str, float],
        median_of: Callable[[str], float | None],
    ) -> list[CusipAnomaly]:
        """
        Correct the flagged rows of one filing that have firm evidence (see the
        class docstring); every other row is returned unchanged.
        """
        own = {a.cusip for a, _ in flagged}
        targets: dict[str, tuple[str, str]] = {}
        for a, filed in flagged:
            candidates = [(c, "rotation") for c in sorted(own) if c != a.cusip]
            if filed.delta == "NEW":
                candidates += [
                    (c, "closed")
                    for c in sorted(set(closing) - own)
                    if closing[c] > 0
                    and abs(filed.shares / closing[c] - 1) <= self.match_shares_tolerance
                ]
            matches = [
                (c, origin)
                for c, origin in candidates
                if (median := median_of(c))
                and abs(a.filed_price / median - 1) <= self.match_tolerance
            ]
            if len(matches) == 1:
                targets[a.cusip] = matches[0]
        targets = self._consistent(targets)

        result: list[CusipAnomaly] = []
        for a, _ in flagged:
            if a.cusip not in targets:
                result.append(a)
                continue
            target, origin = targets[a.cusip]
            why = (
                "a rotated CUSIP of the same filing"
                if origin == "rotation"
                else "a position closed in the same filing"
            )
            note = (
                f"price {a.filed_price:.2f} matches {target} "
                f"({median_of(target):.2f} at the other funds), {why}"
            )
            result.append(replace(a, correct_cusip=target, note=note))
        return result

    @staticmethod
    def _consistent(targets: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
        """
        Keep the assignments no other row claims; rotations only when they close
        into a cycle (every CUSIP of the cycle moved to the next one).
        """
        claims = [t for t, _ in targets.values()]
        unique = {s: t for s, t in targets.items() if claims.count(t[0]) == 1}
        kept: dict[str, tuple[str, str]] = {}
        for source, (target, origin) in unique.items():
            if origin == "closed":
                kept[source] = (target, origin)
                continue
            seen, current = {source}, target
            while current in unique and unique[current][1] == "rotation" and current not in seen:
                seen.add(current)
                current = unique[current][0]
            if current == source:
                kept[source] = (target, origin)
        return kept

    @staticmethod
    def _anomaly(row: FiledRow, reference_price: float) -> CusipAnomaly:
        """
        Build the report entry for a flagged row.
        """
        return CusipAnomaly(
            quarter=row.quarter,
            fund=row.fund,
            cusip=row.cusip,
            filed_company=row.company,
            filed_price=row.price,
            reference_price=reference_price,
        )


def delta_label(shares: int, delta_shares: int) -> str:
    """
    The Delta column for a share count and its change, as the comparison writes it.
    """
    previous = shares - delta_shares
    if previous == 0:
        return "NEW"
    if shares == 0:
        return "CLOSE"
    if delta_shares == 0:
        return "NO CHANGE"
    return format_percentage(delta_shares / previous * 100, True)


def rows_from_quarter_file(quarter: str, fund: str, df: pd.DataFrame) -> list[FiledRow]:
    """
    The priced rows of one saved quarter CSV; the Total line and positions with
    no shares or value carry no price and are skipped.
    """
    holdings = df[df["CUSIP"] != "Total"]
    values = get_numeric_series(holdings["Value"])
    shares = pd.to_numeric(holdings["Shares"], errors="coerce")
    extra = holdings.reindex(columns=["Delta_Shares", "Delta"])
    deltas = pd.to_numeric(extra["Delta_Shares"], errors="coerce")
    labels = extra["Delta"].fillna("")
    rows: list[FiledRow] = []
    for cusip, company, value, count, delta, label in zip(
        holdings["CUSIP"], holdings["Company"], values, shares, deltas, labels, strict=True
    ):
        if pd.notna(count) and count > 0 and pd.notna(value) and value > 0:
            rows.append(
                FiledRow(
                    quarter=quarter,
                    fund=fund,
                    cusip=str(cusip),
                    company=str(company),
                    price=float(value) / float(count),
                    shares=float(count),
                    delta_shares=float(delta) if pd.notna(delta) else 0.0,
                    delta=str(label),
                )
            )
    return rows


def closed_from_quarter_file(df: pd.DataFrame) -> dict[str, float]:
    """
    The CUSIPs a saved quarter CSV marks as closed, with the share count the
    fund held before (the CLOSE row's negated share delta).
    """
    rows = df[df["Delta"] == "CLOSE"]
    sold = pd.to_numeric(rows["Delta_Shares"], errors="coerce").fillna(0)
    return {str(c): float(-d) for c, d in zip(rows["CUSIP"], sold, strict=True)}


def scan_database() -> list[CusipAnomaly]:
    """
    Run the detector over every saved quarter.
    """
    from pathlib import Path

    from app.analysis.splits import factors_between
    from app.database import get_all_quarters
    from app.database.quarters import get_all_quarter_files
    from app.database.splits import load_split_factors

    rows: list[FiledRow] = []
    closed: dict[tuple[str, str], dict[str, float]] = {}
    for quarter in get_all_quarters():
        for file in get_all_quarter_files(quarter):
            fund = Path(file).stem.replace("_", " ")
            df = pd.read_csv(file, dtype=str)
            rows += rows_from_quarter_file(quarter, fund, df)
            closed[(fund, quarter)] = closed_from_quarter_file(df)
    registry = load_split_factors()
    by_cusip: dict[str, set[float]] = defaultdict(set)
    for quarter_factors in registry.values():
        for cusip, factor in quarter_factors.items():
            by_cusip[cusip].add(factor)
    detector = CusipAnomalyDetector(
        split_factors=by_cusip,
        split_factors_fn=lambda prev, curr: factors_between(registry, prev, curr),
    )
    return detector.detect(rows, closed=closed)


def render_anomalies_markdown(anomalies: list[CusipAnomaly], limit: int = 25) -> str:
    """
    The anomaly section of the fetch run summary, one table of up to ``limit``
    rows with a count of the rest.
    """
    ordered = sorted(anomalies, key=lambda a: (a.quarter, a.fund, a.cusip))
    lines = ["## Filing price anomalies", ""]
    if not ordered:
        return "\n".join([*lines, "No price anomalies in the saved filings."])
    lines += [
        "| Quarter | Fund | CUSIP | Filed as | Filed price | Funds' price | Corrected to |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for a in ordered[:limit]:
        lines.append(
            f"| {a.quarter} | {markdown_safe(a.fund)} | {markdown_safe(a.cusip)} | "
            f"{markdown_safe(a.filed_company)} | {a.filed_price:,.2f} | "
            f"{a.reference_price:,.2f} | {a.correct_cusip or ''} |"
        )
    if len(ordered) > limit:
        lines.append(f"\n_…and {len(ordered) - limit} more in database/filing_anomalies.csv._")
    return "\n".join(lines)
