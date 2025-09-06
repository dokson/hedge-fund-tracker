import financedatabase as fd


def get_ticker(cusip):
    """
    Searches for a ticker for a given CUSIP using financedatabase.
    If multiple tickers are found, it returns the shortest one.
    """
    result = fd.Equities().search(cusip=cusip)

    if not result.empty:
        result['ticker_length'] = [len(idx) for idx in result.index]
        result = result.sort_values(by='ticker_length')
        return result.index[0]
    else:
        print(f"⚠️\u3000Finance Database: No ticker found for CUSIP {cusip}")
        return None


def get_company(cusip):
    """
    Searches for a company for a given CUSIP using financedatabase.
    If multiple rows are found, it returns the one with the shortest ticker.
    """
    result = fd.Equities().search(cusip=cusip)

    if not result.empty:
        result['ticker_length'] = [len(idx) for idx in result.index]
        result = result.sort_values(by='ticker_length')
        return result.iloc[0]['name']
    else:
        print(f"⚠️\u3000Finance Database: No company found for CUSIP {cusip}")
        return ''
