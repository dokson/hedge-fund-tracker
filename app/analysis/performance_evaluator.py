from app.stocks.price_fetcher import PriceFetcher
from app.utils.database import load_fund_holdings
from app.utils.strings import get_quarter_date, get_previous_quarter
from datetime import datetime
import pandas as pd

EVAL_TOP_N_POSITIONS = 100


class PerformanceEvaluator:
    """
    Evaluates fund performance by calculating price-based returns of holdings,
    isolating management skill from capital flows.
    """
    @classmethod
    def calculate_quarterly_performance(cls, fund_name, target_quarter):
        """
        Calculates the Holding-Based Return (HBR) for a fund for the specified quarter.
        HBR = Σ (Weight_i * Return_i) for all positions held at the start of the quarter.
        Only the top EVAL_TOP_N_POSITIONS positions by value are considered to optimize speed.
        """
        prev_quarter = get_previous_quarter(target_quarter)
        
        # Load holdings from the start of the quarter (end of the previous quarter)
        df_prev = load_fund_holdings(fund_name, prev_quarter)
        if df_prev.empty:
            return {"error": f"Missing data for {fund_name} in {prev_quarter} (Start of quarter)."}
        
        # Limit to top N positions by value to avoid excessive API calls
        df_prev = df_prev.sort_values(by='Value', ascending=False).head(EVAL_TOP_N_POSITIONS)
        
        # Load holdings at the end of the target quarter
        df_target = load_fund_holdings(fund_name, target_quarter)
        
        # We need the end date of the target quarter for price fetching of closed positions
        end_date_str = get_quarter_date(target_quarter)
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        # Merge previous holdings with target holdings to see which positions were kept/closed
        df_eval = pd.merge(
            df_prev,
            df_target[['CUSIP', 'Reported_Price', 'Shares']],
            on='CUSIP',
            how='left',
            suffixes=('_prev', '_curr')
        )

        total_start_value = df_eval['Value'].sum()
        if total_start_value == 0:
            # This case should be handled by df_prev.empty check, but good for robustness
            return {"error": "Total start value is zero after filtering", "fund": fund_name, "quarter": target_quarter}

        df_eval['Weight'] = df_eval['Value'] / total_start_value

        def get_return(row):
            price_start = row['Reported_Price_prev']
            price_end = row['Reported_Price_curr']
            
            if price_start == 0:
                return 0.0
            
            # If the position was closed, it won't appear in the current report.
            # We fetch the approximate end-of-quarter price to calculate the return.
            if pd.isna(price_end) or price_end == 0:
                print(f"Fetching price for {row['Ticker']} on {end_date} (closed position)...")
                price_end = PriceFetcher.get_avg_price(row['Ticker'], end_date)
                
                # Fallback to no gain (return 0.0) if price fetching fails.
                if price_end is None:
                    return 0.0
            
            return (price_end / price_start) - 1

        # Calculate returns and weighted contributions (scaled to percentages)
        df_eval['Return'] = df_eval.apply(get_return, axis=1) * 100
        df_eval['Weighted_Return'] = df_eval['Weight'] * df_eval['Return']

        portfolio_return = df_eval['Weighted_Return'].sum()
        total_end_value = total_start_value * (1 + portfolio_return / 100)
        
        top_contributors = df_eval.sort_values(by='Weighted_Return', ascending=False).head(10)[['Ticker', 'Company', 'Weight', 'Return', 'Weighted_Return']].to_dict('records')
        top_detractors = df_eval.sort_values(by='Weighted_Return', ascending=True).head(10)[['Ticker', 'Company', 'Weight', 'Return', 'Weighted_Return']].to_dict('records')

        return {
            "fund": fund_name,
            "quarter": target_quarter,
            "portfolio_return": portfolio_return,
            "start_value": total_start_value,
            "end_value": total_end_value,
            "top_contributors": top_contributors,
            "top_detractors": top_detractors
        }
