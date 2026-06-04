"""
Industry resolver: best-effort chain that returns a Yahoo-taxonomy Industry
string for a given ticker / company. Used by `TickerResolver.resolve_ticker`
and `TickerResolver.assign_cusip` so every new row landing in stocks.csv has
an Industry whenever possible.

Chain (each step short-circuits if it produces a value):
    1. yfinance.info.industry — direct, fast, free.
    2. Same-Company lookup in stocks.csv — propagates the Industry from any
       row that already carries it for the same company name (typical case:
       the underlying common stock was resolved earlier and now its warrant /
       unit / share-class hits the resolver).
    3. Groq LLM classification — picks an Industry string from the closed
       sector_hierarchy.csv vocabulary. Optional: skipped when GROQ_API_KEY
       is unset, so the chain degrades gracefully.

Returns "" when every step misses, so the row is still persistable.
"""

import os
import re
from typing import cast

import requests

from app.database import load_sector_hierarchy, load_stocks
from app.stocks.libraries.yfinance import YFinance
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 20


def _match_by_company_name(company: str) -> str:
    """
    Returns the Industry of any existing stocks.csv row with the exact same
    Company name and a non-empty Industry, or "" if none.
    """
    if not company:
        return ""
    stocks = load_stocks()
    if stocks.empty:
        return ""
    matches = stocks[(stocks["Company"] == company) & (stocks["Industry"] != "")]
    if matches.empty:
        return ""
    return cast(str, matches.iloc[0]["Industry"])


def _llm_classify(ticker: str, company: str) -> str | None:
    """
    Asks Groq's llama-3.3-70b to pick an Industry from the closed vocabulary in
    sector_hierarchy.csv. Returns None when GROQ_API_KEY is missing, the API
    errors, or the response is not a recognised Industry string.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    hierarchy = load_sector_hierarchy()
    if hierarchy.empty:
        return None
    vocabulary = sorted(hierarchy["Industry"].unique())
    vocab_block = "\n".join(f"- {industry}" for industry in vocabulary)

    prompt = (
        "Classify a publicly-traded security into exactly ONE Industry from the list.\n\n"
        f"Allowed industries (Yahoo Finance taxonomy):\n{vocab_block}\n\n"
        f"Company: {company}\nTicker: {ticker}\n\n"
        "Output ONLY the chosen Industry string, exactly as it appears in the list. "
        "If the security is a warrant, unit, SPAC pre-merger or other special "
        "structure with no operating business, answer with 'Shell Companies'."
    )

    try:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 32,
            },
            timeout=GROQ_TIMEOUT,
        )
    except requests.RequestException:
        logger.warning("Groq classification: network error for %s", log_safe(ticker), exc_info=True)
        return None

    if not response.ok:
        logger.warning(
            "Groq classification: HTTP %s for ticker %s",
            response.status_code,
            log_safe(ticker),
        )
        return None

    try:
        content = response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, ValueError, IndexError):
        return None

    cleaned = re.sub(r"^[`\"']+|[`\"']+$", "", content).strip()
    if cleaned in vocabulary:
        return cleaned
    # Case-insensitive recovery: model may shuffle casing on edge cases.
    lowered = {industry.lower(): industry for industry in vocabulary}
    return lowered.get(cleaned.lower())


def resolve_industry(ticker: str, company: str) -> str:
    """
    Returns the best-effort Industry for (ticker, company). Empty string if
    every fallback misses, so callers can persist the row and a later AI
    backfill can revisit it.
    """
    # Step 1 — yfinance, direct.
    try:
        classification = YFinance.get_classification(ticker) or {}
    except Exception:
        classification = {}
    industry = classification.get("industry")
    if industry:
        return industry

    # Step 2 — same Company already classified in stocks.csv.
    name_match = _match_by_company_name(company)
    if name_match:
        return name_match

    # Step 3 — Groq LLM (optional, requires GROQ_API_KEY).
    llm_answer = _llm_classify(ticker, company)
    if llm_answer:
        return llm_answer

    return ""
