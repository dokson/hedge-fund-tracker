from app.utils.database import get_all_quarter_files, load_stocks
from app.utils.strings import get_numeric, get_percentage_number
from pathlib import Path
import pandas as pd

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
        fund_name = Path(file_path).stem
        
        df = pd.read_csv(file_path)

        total_row = df[df['CUSIP'] == 'Total']
        total_portfolio_value = get_numeric(total_row['Value'].iloc[0])

        df_stocks = df[df['CUSIP'] != 'Total'].copy()

        df_stocks.loc[:, 'Delta_Value_Num'] = df_stocks['Delta_Value'].apply(get_numeric)
        df_stocks.loc[:, 'Value_Num'] = df_stocks['Value'].apply(get_numeric)
        df_stocks.loc[:, 'Weighted_Delta_Pct'] = (df_stocks['Delta_Value_Num'] / total_portfolio_value) * 100
        df_stocks.loc[:, 'Portfolio_Pct'] = df_stocks['Portfolio%'].apply(get_percentage_number)
        df_stocks.loc[:, 'Fund'] = fund_name

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

    # Using named aggregation for clarity and to avoid multi-level columns
    df_analysis = (
        df_quarter.groupby('CUSIP')
        .agg(
            Total_Value=('Value_Num', 'sum'),
            Total_Delta_Value=('Delta_Value_Num', 'sum'),
            Total_Weighted_Delta_Pct=('Weighted_Delta_Pct', 'sum'),
            Max_Portfolio_Pct=('Portfolio_Pct', 'max'),
            Buyer_Count=('Delta_Value_Num', lambda s: (s > 0).sum()),
            Seller_Count=('Delta_Value_Num', lambda s: (s < 0).sum()),
            Holder_Count=('Fund', lambda s: s[df_quarter.loc[s.index, 'Delta'] != 'CLOSE'].nunique()),
            New_Holder_Count=('Fund', lambda s: s[df_quarter.loc[s.index, 'Delta'] == 'NEW'].nunique()),
        )
        .reset_index()
    )

    df_analysis['Net_Buyers'] = df_analysis['Buyer_Count'] - df_analysis['Seller_Count']

    # Retrieve ticker and company name from stocks masterdata
    df_stocks = load_stocks() 
    df_analysis = df_analysis.set_index('CUSIP').join(df_stocks[['Ticker', 'Company']], how='left').reset_index()

    return df_analysis
