from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
import finnhub
import os
import time

# Load variables from .env file
load_dotenv()

class Finnhub:
    """
    Client for interacting with the Finnhub API.
    This class encapsulates the logic for looking up stock tickers and company information, including handling API keys, rate limiting, and fallback query strategies.
    """
    _COMMON_COMPANY_WORDS = {'the', 'corp', 'inc', 'group', 'ltd', 'co', 'plc', 'hldgs'}
    _MAX_QUERY_LENGTH = 20

    # Initialize API Key and Client at class level
    _API_KEY = os.getenv("FINNHUB_API_KEY")
    _CLIENT = finnhub.Client(api_key=_API_KEY) if _API_KEY else None

    if not _CLIENT:
        print("⚠️\u3000FINNHUB_API_KEY not found: Finnhub will not be used. Falling back to FinanceDatabase for ticker resolution.")


    @staticmethod
    def _is_rate_limit_exception(e):
        """
        Return True if the exception is a Finnhub 429 'rate limit error'.
        """
        return isinstance(e, finnhub.FinnhubAPIException) and '429' in str(e)


    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=30, max=60),
        retry=retry_if_exception(_is_rate_limit_exception.__func__),
        before_sleep=lambda rs: print(f"⚠️\u3000Finnhub API rate limit hit. Retrying in {rs.next_action.sleep:.0f}s... (Attempt #{rs.attempt_number})")
    )
    def _ticker_lookup(query):
        """
        Performs the actual symbol lookup using the Finnhub client.
        This function is decorated for retries.
        """
        time.sleep(1) # Pause to respect API rate limits
        return Finnhub._CLIENT.symbol_lookup(query)


    @staticmethod
    def _lookup(query):
        """
        Looks up a query on Finnhub and returns the best match.
        It calls the API with retry logic and then processes the response.
        """
        if not Finnhub._CLIENT:
            return None

        response_data = Finnhub._ticker_lookup(query)
        if response_data and response_data.get('result'):
            # Prioritize Common Stock/Equity for better accuracy
            for item in response_data['result']:
                if item.get('type') in ['Common Stock', 'Equity', 'STOCK']:
                    return item
            # Fallback to the first result if no common stock is found
            if response_data['result']:
                return response_data['result'][0]
        return None


    @staticmethod
    def get_ticker(cusip: str, company_name: str) -> str | None:
        """
        Attempts to get the ticker from Finnhub.io, using a series of fallback queries.
        Uses a retry mechanism for API rate limits.
        Queries in order:
        1. CUSIP
        2. Company Name
        3. First significant word of Company Name
        """
        # 1. Try with CUSIP
        best_match = Finnhub._lookup(cusip)

        # 2. Fallback to full issuer name (truncated)
        if not best_match and company_name:
            best_match = Finnhub._lookup(company_name[:Finnhub._MAX_QUERY_LENGTH])

        # 3. Fallback to the first word of the issuer name
        if not best_match and company_name:
            first_word = company_name.split(' ')[0]
            # Block common words
            if len(first_word) > 2 and first_word.lower() not in Finnhub._COMMON_COMPANY_WORDS:
                best_match = Finnhub._lookup(first_word)

        if not best_match:
            print(f"⚠️\u3000Finnhub: No ticker found for CUSIP {cusip} / Company '{company_name}'.")
            return None
        
        return best_match.get('symbol')


    @staticmethod
    def get_company(cusip: str) -> str | None:
        """
        Returns the original company name if provided, otherwise looks up the company name from Finnhub.io using CUSIP.
        """
        best_match = Finnhub._lookup(cusip)
        if best_match:
            return best_match.get('description', '').title()
        
        print(f"⚠️\u3000Finnhub: No company found for CUSIP {cusip}")
        return None
