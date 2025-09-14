from app.analysis.non_quarterly import update_last_quarter_with_nq_filings
from app.utils.database import get_last_quarter, is_last_quarter, load_quarterly_data, load_stocks
from app.utils.strings import format_percentage, get_numeric, get_percentage_number
import numpy as np


def aggregate_quarter_by_fund(df_quarter):
    """
    Aggregates quarter fund holdings at the Ticker level.

    Args:
        df_quarter (pd.DataFrame): The DataFrame containing quarterly data.

    Returns:
        pd.DataFrame: An aggregated DataFrame.
    """
    df_stocks = load_stocks()

    # Drop company/ticker from quarterly data to use master data instead. 
    # This ensures consistency and correctly aggregates data for companies that may have multiple CUSIPs
    df_quarter = df_quarter.drop(columns=['Ticker', 'Company']).set_index('CUSIP').join(df_stocks[['Ticker', 'Company']], how='left').reset_index()

    df_fund_quarter = (
        df_quarter.groupby(['Fund', 'Ticker', 'Company'])
        .agg(
            Shares=('Shares', 'sum'),
            Delta_Shares=('Delta_Shares', 'sum'),
            Value=('Value_Num', 'sum'),
            Delta_Value=('Delta_Value_Num', 'sum'),
            Portfolio_Pct=('Portfolio_Pct', 'sum'),
        )
        .reset_index()
    )

    # If the sum of Portfolio_Pct is 0 but there are shares, it means the position is composed of <0.01% holdings
    # We assign a small non-zero value to represent this
    df_fund_quarter.loc[(df_fund_quarter['Portfolio_Pct'] == 0) & (df_fund_quarter['Shares'] > 0), 'Portfolio_Pct'] = 0.009

    # Calculate 'Delta' based on aggregated values
    df_fund_quarter['Delta'] = df_fund_quarter.apply(
        lambda row:
        'CLOSE' if row['Shares'] == 0
        else 'NO CHANGE' if row['Delta_Shares'] == 0
        else 'NEW' if row['Shares'] > 0 and row['Shares'] == row['Delta_Shares']
        else format_percentage(row['Delta_Shares'] / (row['Shares'] - row['Delta_Shares']) * 100, True),
        axis=1
    )

    return df_fund_quarter


def get_quarter_data(quarter=get_last_quarter()):
    df_quarter = load_quarterly_data(quarter)

    df_quarter.loc[:, 'Delta_Value_Num'] = df_quarter['Delta_Value'].apply(get_numeric)
    df_quarter.loc[:, 'Value_Num'] = df_quarter['Value'].apply(get_numeric)
    df_quarter.loc[:, 'Portfolio_Pct'] = df_quarter['Portfolio%'].apply(get_percentage_number)

    if is_last_quarter(quarter):
        df_quarter = update_last_quarter_with_nq_filings(df_quarter)

    return df_quarter


def quarter_analysis(quarter):
    """
    Analyzes stock data for a given quarter to find the most popular, bought, and sold stocks.
    
    Args:
        quarter (str): The quarter in 'YYYYQN' format.

    Returns:
        pd.DataFrame: A DataFrame with aggregated stock analysis for the quarter
    """
    # Fund level calculation
    df_fund_quarter = aggregate_quarter_by_fund(get_quarter_data(quarter))

    df_fund_quarter['is_buyer'] = df_fund_quarter['Delta_Value'] > 0
    df_fund_quarter['is_seller'] = df_fund_quarter['Delta_Value'] < 0
    df_fund_quarter['is_holder'] = df_fund_quarter['Shares'] > 0
    df_fund_quarter['is_new'] = df_fund_quarter['Delta'] == 'NEW'
    df_fund_quarter['is_closed'] = df_fund_quarter['Delta'] == 'CLOSE'
    
    # Stock level calculation
    df_analysis = (
        df_fund_quarter.groupby(['Ticker', 'Company'])
        .agg(
            Total_Value=('Value', 'sum'),
            Total_Delta_Value=('Delta_Value', 'sum'),
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
    df_analysis['Delta'] = np.where((df_analysis['New_Holder_Count'] == df_analysis['Holder_Count']) & (df_analysis['Close_Count'] == 0), np.inf, df_analysis['Total_Delta_Value'] / (df_analysis['Total_Value'] - df_analysis['Total_Delta_Value']) * 100)
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
    df_quarter = get_quarter_data(quarter)

    # Aggregates data for Ticker that may have multiple CUSIPs in the same hedge fund report
    return aggregate_quarter_by_fund(df_quarter[df_quarter['Ticker'] == ticker])
