import os

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from dotenv import load_dotenv

from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)


class FMP:
    """
    Client for Financial Modeling Prep's free-tier /stable/profile endpoint.

    Used for reverse ticker → CUSIP resolution (Form 4 path in
    TickerResolver.assign_cusip) and to expose sector / industry / country
    fields when needed.

    Not a member of the CUSIP-resolution chain: the CUSIP search endpoint is
    gated behind a paid plan, so FMP does not implement get_ticker / get_company.

    Free tier: 250 requests/day. Requires FMP_API_KEY in the environment;
    without the key the client returns None for every lookup.
    """

    load_dotenv()
    API_KEY = os.getenv("FMP_API_KEY")
    ENDPOINT = "https://financialmodelingprep.com/stable/profile"
    TIMEOUT = 10

    @staticmethod
    def _fetch(ticker: str) -> dict | None:
        """
        Calls the /stable/profile endpoint for a ticker and returns the first
        record. Returns None when the API key is missing, the network fails,
        the response is non-OK, or the payload is empty.
        """
        if not FMP.API_KEY:
            return None

        try:
            response = requests.get(
                FMP.ENDPOINT,
                params={"symbol": ticker, "apikey": FMP.API_KEY},
                timeout=FMP.TIMEOUT,
            )
        except RequestException:
            logger.warning("FMP: network error", exc_info=True)
            return None

        if not response.ok:
            logger.warning("FMP: HTTP %s for ticker %s", response.status_code, log_safe(ticker))
            return None

        try:
            data = response.json()
        except ValueError:
            logger.warning("FMP: invalid JSON response", exc_info=True)
            return None

        if not data or not isinstance(data, list):
            return None

        first = data[0]
        return first if isinstance(first, dict) else None

    @staticmethod
    def get_cusip(ticker: str) -> str | None:
        """
        Returns the CUSIP for a US-listed ticker, or None if the security is
        non-US (FMP omits CUSIP for foreign issuers) or the ticker is unknown.
        """
        record = FMP._fetch(ticker)
        if not record:
            logger.warning("FMP: no profile found for ticker %s", log_safe(ticker))
            return None
        cusip = record.get("cusip")
        return cusip or None

    @staticmethod
    def get_profile(ticker: str) -> dict | None:
        """
        Returns a profile dict {cusip, sector, industry, country} for the ticker,
        or None if the ticker has no profile. ISIN is intentionally omitted —
        we always start from CUSIP and SEC filings do not carry ISIN.
        """
        record = FMP._fetch(ticker)
        if not record:
            return None
        return {
            "cusip": record.get("cusip") or None,
            "sector": record.get("sector") or None,
            "industry": record.get("industry") or None,
            "country": record.get("country") or None,
        }
