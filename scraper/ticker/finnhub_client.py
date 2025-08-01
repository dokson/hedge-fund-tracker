import finnhub
import pandas as pd
import time
import os

# Finnhub allows 60 calls/minute
_FINNHUB_TIMEOUT = 1


def load_api_key_from_env(file_path='.env'):
    """
    Loads the Finnhub API key from a .env text file.
    """
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if key.strip() == 'FINNHUB_API_KEY':
                        return value.strip().strip('"\'')
    except Exception as e:
        print(f"Error reading credential file '{file_path}': {e}")
    return None

# Initialize API Key and Client at module level
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or load_api_key_from_env()

if not FINNHUB_API_KEY:
    raise EnvironmentError(
        "Could not find FINNHUB_API_KEY. "
        "Please set it as an environment variable (e.g., in CI secrets) "
        "or in a '.env' file with the line: FINNHUB_API_KEY=\"your_key_here\""
    )

FINNHUB_CLIENT = finnhub.Client(api_key=FINNHUB_API_KEY)

_COMMON_COMPANY_WORDS = {'the', 'corp', 'inc', 'group', 'ltd', 'co', 'plc', 'hldgs'}
_MAX_QUERY_LENGTH = 20


def _lookup_with_retry(query, max_retries=3, backoff_factor=30):
    """
    Performs a symbol lookup with the Finnhub API, with retries for 429 errors.
    """
    for attempt in range(max_retries):
        try:
            response = FINNHUB_CLIENT.symbol_lookup(query)
            return response
        except finnhub.FinnhubAPIException as e:
            if '429' in str(e):
                if attempt < max_retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    print(f"Finnhub API rate limit hit. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Finnhub API rate limit hit. Max retries reached for query '{query}'.")
                    return None
            else:
                print(f"Finnhub API error for query '{query}': {e}")
                return None
        except Exception as e:
            print(f"An unexpected error occurred during Finnhub request for query '{query}': {e}")
            return None
    return None


def _find_ticker_and_company(response_data):
    """
    Helper function to extract the ticker from Finnhub's symbol_lookup response.
    Prioritizes Common Stock/Equity.
    """
    if response_data and 'result' in response_data and len(response_data['result']) > 0:
        # Prioritize Common Stock/Equity for better accuracy
        for item in response_data['result']:
            if 'symbol' in item and 'type' in item and item['type'] in ['Common Stock', 'Equity', 'STOCK']:
                return item['symbol'], item['description']
        # Fallback to the first result if no common stock is found
        if 'symbol' in response_data['result'][0]:
            return response_data['result'][0]['symbol'], response_data['result'][0]['description']
    return None, ''


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
    response = _lookup_with_retry(cusip)

    ticker, finnhub_company = _find_ticker_and_company(response)

    if company_name == '':
        company_name = finnhub_company

    # 2. Fallback to full issuer name (truncated)
    if pd.isna(ticker) and company_name:
        response = _lookup_with_retry(company_name[:_MAX_QUERY_LENGTH])
        ticker, _ = _find_ticker_and_company(response)
    
    # 3. Fallback to the first word of the issuer name
    if pd.isna(ticker) and company_name:
        first_word = company_name.split(' ')[0]
        # Block common words
        if len(first_word) > 2 and first_word.lower() not in _COMMON_COMPANY_WORDS:
            response = _lookup_with_retry(first_word)
            ticker, _ = _find_ticker_and_company(response)

    if pd.isna(ticker):
        print(f"Finnhub: No ticker found for CUSIP {cusip} / Company '{company_name}'.")
    return ticker, company_name
