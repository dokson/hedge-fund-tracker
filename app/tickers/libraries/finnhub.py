from app.tickers.libraries.base_library import FinanceLibrary
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
import finnhub
import os
import time


# Load variables from .env file
load_dotenv()

class Finnhub(FinanceLibrary):
    """
    Client for interacting with the Finnhub API.
    This class encapsulates the logic for looking up stock tickers and company information, including handling API keys, rate limiting, and fallback query strategies.
    """
    COMMON_COMPANY_WORDS = {'the', 'corp', 'inc', 'group', 'ltd', 'co', 'plc', 'hldgs'}
    MAX_QUERY_LENGTH = 20

    # Initialize API Key and Client at class level
    API_KEY = os.getenv("FINNHUB_API_KEY")
    CLIENT = finnhub.Client(api_key=API_KEY) if API_KEY else None

    if not CLIENT:
        print("⚠️\u3000FINNHUB_API_KEY not found: Finnhub will not be used. Falling back to FinanceDatabase for ticker resolution.")


    @classmethod
    def _is_rate_limit_exception(cls, e):
        """
        Return True if the exception is a Finnhub 429 'rate limit error'.
        """
        return isinstance(e, finnhub.FinnhubAPIException) and '429' in str(e)


    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=30, max=60),
        retry=retry_if_exception(_is_rate_limit_exception),
        before_sleep=lambda rs: print(f"⚠️\u3000Finnhub API rate limit hit. Retrying in {rs.next_action.sleep:.0f}s... (Attempt #{rs.attempt_number})")
    )
    def _ticker_lookup(query):
        """
        Performs the actual symbol lookup using the Finnhub client.
        This function is decorated for retries.
        """
        time.sleep(1) # Pause to respect API rate limits
        return Finnhub.CLIENT.symbol_lookup(query)


    def _lookup(self, query):
        """
        Looks up a query on Finnhub and returns the best match.
        It calls the API with retry logic and then processes the response.
        """
        if not self.CLIENT:
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


    def get_ticker(self, cusip: str, **kwargs) -> str | None:
        """
        Attempts to get the ticker from Finnhub.io, using a series of fallback queries.
        Uses a retry mechanism for API rate limits.
        Queries in order:
        1. CUSIP
        2. Company Name (from kwargs)
        3. First significant word of Company Name
        """
        company_name = kwargs.get('company_name')
        # 1. Try with CUSIP
        best_match = self._lookup(cusip)

        # 2. Fallback to full issuer name (truncated)
        if not best_match and company_name:
            best_match = self._lookup(company_name[:self.MAX_QUERY_LENGTH])

        # 3. Fallback to the first word of the issuer name
        if not best_match and company_name:
            first_word = company_name.split(' ')[0]
            # Block common words
            if len(first_word) > 2 and first_word.lower() not in self.COMMON_COMPANY_WORDS:
                best_match = self._lookup(first_word)

        if not best_match:
            print(f"⚠️\u3000Finnhub: No ticker found for CUSIP {cusip} / Company '{company_name}'.")
            return None
        
        return best_match.get('symbol')


    def get_company(self, cusip: str, **kwargs) -> str | None:
        """
        Returns the original company name if provided, otherwise looks up the company name from Finnhub.io using CUSIP.
        """
        best_match = self._lookup(cusip)
        if best_match:
            return best_match.get('description', '').title()
        
        print(f"⚠️\u3000Finnhub: No company found for CUSIP {cusip}")
        return None
