from app.tickers.resolver import resolve_ticker
from app.utils.pd import coalesce
from app.utils.strings import format_percentage, format_value
import pandas as pd


def generate_comparison(df_recent, df_previous):
    """
    Generates a comparison report between the two DataFrames, calculating percentage change and indicating new positions.
    """
    if df_previous is None:
        df_previous = pd.DataFrame(columns=df_recent.columns)

    df_comparison = pd.merge(
        df_recent,
        df_previous,
        on=['CUSIP'],
        how='outer',
        suffixes=('_recent', '_previous')
    )

    df_comparison['Shares'] = pd.to_numeric(df_comparison['Shares_recent'], errors='coerce').fillna(0).astype('int64')
    df_comparison['Shares_previous'] = pd.to_numeric(df_comparison['Shares_previous'], errors='coerce').fillna(0).astype('int64')
    df_comparison['Value'] = pd.to_numeric(df_comparison['Value_recent'], errors='coerce').fillna(0).astype('int64')
    df_comparison['Value_previous'] = pd.to_numeric(df_comparison['Value_previous'], errors='coerce').fillna(0).astype('int64')

    df_comparison['Company'] = coalesce(df_comparison['Company_recent'], df_comparison['Company_previous'])
    df_comparison['Price_per_Share'] = coalesce(df_comparison['Value'] / df_comparison['Shares'], df_comparison['Value_previous'] / df_comparison['Shares_previous'])
    df_comparison['Delta_Shares'] = df_comparison['Shares'] - df_comparison['Shares_previous']
    df_comparison['Delta_Value'] = df_comparison['Delta_Shares'] * df_comparison['Price_per_Share']
    df_comparison['Delta%'] = (df_comparison['Delta_Shares'] / df_comparison['Shares_previous']) * 100

    df_comparison['Delta'] = df_comparison.apply(
        lambda row: 
        'NEW' if row['Shares_previous'] == 0
        else 'CLOSE' if row['Shares'] == 0
        else 'NO CHANGE' if row['Shares'] == row['Shares_previous']
        else format_percentage(row['Delta%'], True),
        axis=1
    )

    total_portfolio_value = df_comparison['Value'].sum()
    previous_portfolio_value = df_comparison['Value_previous'].sum()
    total_delta_value = total_portfolio_value - previous_portfolio_value
    total_delta = (total_delta_value / previous_portfolio_value) * 100 if previous_portfolio_value != 0 else float('inf') 
    
    df_comparison = resolve_ticker(df_comparison)

    # Order results by Delta_Value descending
    df_comparison = df_comparison.sort_values(by=['Delta_Value', 'Value'], ascending=[False, False])

    # Format fields
    df_comparison['Portfolio%'] = ((df_comparison['Value'] / total_portfolio_value) * 100).apply(
        lambda x: format_percentage(x, decimal_places=2) if 0.01 <= x < 1 else format_percentage(x)
    )
    df_comparison['Value'] = df_comparison['Value'].apply(format_value)
    df_comparison['Delta_Value'] = df_comparison['Delta_Value'].apply(format_value)

    df_comparison = df_comparison[['CUSIP', 'Ticker', 'Company', 'Shares', 'Value', 'Delta_Value', 'Delta', 'Portfolio%']]

    # Final Total row
    total_row = pd.DataFrame([{
        'CUSIP': 'Total', 
        'Ticker': '', 
        'Company': '',
        'Shares': '',
        'Value': format_value(total_portfolio_value),
        'Delta_Value': format_value(total_delta_value),
        'Delta': format_percentage(total_delta, True),
        'Portfolio%': format_percentage(100),
    }])

    return pd.concat([df_comparison, total_row], ignore_index=True)
