"""
Service layer for applying NASDAQ ticker (symbol) changes to the database.

Kept separate from the HTTP handlers in app/server.py so the orchestration is
unit-testable without FastAPI and reusable from the CLI.
"""

from app.database import find_cusips_for_ticker, update_ticker
from app.stocks.libraries.nasdaq import Nasdaq
from app.stocks.libraries.yfinance import YFinance


def detect_applicable_ticker_changes() -> dict:
    """
    Fetch recent NASDAQ symbol changes and return those whose old symbol maps to
    one or more CUSIPs already tracked in stocks.csv.

    Shape: ``{"total_changes": int, "applicable": [{"oldSymbol", "newSymbol",
    "companyName", "cusips"}, ...]}``.
    """
    changes = Nasdaq.get_symbol_changes()
    applicable = []
    for change in changes:
        old_symbol = change.get("oldSymbol", "")
        matching = find_cusips_for_ticker(old_symbol)
        if matching:
            applicable.append(
                {
                    "oldSymbol": old_symbol,
                    "newSymbol": change.get("newSymbol", ""),
                    "companyName": change.get("companyName", ""),
                    "cusips": [s["CUSIP"] for s in matching],
                }
            )
    return {"total_changes": len(changes), "applicable": applicable}


def apply_ticker_changes() -> dict:
    """
    Detect applicable NASDAQ ticker changes and apply each across the database,
    enriching the new company name from YFinance when available.

    Shape: ``{"applied": [{"old", "new", "companyName"}, ...], "message": str}``.
    """
    changes = Nasdaq.get_symbol_changes()
    applied = []
    for change in changes:
        old_symbol = change.get("oldSymbol", "")
        new_symbol = change.get("newSymbol", "")
        matching = find_cusips_for_ticker(old_symbol)
        if matching:
            company = YFinance.get_company("", ticker=new_symbol) or change.get("companyName", "")
            update_ticker(old_symbol, new_symbol, new_company=company)
            applied.append({"old": old_symbol, "new": new_symbol, "companyName": company})

    if not applied:
        message = "No applicable ticker changes found on NASDAQ."
    else:
        lines = [f"{a['old']} → {a['new']} ({a['companyName']})" for a in applied]
        message = f"Applied {len(applied)} ticker change(s):\n" + "\n".join(lines)
    return {"applied": applied, "message": message}
