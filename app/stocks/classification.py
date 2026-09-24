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
    3. LLM classification — Gemini flash-lite (Groq fallback) picks an Industry
       from the closed sector_hierarchy.csv vocabulary. Optional: skipped when
       no API key is set, so the chain degrades gracefully.

Returns "" when every step misses, so the row is still persistable.
"""

import os
import re
from typing import cast

from app.ai.clients.base_client import AIClient
from app.ai.clients.google_client import GoogleAIClient
from app.ai.clients.groq_client import GroqClient
from app.ai.response_parser import ResponseParser
from app.database import load_sector_hierarchy, load_stocks
from app.stocks.libraries.yfinance import YFinance
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

GEMINI_CLASSIFIER_MODEL = "gemini-3.5-flash-lite"
GROQ_CLASSIFIER_MODEL = GroqClient.DEFAULT_MODEL
# Gemini answers a bare 400 INVALID_ARGUMENT for enums past ~100-130 values.
GEMINI_MAX_ENUM = 100
SHELL_INDUSTRY = "Shell Companies"

# LLMs over-apply "Shell Companies" to small operating issuers, so it is only trusted on blank-check names.
_BLANK_CHECK_RE = re.compile(r"\b(?:acquisition|merger corp|blank check|spac)\b", re.IGNORECASE)


def _looks_like_blank_check(company: str) -> bool:
    """
    Whether a company name reads like a blank-check / SPAC vehicle.
    """
    return bool(_BLANK_CHECK_RE.search(company or ""))


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


def _build_prompt(ticker: str, company: str, vocabulary: list[str], operating: bool) -> str:
    """
    Builds the classification prompt over the closed Industry vocabulary.

    ``operating`` marks the re-ask after a rejected 'Shell Companies' answer.
    """
    vocab_block = "\n".join(f"- {industry}" for industry in vocabulary)
    rules = "Securities such as warrants, rights and units take the issuer's operating industry. "
    if operating:
        rules += "This company has an operating business: pick the industry it operates in."
    else:
        rules += (
            f"Answer '{SHELL_INDUSTRY}' only for a blank-check/SPAC company that has not "
            "yet completed a merger (no operating business)."
        )
    return (
        "Classify a publicly-traded security into exactly ONE Industry from the list.\n\n"
        f"Allowed industries (Yahoo Finance taxonomy):\n{vocab_block}\n\n"
        f"Company: {company}\nTicker: {ticker}\n\n"
        'Answer as JSON {"industry": "<Industry>"}, using the string exactly as it '
        f"appears in the list. {rules}"
    )


def _industry_schema(vocabulary: list[str], max_enum: int | None) -> dict:
    """
    JSON Schema for the answer: an enum over ``vocabulary`` unless it exceeds
    ``max_enum`` (then a plain string, validated in code).
    """
    field: dict = {"type": "string"}
    if max_enum is None or len(vocabulary) <= max_enum:
        field["enum"] = vocabulary
    return {
        "type": "object",
        "properties": {"industry": field},
        "required": ["industry"],
        "additionalProperties": False,
    }


def _ask_once(
    client: AIClient,
    ticker: str,
    company: str,
    vocabulary: list[str],
    operating: bool,
    max_enum: int | None,
) -> str | None:
    """
    Sends one classification request and returns the answer if it is in ``vocabulary``.
    """
    prompt = _build_prompt(ticker, company, vocabulary, operating)
    try:
        raw = client.generate_content(
            prompt, reasoning="low", response_schema=_industry_schema(vocabulary, max_enum)
        )
    except Exception:
        logger.warning(
            "Industry classification via %s failed for %s",
            client.get_model_name(),
            log_safe(ticker),
            exc_info=True,
        )
        return None
    answer = ResponseParser.parse_json(raw).get("industry")
    if isinstance(answer, str) and answer in vocabulary:
        return answer
    return None


def _ask(
    client: AIClient,
    ticker: str,
    company: str,
    vocabulary: list[str],
    max_enum: int | None = None,
) -> str | None:
    """
    Classifies with one provider, re-asking once without 'Shell Companies' when
    that label comes back for a name that is not a blank-check vehicle.
    """
    answer = _ask_once(client, ticker, company, vocabulary, operating=False, max_enum=max_enum)
    if answer != SHELL_INDUSTRY or _looks_like_blank_check(company):
        return answer
    logger.progress(
        "Re-asking without '%s' for operating-name %s", SHELL_INDUSTRY, log_safe(company)
    )
    operating_vocabulary = [industry for industry in vocabulary if industry != SHELL_INDUSTRY]
    return _ask_once(
        client, ticker, company, operating_vocabulary, operating=True, max_enum=max_enum
    )


def _llm_classify(ticker: str, company: str) -> str | None:
    """
    Picks an Industry from the sector_hierarchy.csv vocabulary with Gemini
    flash-lite, falling back to Groq when GOOGLE_API_KEY is missing or Gemini
    fails or answers outside the vocabulary. Returns None when neither yields
    a valid answer.
    """
    google_key = os.getenv("GOOGLE_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    if not google_key and not groq_key:
        return None

    hierarchy = load_sector_hierarchy()
    if hierarchy.empty:
        return None
    vocabulary = sorted(hierarchy["Industry"].unique())

    if google_key:
        gemini = GoogleAIClient(model=GEMINI_CLASSIFIER_MODEL, api_key=google_key)
        answer = _ask(gemini, ticker, company, vocabulary, GEMINI_MAX_ENUM)
        if answer:
            return answer
    if groq_key:
        groq = GroqClient(model=GROQ_CLASSIFIER_MODEL, api_key=groq_key)
        return _ask(groq, ticker, company, vocabulary)
    return None


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

    # Step 3 — LLM (optional, requires GOOGLE_API_KEY or GROQ_API_KEY).
    llm_answer = _llm_classify(ticker, company)
    if llm_answer:
        return llm_answer

    return ""
