from dataclasses import dataclass

import numpy as np
import pandas as pd

# Number of names the five non-Avg-Portfolio strategies hold each quarter.
DEFAULT_TOP_N = 30


@dataclass(frozen=True)
class StrategySpec:
    """
    Definition of a backtestable consensus strategy.

    Mirrors a `/quarterly` tab: ``sort_column`` + ``ascending`` reproduce the
    tab's default ranking, and the filter flags reproduce its default filters.
    Selection picks the screen; weighting always uses ``Avg_Portfolio_Pct``
    (the universal conviction weight) so strategies differ only in *what* they
    hold, not *how* it is weighted.
    """

    strategy_id: str
    label: str
    sort_column: str
    ascending: bool = False
    use_min_holders: bool = False
    exclude_infinite_delta: bool = False
    capped: bool = True  # if False, top_n is ignored (Avg Portfolio keeps every passing name)
    # "positive"/"negative" restricts the screen to that delta sign; None = no constraint.
    # (Decreasing must hold only shrinking positions, Increasing only growing ones.)
    delta_sign: str | None = None
    # Min-holders threshold = ceil(funds / min_holders_divisor); only used when use_min_holders.
    min_holders_divisor: int = 10


# Order matches the /quarterly tab order; ids are stable (used in CSV + UI).
STRATEGIES: list[StrategySpec] = [
    StrategySpec(
        "avg_portfolio", "Avg Portfolio", "Avg_Portfolio_Pct", use_min_holders=True, capped=False
    ),
    StrategySpec("consensus", "Consensus Buys", "Net_Buyers"),
    StrategySpec("new_consensus", "New Consensus", "New_Holder_Count"),
    StrategySpec("big_bets", "Big Bets", "Max_Portfolio_Pct"),
    StrategySpec(
        "increasing",
        "Increasing",
        "Delta",
        use_min_holders=True,
        exclude_infinite_delta=True,
        delta_sign="positive",
    ),
    StrategySpec(
        "decreasing",
        "Decreasing",
        "Total_Delta_Value",
        ascending=True,
        delta_sign="negative",
    ),
]

_BY_ID = {s.strategy_id: s for s in STRATEGIES}


def strategy_by_id(strategy_id: str) -> StrategySpec:
    """
    Return the StrategySpec for an id, raising KeyError if unknown.
    """
    return _BY_ID[strategy_id]


def strategy_definitions() -> list[dict]:
    """
    Language-agnostic canonical spec for every strategy.

    This is the single source of truth pinned by ``tests/fixtures/strategies.json``;
    the TypeScript ``src/lib/strategies.ts`` guard test asserts it matches, so the
    backtest and the QuarterlyTrends UI can't define the strategies differently.
    ``metric`` is the lower-cased ranking column (the cross-language key).
    """
    return [
        {
            "id": s.strategy_id,
            "label": s.label,
            "metric": s.sort_column.lower(),
            "ascending": s.ascending,
            "min_holders": s.use_min_holders,
            "exclude_infinite_delta": s.exclude_infinite_delta,
            "capped": s.capped,
            "top_n": DEFAULT_TOP_N if s.capped else None,
            "delta_sign": s.delta_sign,
            "min_holders_divisor": s.min_holders_divisor,
        }
        for s in STRATEGIES
    ]


def select_screen(
    df: pd.DataFrame, spec: StrategySpec, *, threshold: int, top_n: int = DEFAULT_TOP_N
) -> pd.DataFrame:
    """
    Select a strategy's screen from the quarter's stock-level analysis frame.

    Applies the strategy's min-holders / infinite-delta filters, ranks by its
    sort column, and caps to ``top_n`` rows (unless the spec is uncapped). The
    returned frame is ordered best-first and retains ``Ticker`` and
    ``Avg_Portfolio_Pct`` for downstream weighting.
    """
    selected = df
    if spec.use_min_holders:
        selected = selected[selected["Holder_Count"] >= threshold]
    if spec.exclude_infinite_delta:
        selected = selected[np.isfinite(selected[spec.sort_column])]
    else:
        selected = selected[selected[spec.sort_column].notna()]
    if spec.delta_sign == "positive":
        selected = selected[selected[spec.sort_column] > 0]
    elif spec.delta_sign == "negative":
        selected = selected[selected[spec.sort_column] < 0]
    selected = selected.sort_values(spec.sort_column, ascending=spec.ascending, kind="stable")
    if spec.capped:
        selected = selected.head(top_n)
    return selected
