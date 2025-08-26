from app.utils.database import get_all_quarter_files, load_stocks
from app.utils.strings import format_percentage, get_numeric, get_percentage_number
from pathlib import Path
import pandas as pd
import numpy as np

def _load_quarter_data(quarter):
    """
    Loads all fund comparison data for a given quarter (e.g., '2025Q1').

    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A concatenated DataFrame of all fund data for the quarter
    """
    all_fund_data = []

    for file_path in get_all_quarter_files(quarter):
        df = pd.read_csv(file_path)

        total_row = df[df['CUSIP'] == 'Total']
        total_portfolio_value = get_numeric(total_row['Value'].iloc[0])

        df_stocks = df[df['CUSIP'] != 'Total'].copy()

        df_stocks.loc[:, 'Delta_Value_Num'] = df_stocks['Delta_Value'].apply(get_numeric)
        df_stocks.loc[:, 'Value_Num'] = df_stocks['Value'].apply(get_numeric)
        df_stocks.loc[:, 'Weighted_Delta_Pct'] = (df_stocks['Delta_Value_Num'] / total_portfolio_value) * 100
        df_stocks.loc[:, 'Portfolio_Pct'] = df_stocks['Portfolio%'].apply(get_percentage_number)
        df_stocks.loc[:, 'Fund'] = Path(file_path).stem.replace('_', ' ')

        all_fund_data.append(df_stocks)

    return pd.concat(all_fund_data, ignore_index=True)


def quarter_analysis(quarter):
    """
    Analyzes stock data for a given quarter to find the most popular, bought, and sold stocks.
    
    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame with aggregated stock analysis for the quarter
    """
    df_quarter = _load_quarter_data(quarter)
    df_stocks = load_stocks()

    # Drop company/ticker from quarterly data to use master data instead. 
    # This ensures consistency and correctly aggregates data for companies that may have multiple CUSIPs
    df_quarter = df_quarter.drop(columns=['Ticker', 'Company']).set_index('CUSIP').join(df_stocks[['Ticker', 'Company']], how='left').reset_index()

    # Fund level calculation
    df_fund_quarter = (
        df_quarter.groupby(['Fund', 'Ticker', 'Company'])
        .agg(
            Value_Num=('Value_Num', 'sum'),
            Delta_Value_Num=('Delta_Value_Num', 'sum'),
            Portfolio_Pct=('Portfolio_Pct', 'sum'),
            Weighted_Delta_Pct=('Weighted_Delta_Pct', 'sum')
        )
        .reset_index()
    )

    df_fund_quarter['is_buyer'] = df_fund_quarter['Delta_Value_Num'] > 0
    df_fund_quarter['is_seller'] = df_fund_quarter['Delta_Value_Num'] < 0
    df_fund_quarter['is_holder'] = df_fund_quarter['Value_Num'] > 0
    df_fund_quarter['is_new'] = (df_fund_quarter['Value_Num'] == df_fund_quarter['Delta_Value_Num']) & (df_fund_quarter['Value_Num'] > 0)
    df_fund_quarter['is_closed'] = df_fund_quarter['Value_Num'] == 0
    
    # Stock level calculation
    df_analysis = (
        df_fund_quarter.groupby(['Ticker', 'Company'])
        .agg(
            Total_Value=('Value_Num', 'sum'),
            Total_Delta_Value=('Delta_Value_Num', 'sum'),
            Total_Weighted_Delta_Pct=('Weighted_Delta_Pct', 'sum'),
            Max_Portfolio_Pct=('Portfolio_Pct', 'max'),
            Avg_Portfolio_Pct=('Portfolio_Pct', 'mean'),
            Buyer_Count=('is_buyer', 'sum'),
            Seller_Count=('is_seller', 'sum'),
            Holder_Count=('is_holder', 'sum'),
            New_Holder_Count=('is_new', 'sum'),
            Close_Count=('is_closed', 'sum'),
        )
        .reset_index()
    )

    df_analysis['Net_Buyers'] = df_analysis['Buyer_Count'] - df_analysis['Seller_Count']
    df_analysis['Delta'] = np.where((df_analysis['New_Holder_Count'] == df_analysis['Holder_Count']) & (df_analysis['Close_Count'] == 0), np.inf, df_analysis['Total_Delta_Value'] / df_analysis['Total_Value'] * 100)
    df_analysis['Buyer_Seller_Ratio'] = np.where(df_analysis['Seller_Count'] > 0, df_analysis['Buyer_Count'] / df_analysis['Seller_Count'],  np.inf)

    return df_analysis


def stock_analysis(ticker, quarter):
    """
    Analyzes a single stock for a given quarter, returning a list of funds that hold it.
    
    Args:
        ticker (str): The stock ticker to analyze.
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame with fund-level details for the specified stock.
    """
    df_quarter = _load_quarter_data(quarter)
    df_quarter = df_quarter[df_quarter['Ticker'] == ticker]

    # Aggregates data for Ticker that may have multiple CUSIPs in the same hedge fund report
    df_analysis = (
        df_quarter.groupby(['Fund', 'Ticker'])
        .agg(
            Company=('Company', 'first'),
            Value=('Value_Num', 'sum'),
            Delta_Value=('Delta_Value_Num', 'sum'),
            Portfolio_Pct=('Portfolio_Pct', 'sum'),
        )
        .reset_index()
    )

    # If the sum of Portfolio_Pct is 0 but the value is positive, it means the position is composed of <0.01% holdings
    # We assign a small non-zero value to represent this.
    df_analysis.loc[(df_analysis['Portfolio_Pct'] == 0) & (df_analysis['Value'] > 0), 'Portfolio_Pct'] = 0.009

    # Recalculate 'Delta' based on aggregated values
    df_analysis['Delta'] = df_analysis.apply(
        lambda row:
        'CLOSE' if row['Value'] == 0
        else 'NO CHANGE' if row['Delta_Value'] == 0
        else 'NEW' if row['Value'] > 0 and row['Value'] == row['Delta_Value']
        else format_percentage(row['Delta_Value'] / (row['Value'] - row['Delta_Value']) * 100, True),
        axis=1
    )

    return df_analysis
