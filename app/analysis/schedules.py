from app.scraper.xml_processor import xml_to_dataframe_schedule
from app.tickers.resolver import resolve_ticker
from app.utils.database import load_schedules_data
from app.utils.pd import coalesce
from app.utils.strings import format_value
import datetime
import numpy as np
import pandas as pd
import yfinance as yf


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
        schedule_df = schedule_df[schedule_df['CIK'] != cik]
        if schedule_df.empty:
            print(f"Filing is referring to {fund_denomination} ({cik}) shares itself: skipping because it is not relevant.")
            return None

        filtered_df = schedule_df[schedule_df['Owner'].str.upper() == fund_denomination.upper()].copy()
        if filtered_df.empty:
            filtered_df = schedule_df[schedule_df['Owner'] == cik].copy()

        if not filtered_df.empty:
            filtered_df['Filing_Date'] = pd.to_datetime(filing['date'])
            schedule_list.append(filtered_df)
        else:
            print(schedule_df)
            print("⚠️\u3000Hedge fund denomination or CIK not found inside filing.")
            return None

    schedule_filings_df = pd.concat(schedule_list, ignore_index=True)
    # Keep only the most recent entry for each CUSIP
    schedule_filings_df = schedule_filings_df.sort_values(by=['CUSIP', 'Filing_Date', 'Date'], ascending=False).drop_duplicates(subset='CUSIP', keep='first')
    schedule_filings_df = resolve_ticker(schedule_filings_df)

    # Initialize 'Value' column before the loop to prevent KeyError
    schedule_filings_df['Value'] = pd.NA
    for index, row in schedule_filings_df.iterrows():
        ticker = row['Ticker']
        date = row['Date'].date()
        # yfinance 'end' parameter is exclusive. To get a single day, we need the next day as the end.
        price_data = yf.download(tickers=ticker, start=date, end=date+datetime.timedelta(days=1), auto_adjust=False, progress=False)
        if not price_data.empty:
            # Considering daily price as the average of daily high and daily low
            price_per_share = (price_data['High'].iloc[0].item() + price_data['Low'].iloc[0].item()) / 2
            schedule_filings_df.at[index, 'Value'] = price_per_share * row['Shares']
        else:
            print(f"⚠️\u3000Could not find price for {ticker} on {date}.")

    schedule_filings_df['Value'] = format_value(schedule_filings_df['Value'])

    return schedule_filings_df[['CUSIP', 'Ticker', 'Company', 'Shares', 'Value', 'Date']]


def update_last_quarter_with_schedules(last_quarter_df):
    """
    Updates the 13F holdings dataframe with more recent data from schedule filings.

    - For existing CUSIPs, it updates 'Shares' and recalculates 'Value' based on the original price.
    - For new CUSIPs, it adds the row with 'Value' as N/A.
    """
    schedule_df = load_schedules_data()

    last_quarter_df['Price_per_Share'] = np.where(last_quarter_df['Shares'] > 0, last_quarter_df['Value_Num'] / last_quarter_df['Shares'], 0)

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
    updated_df['Delta_Value_Num'] = coalesce((updated_df['Shares_schedule'] - updated_df['Shares_13f']) * updated_df['Price_per_Share'], updated_df['Delta_Value_Num'])
    
    updated_df['Delta'] = updated_df.apply(
        lambda row:
        'NEW (13D/G)' if pd.isna(row['Shares_13f'])
        else 'CLOSE' if row['Shares_schedule'] == 0
        else (row['Shares_schedule'] - row['Shares_13f']) / row['Shares_13f'] * 100 if not pd.isna(row['Shares_schedule'])
        else row['Delta'],
        axis=1
    )

    updated_df['Value_Num'] = updated_df['Shares'] * updated_df['Price_per_Share']
    total_value_per_fund = updated_df.groupby('Fund')['Value_Num'].transform('sum')
    updated_df['Portfolio_Pct'] = (updated_df['Value_Num'] / total_value_per_fund) * 100

    return updated_df[['Fund', 'CUSIP', 'Ticker', 'Company', 'Shares', 'Value_Num', 'Delta_Value_Num', 'Delta', 'Portfolio_Pct']]
