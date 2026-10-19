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

    Any other flagged row is restated at the funds' price. Its share count is
    put on the value-implied basis when the gap equals a split factor registered
    for the CUSIP (``split_factors``, within ``split_tolerance``), or when that
    count continues one of the fund's adjacent filings (``continuity_tolerance``)
    while the filed count continues neither; otherwise its value is restated.
    Any share restatement corrects the delta of the fund's next filing, compared
    against the wrong count across ``split_factors_fn(previous, current)``, also
    when that filing is restated itself.

    A filing valued at another date than the quarter end shows as most of its
    book off the funds' prices (see ``_stale_filings``): every row of it more than
    ``stale_gap`` off, even within ``price_tolerance``, has its value restated.
    """

    price_tolerance: float = 0.4
    min_reporters: int = 3
    match_tolerance: float = 0.05
    match_shares_tolerance: float = 0.5
    split_tolerance: float = 0.02
    continuity_tolerance: float = 0.05
    split_factors: Mapping[str, Iterable[float]] = field(default_factory=dict)
    split_factors_fn: Callable[[str, str], Mapping[str, float]] | None = None
    stale_gap: float = 0.05
    stale_share: float = 0.4
    stale_min_rows: int = 10

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

        stale = self._stale_filings(priced, medians)
        by_filing: dict[tuple[str, str], list[tuple[CusipAnomaly, FiledRow]]] = defaultdict(list)
        stale_rows: list[tuple[CusipAnomaly, FiledRow]] = []
        for r in priced:
            median = medians.get((r.quarter, r.cusip))
            if not median:
                continue
            gap = abs(r.price / median - 1)
            if gap > self.price_tolerance:
                by_filing[(r.fund, r.quarter)].append((self._anomaly(r, median), r))
            elif gap > self.stale_gap and (r.fund, r.quarter) in stale:
                note = "the filing is priced at another date than the funds' quarter end"
                stale_rows.append((replace(self._anomaly(r, median), note=note), r))

        filed = {(r.fund, r.quarter, r.cusip): r for r in priced}
        fund_quarters: dict[str, set[str]] = defaultdict(set)
        for fund, quarter in [(r.fund, r.quarter) for r in priced] + list(closed or {}):
            fund_quarters[fund].add(quarter)
        anomalies: list[CusipAnomaly] = [self._value_restatement(a, r) for a, r in stale_rows]
        for (fund, quarter), flagged in by_filing.items():
            closing = (closed or {}).get((fund, quarter), {})
            for a in self._match(flagged, closing, lambda c, q=quarter: medians.get((q, c))):
                if a.correct_cusip:
                    anomalies.append(replace(a, kind="cusip"))
                else:
                    row = filed[(a.fund, a.quarter, a.cusip)]
                    neighbours = self._neighbours(row, filed, fund_quarters[fund])
                    anomalies.append(self._restate(a, row, neighbours))
        anomalies = self._follow_share_restatements(anomalies, filed, closed or {}, fund_quarters)
        return sorted(anomalies, key=lambda a: (a.quarter, a.fund, a.cusip))

    def _factor(self, cusip: str, previous: str, current: str) -> float:
        """
        The split factor of ``cusip`` between two of a fund's filings, 1 without one.
        """
        factors = self.split_factors_fn(previous, current) if self.split_factors_fn else {}
        return factors.get(cusip, 1.0)

    def _neighbours(
        self, row: FiledRow, filed: Mapping[tuple[str, str, str], FiledRow], quarters: set[str]
    ) -> list[tuple[str, float]]:
        """
        The share counts of the row's position in the fund's previous and next
        filings, on the row's basis: (quarter, shares) for each one that holds it.
        The previous count comes from the row's own delta, so it is known even
        when that filing predates the database.
        """
        earlier = sorted(q for q in quarters if q < row.quarter)
        later = sorted(q for q in quarters if q > row.quarter)
        neighbours: list[tuple[str, float]] = []
        previous = row.shares - row.delta_shares
        if row.delta != "NEW" and previous > 0:
            neighbours.append((earlier[-1] if earlier else "previous", previous))
        nxt = filed.get((row.fund, later[0], row.cusip)) if later else None
        if later and nxt is not None:
            neighbours.append(
                (later[0], nxt.shares / self._factor(row.cusip, row.quarter, later[0]))
            )
        return neighbours

    def _continued(
        self, filed_shares: float, implied_shares: float, neighbours: list[tuple[str, float]]
    ) -> tuple[str, float] | None:
        """
        The adjacent filing the value-implied share count continues, when the filed
        count continues none: the share count is then the wrong figure.
        """

        def close(count: float, other: float) -> bool:
            """
            Whether two share counts are the same holding.
            """
            return abs(count / other - 1) <= self.continuity_tolerance

        if any(close(filed_shares, n) for _, n in neighbours):
            return None
        return next(((q, n) for q, n in neighbours if close(implied_shares, n)), None)

    def _restate(
        self, anomaly: CusipAnomaly, row: FiledRow, neighbours: list[tuple[str, float]]
    ) -> CusipAnomaly:
        """
        Restate a row at the funds' price: its share count when the gap is a
        registered split factor of the CUSIP or the value continues an adjacent
        filing (see ``_continued``), its value otherwise.
        """
        price = anomaly.reference_price
        ratio = row.price / price
        on_split_basis = any(
            abs(ratio * f - 1) <= self.split_tolerance or abs(ratio / f - 1) <= self.split_tolerance
            for f in self.split_factors.get(row.cusip, ())
        )
        continued = (
            None if on_split_basis else self._continued(row.shares, row.value / price, neighbours)
        )
        if on_split_basis or continued:
            shares = round(row.value / price)
            delta_shares = round(row.delta_shares + shares - row.shares)
            restated = Restatement(
                shares=shares,
                value=row.value,
                delta_shares=delta_shares,
                delta_value=delta_shares * price,
                delta=delta_label(shares, delta_shares),
            )
            note = (
                f"value is {shares:,} shares at the funds' price, like the {continued[0]} "
                f"filing's {continued[1]:,.0f}"
                if continued
                else ""
            )
            return replace(anomaly, kind="shares", restated=restated, note=note)
        return self._value_restatement(anomaly, row)

    @staticmethod
    def _value_restatement(anomaly: CusipAnomaly, row: FiledRow) -> CusipAnomaly:
        """
        The row at the funds' price with its filed share count.
        """
        price = anomaly.reference_price
        restated = Restatement(
            shares=round(row.shares),
            value=row.shares * price,
            delta_shares=round(row.delta_shares),
            delta_value=row.delta_shares * price,
            delta=row.delta,
        )
        return replace(anomaly, kind="value", restated=restated)

    def _stale_filings(
        self, priced: list[FiledRow], medians: Mapping[tuple[str, str], float]
    ) -> set[tuple[str, str]]:
        """
        The (fund, quarter) filings valued at another date: at least
        ``stale_min_rows`` rows the funds price, and ``stale_share`` of their
        filed value more than ``stale_gap`` away from the funds' price.
        """
        judged: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
        for r in priced:
            median = medians.get((r.quarter, r.cusip))
            if not median:
                continue
            tally = judged[(r.fund, r.quarter)]
            tally[0] += 1
            tally[1] += r.value
            if abs(r.price / median - 1) > self.stale_gap:
                tally[2] += r.value
        return {
            filing
            for filing, (count, total, off) in judged.items()
            if count >= self.stale_min_rows and total > 0 and off / total >= self.stale_share
        }

    def _follow_share_restatements(
        self,
        anomalies: list[CusipAnomaly],
        filed: Mapping[tuple[str, str, str], FiledRow],
        closed: Mapping[tuple[str, str], Mapping[str, float]],
        fund_quarters: Mapping[str, set[str]],
    ) -> list[CusipAnomaly]:
        """
        Correct the delta of the fund's next filing after every share restatement:
        shifted in place when that filing is restated itself, a carried row otherwise.
        """
        index = {(a.fund, a.quarter, a.cusip): i for i, a in enumerate(anomalies)}
        result = list(anomalies)
        carried: list[CusipAnomaly] = []
        for a in anomalies:
            later = sorted(q for q in fund_quarters[a.fund] if q > a.quarter)
            if a.kind != "shares" or a.restated is None or not later:
                continue
            quarter = later[0]
            factor = self._factor(a.cusip, a.quarter, quarter)
            shift = round((a.restated.shares - filed[(a.fund, a.quarter, a.cusip)].shares) * factor)
            i = index.get((a.fund, quarter, a.cusip))
            if i is not None:
                result[i] = self._shifted(result[i], shift, a.quarter)
            elif carry := self._carry(a, quarter, factor, shift, filed, closed):
                carried.append(carry)
        return result + carried

    @staticmethod
    def _shifted(anomaly: CusipAnomaly, shift: int, previous: str) -> CusipAnomaly:
        """
        A restated row whose delta was measured against a count the ``previous``
        filing's share restatement moved by ``shift``.
        """
        if anomaly.restated is None or shift == 0:
            return anomaly
        delta_shares = anomaly.restated.delta_shares - shift
        restated = replace(
            anomaly.restated,
            delta_shares=delta_shares,
            delta_value=delta_shares * anomaly.reference_price,
            delta=delta_label(anomaly.restated.shares, delta_shares),
        )
        note = "; ".join(
            filter(None, [anomaly.note, f"delta follows the {previous} share restatement"])
        )
        return replace(anomaly, restated=restated, note=note)

    @staticmethod
    def _carry(
        anomaly: CusipAnomaly,
        quarter: str,
        factor: float,
        shift: int,
        filed: Mapping[tuple[str, str, str], FiledRow],
        closed: Mapping[tuple[str, str], Mapping[str, float]],
    ) -> CusipAnomaly | None:
        """
        The fund's next filing (``quarter``) of a share-restated CUSIP that is not
        flagged itself, its delta recomputed against the restated count; None when
        that filing neither holds nor closes the position.
        """
        assert anomaly.restated is not None
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
