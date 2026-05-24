import os

import requests
from dotenv import load_dotenv

from app.stocks.libraries.base_library import FinanceLibrary
from app.stocks.utils.identifiers import normalize_ticker
from app.utils.logger import get_logger, log_safe
from app.utils.strings import format_string

logger = get_logger(__name__)


class OpenFIGI(FinanceLibrary):
    """
    Client for OpenFIGI's identifier mapping API (https://www.openfigi.com/api).

    Resolves CUSIP → ticker and CUSIP → company name. OpenFIGI does not expose
    CUSIPs in mapping responses, so reverse ticker → CUSIP is not supported here.

    OPENFIGI_API_KEY is optional: without a key the public endpoint allows
    ~25 requests/minute; with a key the limit is ~250/minute.
    """

    load_dotenv()
    API_KEY = os.getenv("OPENFIGI_API_KEY")
    ENDPOINT = "https://api.openfigi.com/v3/mapping"
    TIMEOUT = 10
    PREFERRED_SECURITY_TYPES = {"Common Stock", "Depositary Receipt", "ADR", "REIT", "ETP"}

    @staticmethod
    def _post(payload: list[dict]) -> list | None:
        """
        POSTs a mapping payload to OpenFIGI. Returns the parsed JSON list on
        success, or None on rate limit / HTTP error / network failure.
        """
        headers = {"Content-Type": "application/json"}
        if OpenFIGI.API_KEY:
            headers["X-OPENFIGI-APIKEY"] = OpenFIGI.API_KEY

        try:
            response = requests.post(
                OpenFIGI.ENDPOINT,
                json=payload,
                headers=headers,
                timeout=OpenFIGI.TIMEOUT,
            )
        except requests.RequestException:
            logger.warning("OpenFIGI: network error", exc_info=True)
            return None

        if response.status_code == 429:
            logger.warning("OpenFIGI: rate limit hit (HTTP 429)")
            return None

        if not response.ok:
            logger.warning("OpenFIGI: HTTP %s response", response.status_code)
            return None

        try:
            return response.json()
        except ValueError:
            logger.warning("OpenFIGI: invalid JSON response", exc_info=True)
            return None

    @staticmethod
    def _lookup_by_cusip(cusip: str) -> dict | None:
        """
        Looks up a CUSIP and returns the best-matching record, preferring
        Common Stock and similar equity-like security types.
        """
        results = OpenFIGI._post([{"idType": "ID_CUSIP", "idValue": cusip}])
        if not results:
            return None

        first = results[0]
        if not isinstance(first, dict):
            return None

        data = first.get("data") or []
        if not data:
            return None

        for item in data:
            if item.get("securityType") in OpenFIGI.PREFERRED_SECURITY_TYPES:
                return item

        return data[0]

    @staticmethod
    def get_ticker(cusip: str, **kwargs) -> str | None:
        """
        Returns the ticker for a given CUSIP, or None if no match.
        """
        match = OpenFIGI._lookup_by_cusip(cusip)
        if not match:
            logger.warning("OpenFIGI: No ticker found for CUSIP %s", log_safe(cusip))
            return None

        ticker = match.get("ticker")
        if not ticker:
            return None
        return normalize_ticker(ticker) or None

    @staticmethod
    def get_company(cusip: str, **kwargs) -> str | None:
        """
        Returns the formatted company name for a given CUSIP, or None.
        """
        match = OpenFIGI._lookup_by_cusip(cusip)
        if not match:
            logger.warning("OpenFIGI: No company found for CUSIP %s", log_safe(cusip))
            return None

        name = match.get("name")
        if not name:
            return None
        return format_string(name)
