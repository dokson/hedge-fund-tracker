import pandas as pd

from app.stocks.ticker_resolver import TickerResolver
from app.utils.logger import get_logger, log_safe
from app.utils.pd import coalesce, format_value_series
from app.utils.strings import format_percentage, format_value

logger = get_logger(__name__)


def _is_equity_cusip(cusip: object) -> bool:
    """
    Returns True for equity-style CUSIPs: 9 characters with a numeric issue
    code (positions 7-8). Debt issues use alphabetic issue codes, so a bond
    of the same issuer is never mistaken for the equity.
    """
    return isinstance(cusip, str) and len(cusip) == 9 and cusip[6:8].isdigit()


def _link_cusip_changes(df_comparison: pd.DataFrame) -> pd.DataFrame:
    """
    Collapses NEW/CLOSE row pairs resolving to the same ticker into a single
    continuing position, so a CUSIP change between quarters (reorganization,
    reverse split, merger) is not reported as a closed position plus a new one.
    Only unambiguous 1:1 pairs of equity-style CUSIPs are linked (a debt CUSIP
    resolving to the issuer's ticker is a different instrument, not a CUSIP
    change); linked rows are flagged via 'CUSIP_Changed' and keep the recent
    CUSIP.
    """
    df_comparison["CUSIP_Changed"] = False

    equity_mask = df_comparison["CUSIP"].map(_is_equity_cusip)
    new_mask = (
        equity_mask
        & (df_comparison["Shares_previous"] == 0)
        & (df_comparison["Shares"] > 0)
        & (df_comparison["Value"] > 0)
    )
    close_mask = (
        equity_mask
        & (df_comparison["Shares"] == 0)
        & (df_comparison["Shares_previous"] > 0)
        & (df_comparison["Value_previous"] > 0)
    )

    candidate_tickers = df_comparison.loc[new_mask | close_mask, "Ticker"].dropna().unique()
    rows_to_drop = []
    for ticker in candidate_tickers:
        if not ticker:
            continue
        new_rows = df_comparison.index[new_mask & (df_comparison["Ticker"] == ticker)]
        close_rows = df_comparison.index[close_mask & (df_comparison["Ticker"] == ticker)]
        if len(new_rows) != 1 or len(close_rows) != 1:
            continue
        new_row, close_row = new_rows[0], close_rows[0]
        df_comparison.at[new_row, "Shares_previous"] = df_comparison.at[
            close_row, "Shares_previous"
        ]
        df_comparison.at[new_row, "Value_previous"] = df_comparison.at[close_row, "Value_previous"]
        df_comparison.at[new_row, "CUSIP_Changed"] = True
        rows_to_drop.append(close_row)
        logger.info(
            "Linked CUSIP change for %s: %s → %s",
            log_safe(str(ticker)),
            log_safe(str(df_comparison.at[close_row, "CUSIP"])),
            log_safe(str(df_comparison.at[new_row, "CUSIP"])),
            emoji="🔗",
        )

    return df_comparison.drop(index=rows_to_drop)


def generate_comparison(df_recent: pd.DataFrame, df_previous: pd.DataFrame | None) -> pd.DataFrame:
    """
    Generates a comparison report between the two DataFrames, calculating percentage change and indicating new positions.
    """
    if df_previous is None:
        df_previous = pd.DataFrame(columns=df_recent.columns)

    df_comparison = pd.merge(
        df_recent, df_previous, on=["CUSIP"], how="outer", suffixes=("_recent", "_previous")
    )

    df_comparison["Shares"] = (
        pd.to_numeric(df_comparison["Shares_recent"], errors="coerce").fillna(0).astype("int64")
    )
    df_comparison["Shares_previous"] = (
        pd.to_numeric(df_comparison["Shares_previous"], errors="coerce").fillna(0).astype("int64")
    )
    df_comparison["Value"] = (
        pd.to_numeric(df_comparison["Value_recent"], errors="coerce").fillna(0).astype("int64")
    )
    df_comparison["Value_previous"] = (
        pd.to_numeric(df_comparison["Value_previous"], errors="coerce").fillna(0).astype("int64")
    )

    df_comparison["Company"] = coalesce(
        df_comparison["Company_recent"], df_comparison["Company_previous"]
    )

    df_comparison = TickerResolver.resolve_ticker(df_comparison)
    df_comparison = _link_cusip_changes(df_comparison)

    df_comparison["Price_per_Share"] = coalesce(
        df_comparison["Value"] / df_comparison["Shares"],
        df_comparison["Value_previous"] / df_comparison["Shares_previous"],
    )
    df_comparison["Delta_Shares"] = df_comparison["Shares"] - df_comparison["Shares_previous"]
    df_comparison["Delta_Value"] = df_comparison["Delta_Shares"] * df_comparison["Price_per_Share"]
    df_comparison["Delta%"] = (
        df_comparison["Delta_Shares"] / df_comparison["Shares_previous"].replace(0, pd.NA)
    ) * 100

    # Share counts are not comparable across a CUSIP change: deltas for linked
    # rows are value-based, with Delta_Shares expressed in recent-share terms.
    linked = df_comparison["CUSIP_Changed"]
    if linked.any():
        delta_value = (
            df_comparison.loc[linked, "Value"] - df_comparison.loc[linked, "Value_previous"]
        )
        df_comparison.loc[linked, "Delta_Value"] = delta_value
        df_comparison.loc[linked, "Delta_Shares"] = (
            (delta_value / df_comparison.loc[linked, "Price_per_Share"]).round().astype("int64")
        )
        df_comparison.loc[linked, "Delta%"] = (
            delta_value / df_comparison.loc[linked, "Value_previous"]
        ) * 100

    df_comparison["Delta"] = df_comparison.apply(
        lambda row: (
            format_percentage(row["Delta%"], True)
            if row["CUSIP_Changed"]
            else "NEW"
            if row["Shares_previous"] == 0
            else "CLOSE"
            if row["Shares"] == 0
            else "NO CHANGE"
            if row["Shares"] == row["Shares_previous"]
            else format_percentage(row["Delta%"], True)
        ),
        axis=1,
    )

    total_portfolio_value = df_comparison["Value"].sum()
    previous_portfolio_value = df_comparison["Value_previous"].sum()
    total_delta_value = df_comparison["Delta_Value"].sum()

    total_delta = (
        total_delta_value / previous_portfolio_value * 100
        if previous_portfolio_value != 0
        else total_delta_value / total_portfolio_value * 100
    )

    # Order results by Delta_Value descending
    df_comparison = df_comparison.sort_values(by=["Delta_Value", "Value"], ascending=[False, False])

    # Format fields
    df_comparison["Portfolio%"] = ((df_comparison["Value"] / total_portfolio_value) * 100).apply(
        lambda x: format_percentage(x, decimal_places=2) if 0.01 <= x < 1 else format_percentage(x)
    )
    df_comparison["Value"] = format_value_series(df_comparison["Value"])
    df_comparison["Delta_Value"] = format_value_series(df_comparison["Delta_Value"])

    df_comparison = df_comparison[
        [
            "CUSIP",
            "Ticker",
            "Company",
            "Shares",
            "Delta_Shares",
            "Value",
            "Delta_Value",
            "Delta",
            "Portfolio%",
        ]
    ]

    # Final Total row
    total_row = pd.DataFrame(
        [
            {
                "CUSIP": "Total",
                "Ticker": "",
                "Company": "",
                "Shares": "",
                "Delta_Shares": "",
                "Value": format_value(total_portfolio_value),
                "Delta_Value": format_value(total_delta_value),
                "Delta": format_percentage(total_delta, True),
                "Portfolio%": format_percentage(100),
            }
        ]
    )

    return pd.concat([df_comparison, total_row], ignore_index=True)
