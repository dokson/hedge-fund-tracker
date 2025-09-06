from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
import finnhub
import os
import pandas as pd

_FINNHUB_TIMEOUT = 1
_COMMON_COMPANY_WORDS = {'the', 'corp', 'inc', 'group', 'ltd', 'co', 'plc', 'hldgs'}
_MAX_QUERY_LENGTH = 20

# Load variables from .env file
load_dotenv()
# Initialize API Key and Client at module level
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if not FINNHUB_API_KEY:
    raise EnvironmentError(
        "❌ FINNHUB_API_KEY not found. "
        "Please set it as an environment variable (e.g. in CI secrets) or in a '.env' file"
    )

FINNHUB_CLIENT = finnhub.Client(api_key=FINNHUB_API_KEY)


def _is_rate_limit_exception(e):
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
    return FINNHUB_CLIENT.symbol_lookup(query)


def _find_ticker_and_company(query):
    """
    Looks up a query on Finnhub and extracts the best ticker and company description.
    It calls the API with retry logic and then processes the response.
    """
    response_data = _ticker_lookup(query)
    if response_data and response_data.get('result'):
        # Prioritize Common Stock/Equity for better accuracy
        for item in response_data['result']:
            if item.get('type') in ['Common Stock', 'Equity', 'STOCK']:
                return item.get('symbol'), item.get('description')
        # Fallback to the first result if no common stock is found
        if response_data['result']:
            first_item = response_data['result'][0]
            return first_item.get('symbol'), first_item.get('description')
    return None, ''


def get_finnhub_timeout():
    """
    Returns the configured timeout for Finnhub API requests.
    """
    return _FINNHUB_TIMEOUT


def get_ticker_and_company(cusip, company_name):
    """
    Attempts to get the ticker from Finnhub.io, using a series of fallback queries.
    Uses a retry mechanism for API rate limits.
    Queries in order:
    1. CUSIP
    2. Company Name
    3. First significant word of Company Name
    """
    # 1. Try with CUSIP
    ticker, finnhub_company = _find_ticker_and_company(cusip)

    if company_name == '':
        company_name = finnhub_company

    # 2. Fallback to full issuer name (truncated)
    if pd.isna(ticker) and company_name:
        ticker, _ = _find_ticker_and_company(company_name[:_MAX_QUERY_LENGTH])
    
    # 3. Fallback to the first word of the issuer name
    if pd.isna(ticker) and company_name:
        first_word = company_name.split(' ')[0]
        # Block common words
        if len(first_word) > 2 and first_word.lower() not in _COMMON_COMPANY_WORDS:
            ticker, _ = _find_ticker_and_company(first_word)

    if pd.isna(ticker):
        print(f"⚠️\u3000Finnhub: No ticker found for CUSIP {cusip} / Company '{company_name}'.")
    return ticker, company_name
