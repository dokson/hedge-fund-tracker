from app.scraper.xml_processor import xml_to_dataframe_4, xml_to_dataframe_schedule
from app.tickers.resolver import resolve_ticker
from app.utils.database import load_schedules_data
from app.utils.github import open_issue
from app.utils.pd import coalesce
from app.utils.strings import format_percentage, format_value, get_numeric
import datetime
import pandas as pd
import yfinance as yf


def get_latest_schedule_filings_dataframe(schedule_filings, fund_denomination, cik):
    """
    Processes all raw schedule filings (13D/G + 4) and returns a DataFrame with the most recent holding for each CUSIP.

    - Iterates through a list of filings, converting XML content to a DataFrame.
    - Filters the data to find holdings associated with the fund, trying by denomination first, then by CIK.
    - Combines all valid filings and de-duplicates them to keep only the latest entry per CUSIP.
    """
    schedule_list = []
    
    for filing in schedule_filings:
        if filing['type'] == 'SCHEDULE':
            schedule_df = xml_to_dataframe_schedule(filing['xml_content'])
        else:
            schedule_df = xml_to_dataframe_4(filing['xml_content'])
        
        schedule_df = schedule_df[schedule_df['CIK'] != cik]
        if schedule_df.empty:
            print(f"{filing['type']} filing ({filing['date']}) is referring to {fund_denomination} ({cik}) shares itself: skipping because it is not relevant.")
            continue

        filtered_df = schedule_df[schedule_df['Owner'].str.upper() == fund_denomination.upper()].copy()
        if filtered_df.empty:
            filtered_df = schedule_df[schedule_df['Owner'] == cik].copy()

        if not filtered_df.empty:
            filtered_df['Filing_Date'] = pd.to_datetime(filing['date'])
            schedule_list.append(filtered_df)
        else:
            # If no match is found, open an issue on GitHub to investigate `hedge_funds.csv` file
            subject = f"Hedge Fund Tracker Alert: CIK/Denomination not found in filing on {filing['date']}."
            body = (
                f"CIK:'{cik}' / Denomination '{fund_denomination}'\n"
                f"Filing Type: {filing['type']}\n"
                f"Filing Date: {filing['date']}\n\n"
                f"Filing Content:\n{schedule_df}"
            )
            open_issue(subject, body)

    if not schedule_list:
        return None

    schedule_filings_df = pd.concat(schedule_list, ignore_index=True)
    schedule_filings_df = resolve_ticker(schedule_filings_df)

    # Keep only the most recent entry for each Ticker
    schedule_filings_df = schedule_filings_df.sort_values(by=['Ticker', 'Filing_Date', 'Date'], ascending=False).drop_duplicates(subset='Ticker', keep='first')

    # Initialize columns before the loop to prevent KeyError
    schedule_filings_df['Value'] = pd.NA
    schedule_filings_df['Avg_Price'] = pd.NA

    for index, row in schedule_filings_df.iterrows():
        ticker = row['Ticker']
        date = row['Date'].date()
        # yfinance 'end' parameter is exclusive. To get a single day, we need the next day as the end.
        price_data = yf.download(tickers=ticker, start=date, end=date+datetime.timedelta(days=1), auto_adjust=False, progress=False)
        if not price_data.empty:
            # Considering daily price as the average of daily high and daily low
            average_price = (price_data['High'].iloc[0].item() + price_data['Low'].iloc[0].item()) / 2
            schedule_filings_df.at[index, 'Avg_Price'] = round(average_price, 2)
            schedule_filings_df.at[index, 'Value'] = average_price * row['Shares']
        else:
            print(f"⚠️\u3000Could not find price for {ticker} on {date}.")

    # Numerics to String format
    schedule_filings_df['Value'] = schedule_filings_df['Value'].apply(format_value)
    schedule_filings_df['Avg_Price'] = schedule_filings_df['Avg_Price'].apply(format_value)

    return schedule_filings_df[['CUSIP', 'Ticker', 'Company', 'Shares', 'Value', 'Avg_Price', 'Date']]


def update_last_quarter_with_schedules(last_quarter_df):
    """
    Updates the 13F holdings dataframe with more recent data from schedule filings.

    - For existing CUSIPs, it updates 'Shares' and recalculates 'Value' based on the original price.
    - For new CUSIPs, it adds the row with 'Value' as N/A.
    """
    schedule_df = load_schedules_data()
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
        'NEW' if pd.isna(row['Shares_13f'])
        else 'CLOSE' if row['Shares_schedule'] == 0
        else (row['Shares_schedule'] - row['Shares_13f']) / row['Shares_13f'] * 100 if not pd.isna(row['Shares_schedule'])
        else format_percentage(row['Delta']),
        axis=1
    )

    updated_df['Value_Num'] = coalesce(updated_df['Value_Num_schedule'], updated_df['Value_Num_13f'])
    total_value_per_fund = updated_df.groupby('Fund')['Value_Num'].transform('sum')
    updated_df['Portfolio_Pct'] = (updated_df['Value_Num'] / total_value_per_fund) * 100

    return updated_df[['Fund', 'CUSIP', 'Ticker', 'Company', 'Shares', 'Delta_Shares', 'Value_Num', 'Delta_Value_Num', 'Delta', 'Portfolio_Pct']]


def get_latest_filings_info(quarter_data):
    # Filter quarter_data for rows present in schedules_df (latest filings) and enrich with quarterly data.
    schedules_df = load_schedules_data().reset_index().set_index(['Fund', 'Ticker'])
    filings_df = schedules_df.join(quarter_data.set_index(['Fund', 'Ticker']), how='inner', rsuffix='_quarter').reset_index()

    return filings_df
