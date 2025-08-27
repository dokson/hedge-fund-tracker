from app.scraper.xml_processor import xml_to_dataframe_schedule
from app.tickers.resolver import resolve_ticker
from app.utils.pd import coalesce
import numpy as np
import pandas as pd


def get_latest_schedule_filings_dataframe(schedule_filings, fund_denomination, cik):
    """
    Processes raw schedule filings (13D/G) and returns a DataFrame with the most recent holding for each CUSIP.

    - Iterates through a list of filings, converting XML content to a DataFrame.
    - Filters the data to find holdings associated with the fund, trying by denomination first, then by CIK.
    - Combines all valid filings and de-duplicates them to keep only the latest entry per CUSIP.
    """
    schedule_list = []
    
    for filing in schedule_filings:
        schedule_df = xml_to_dataframe_schedule(filing['xml_content'])
        filtered_df = schedule_df[schedule_df['Owner'].str.upper() == fund_denomination.upper()].copy()
        if filtered_df.empty:
            filtered_df = schedule_df[schedule_df['Owner'] == cik].copy()

        if not filtered_df.empty:
            filtered_df['Date'] = pd.to_datetime(filing['date'])
            schedule_list.append(filtered_df)
        else:
            print(schedule_df)
            print("⚠️ Hedge fund denomination or CIK not found inside filing.")
            return None

    schedule_filings_df = pd.concat(schedule_list, ignore_index=True)
    # Keep only the most recent entry for each CUSIP
    schedule_filings_df = schedule_filings_df.sort_values(by=['CUSIP', 'Date'], ascending=[True, False]).drop_duplicates(subset='CUSIP', keep='first')
    schedule_filings_df = resolve_ticker(schedule_filings_df)

    return schedule_filings_df[['CUSIP', 'Ticker', 'Company', 'Shares', 'Date']]


def update_dataframe_with_schedule(quarter_13f_df, schedule_df):
    """
    Updates the 13F holdings dataframe with more recent data from schedule filings.
    - For existing CUSIPs, it updates 'Shares' and recalculates 'Value' based on the original price.
    - For new CUSIPs, it adds the row with 'Value' as N/A.
    """

    quarter_13f_df['Price_per_Share'] = (quarter_13f_df['Value'] / quarter_13f_df['Shares']).round(2)

    updated_df = pd.merge(
        quarter_13f_df,
        schedule_df[['CUSIP', 'Shares', 'Company']],
        on='CUSIP',
        how='outer',
        suffixes=('_13f', '_schedule'),
        indicator=True
    )

    updated_df['Shares'] = coalesce(updated_df['Shares_schedule'], updated_df['Shares_13f']).astype('int64')
    updated_df['Company'] = coalesce(updated_df['Company_13f'], updated_df['Company_schedule'])

    conditions = [
        updated_df['_merge'] == 'both',          # Updated position
        updated_df['_merge'] == 'left_only',     # Unchanged 13F position
        updated_df['_merge'] == 'right_only'     # New position from schedule
    ]
    choices = [
        updated_df['Shares_schedule'] * updated_df['Price_per_Share'],  # Compute value for updates
        updated_df['Value'],                                            # Unchanged 13F position
        pd.NA                                                           # NA for new positions
    ]
    updated_df['Value'] = np.select(conditions, choices)

    return updated_df[['CUSIP', 'Company', 'Shares', 'Value']]
