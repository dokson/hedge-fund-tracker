from app.scraper.xml_processor import xml_to_dataframe_4, xml_to_dataframe_schedule
from app.tickers.libraries import YFinance
from app.tickers.resolver import resolve_ticker
from app.utils.database import load_non_quarterly_data
from app.utils.github import open_issue
from app.utils.pd import coalesce
from app.utils.strings import format_percentage, format_value, get_numeric
import pandas as pd


def get_non_quarterly_filings_dataframe(non_quarterly_filings: list[dict], fund_denomination: str, cik: str) -> pd.DataFrame | None:
    """
    Processes all raw schedule filings (13D/G + 4) and returns a DataFrame with the most recent holding for each CUSIP.

    - Iterates through a list of filings, converting XML content to a DataFrame.
    - Filters the data to find holdings associated with the fund, trying by denomination first, then by CIK.
    - Combines all valid filings and de-duplicates them to keep only the latest entry per CUSIP.
    """
    filing_list = []
    
    for filing in non_quarterly_filings:
        if filing['type'] == 'SCHEDULE':
            filing_df = xml_to_dataframe_schedule(filing['xml_content'])
        else:
            filing_df = xml_to_dataframe_4(filing['xml_content'])
        
        filing_df = filing_df[filing_df['CIK'] != cik]
        if filing_df.empty:
            print(f"{filing['type']} filing ({filing['date']}) is referring to {fund_denomination} ({cik}) shares itself: skipping because it is not relevant.")
            continue

        filtered_df = filing_df[filing_df['Owner'].str.upper() == fund_denomination.upper()].copy()
        if filtered_df.empty:
            filtered_df = filing_df[filing_df['Owner_CIK'] == cik].copy()

        if not filtered_df.empty:
            filtered_df['Filing_Date'] = pd.to_datetime(filing['date'])
            filtered_df['Accepted_On'] = pd.to_datetime(filing['accepted_on'])
            filing_list.append(filtered_df)
        else:
            # If no match is found, open an issue on GitHub to investigate `hedge_funds.csv` file
            subject = f"Hedge Fund Tracker Alert: CIK/Denomination not found in filing on {filing['date']}."
            body = (
                f"CIK:'{cik}' / Denomination '{fund_denomination}'\n"
                f"Filing Type: {filing['type']}\n"
                f"Filing Date: {filing['date']}\n\n"
                f"Filing Content:\n{filing_df.to_string()}"
            )
            open_issue(subject, body)

    if not filing_list:
        return None

    non_quarterly_filings_df = pd.concat(filing_list, ignore_index=True)
    non_quarterly_filings_df = resolve_ticker(non_quarterly_filings_df)

    # Keep only the most recent accepted entry for each Ticker-Date combination because there can be amendments on the same Filing Date
    non_quarterly_filings_df = non_quarterly_filings_df.sort_values(by=['Ticker', 'Date', 'Accepted_On'], ascending=False).drop_duplicates(subset=['Ticker', 'Date'], keep='first')

    # Initialize columns before the loop to prevent KeyError
    non_quarterly_filings_df['Value'] = pd.NA
    non_quarterly_filings_df['Avg_Price'] = pd.NA

    for index, row in non_quarterly_filings_df.iterrows():
        ticker = row['Ticker']
        date = row['Date'].date()
        price = YFinance.get_avg_price(ticker, date)
        if price:
            non_quarterly_filings_df.at[index, 'Avg_Price'] = price
            non_quarterly_filings_df.at[index, 'Value'] = price * row['Shares']
        else:
            print(f"⚠️\u3000Could not find price for {ticker} on {date}.")

    # Numerics to String format
    non_quarterly_filings_df['Value'] = non_quarterly_filings_df['Value'].apply(format_value)
    non_quarterly_filings_df['Avg_Price'] = non_quarterly_filings_df['Avg_Price'].apply(format_value)

    return non_quarterly_filings_df[['CUSIP', 'Ticker', 'Company', 'Shares', 'Value', 'Avg_Price', 'Date', 'Filing_Date']]


def update_last_quarter_with_nq_filings(last_quarter_df: pd.DataFrame) -> pd.DataFrame:
    """
    Updates the 13F holdings dataframe with more recent data from non quarterly filings.

    - For existing CUSIPs, it updates 'Shares' and recalculates 'Value' based on the original price.
    - For new CUSIPs, it adds the row with 'Value' as N/A.
    """
    schedule_df = load_non_quarterly_data().set_index(['Fund', 'CUSIP'])
    schedule_df.loc[:, 'Value_Num'] = schedule_df['Value'].apply(get_numeric)

    updated_df = pd.merge(
        last_quarter_df,
        schedule_df,
        on=['Fund', 'CUSIP'],
        how='outer',
        suffixes=('_13f', '_schedule'),
        indicator=True
    )
    updated_df['Ticker'] = coalesce(updated_df['Ticker_13f'], updated_df['Ticker_schedule'])
    updated_df['Company'] = coalesce(updated_df['Company_13f'], updated_df['Company_schedule'].str.upper())
    updated_df['Shares'] = coalesce(updated_df['Shares_schedule'], updated_df['Shares_13f']).astype('int64')
    updated_df['Delta_Shares'] = coalesce(updated_df['Shares_schedule'] - coalesce(updated_df['Shares_13f'], 0), updated_df['Delta_Shares'])
    updated_df['Delta_Value_Num'] = coalesce(updated_df['Value_Num_schedule'] - coalesce(updated_df['Value_Num_13f'], 0), updated_df['Delta_Value_Num'])
    
    updated_df['Delta'] = updated_df.apply(
        lambda row:
        'NEW' if pd.isna(row['Shares_13f']) or row['Shares_13f'] == 0
        else 'CLOSE' if row['Shares_schedule'] == 0
        else (row['Shares_schedule'] - row['Shares_13f']) / row['Shares_13f'] * 100 if not pd.isna(row['Shares_schedule'])
        else format_percentage(row['Delta']),
        axis=1
    )

    updated_df['Value_Num'] = coalesce(updated_df['Value_Num_schedule'], updated_df['Value_Num_13f'])
    total_value_per_fund = updated_df.groupby('Fund')['Value_Num'].transform('sum')
    updated_df['Portfolio_Pct'] = (updated_df['Value_Num'] / total_value_per_fund) * 100

    return updated_df[['Fund', 'CUSIP', 'Ticker', 'Company', 'Shares', 'Delta_Shares', 'Value_Num', 'Delta_Value_Num', 'Delta', 'Portfolio_Pct']]


def get_nq_filings_info(quarter_data: pd.DataFrame) -> pd.DataFrame:
    """
    Load latest non quarterly filings (load_non_quarterly_data) and enrich with quarterly data.
    """
    non_quarterly_filings_df = load_non_quarterly_data().set_index(['Fund', 'Ticker'])
    quarter_data = quarter_data.set_index(['Fund', 'Ticker'])

    return non_quarterly_filings_df.join(quarter_data, how='inner', rsuffix='_quarter').reset_index()
