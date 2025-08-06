from app.scraper.xml_processor import xml_to_dataframe_schedule
from app.tickers.resolver import resolve_ticker
from app.utils.pd import coalesce
from app.utils.strings import format_percentage, format_value
import pandas as pd


def get_latest_schedule_filings_dataframe(schedule_filings, fund_name, cik):
    schedule_list = []
    
    for filing in schedule_filings:
        schedule_df = xml_to_dataframe_schedule(filing['xml_content'])
        filtered_df = schedule_df[schedule_df['Owner'] == fund_name.upper()]
        if filtered_df.empty:
            schedule_df = schedule_df[schedule_df['Owner'] == cik.upper()]
        else:
            schedule_df = filtered_df

        schedule_df['Date'] = pd.to_datetime(filing['date'])
        schedule_list.append(schedule_df)

    schedule_filings_df = pd.concat(schedule_list, ignore_index=True)
    schedule_filings_df = schedule_filings_df.sort_values(by=['CUSIP', 'Date'], ascending=[True, False])
    # Keep only the most recent entry for each CUSIP
    schedule_filings_df = schedule_filings_df.drop_duplicates(subset='CUSIP', keep='first')

    return schedule_filings_df


def generate_comparison(df_recent, df_previous):
    """
    Generates a comparison report between the two DataFrames, calculating percentage change and indicating new positions.
    """
    df_comparison = pd.merge(
        df_recent,
        df_previous,
        on=['CUSIP'],
        how='outer',
        suffixes=('_recent', '_previous')
    )

    df_comparison['Shares_recent'] = df_comparison['Shares_recent'].fillna(0).astype('int64')
    df_comparison['Shares_previous'] = df_comparison['Shares_previous'].fillna(0).astype('int64')
    df_comparison['Value'] = df_comparison['Value_recent'].fillna(0).astype('int64')
    df_comparison['Value_previous'] = df_comparison['Value_previous'].fillna(0).astype('int64')

    df_comparison['Company'] = coalesce(df_comparison['Company_recent'], df_comparison['Company_previous'])
    df_comparison['Price_per_Share'] = (coalesce(df_comparison['Value'] / df_comparison['Shares_recent'], df_comparison['Value_previous'] / df_comparison['Shares_previous'])).round(2)
    df_comparison['Delta_Shares'] = df_comparison['Shares_recent'] - df_comparison['Shares_previous']
    df_comparison['Delta_Value'] = (df_comparison['Delta_Shares'] * df_comparison['Price_per_Share']).fillna(0).astype(int)
    df_comparison['Delta%'] = (df_comparison['Delta_Shares'] / df_comparison['Shares_previous']) * 100

    df_comparison['Delta'] = df_comparison.apply(
        lambda row: 
        'NEW' if row['Shares_previous'] == 0
        else 'CLOSE' if row['Shares_recent'] == 0
        else 'NO CHANGE' if row['Shares_recent'] == row['Shares_previous']
        else format_percentage(row['Delta%'], True),
        axis=1
    )

    total_portfolio_value = df_comparison['Value'].sum()
    previous_portfolio_value = df_comparison['Value_previous'].sum()
    total_delta_value = total_portfolio_value - previous_portfolio_value
    total_delta = (total_delta_value / previous_portfolio_value) * 100
    
    df_comparison['Portfolio%'] = ((df_comparison['Value'] / total_portfolio_value) * 100).apply(format_percentage)
    df_comparison = resolve_ticker(df_comparison)

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Company', 'Value', 'Portfolio%', 'Delta_Value', 'Delta']] \
                        .sort_values(by=['Delta_Value', 'Value'], ascending=False)

    df_comparison['Value'] = df_comparison['Value'].apply(format_value)
    df_comparison['Delta_Value'] = df_comparison['Delta_Value'].apply(format_value)

    # Add grand total row
    total_row = pd.DataFrame([{
        'CUSIP': 'Total', 
        'Ticker': '', 
        'Company': '',
        'Value': format_value(total_portfolio_value),
        'Portfolio%': format_percentage(100),
        'Delta_Value': format_value(total_delta_value),
        'Delta': format_percentage(total_delta, True)
    }])

    return pd.concat([df_comparison, total_row], ignore_index=True)
