import os
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sqlalchemy import text, create_engine

# Initialize database connection engine
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db")
engine = create_engine(DATABASE_URL)

def get_optimized_portfolio_weights():
    """
    Retrieves historical price data for all active companies, calculates the 
    covariance matrix of daily returns, and uses SciPy to compute the optimal Markowitz 
    portfolio weights that maximize the Sharpe Ratio (long-only, fully invested constraint).
    """
    try:
        with engine.connect() as conn:
            # Fetch active tickers
            tickers_rows = conn.execute(text("SELECT ticker FROM companies")).fetchall()
            tickers = [r[0] for r in tickers_rows]
            if not tickers:
                return {}
                
            # Fetch price history for each ticker (last 90 days)
            price_data = {}
            for ticker in tickers:
                rows = conn.execute(
                    text("""
                        SELECT timestamp, close 
                        FROM stock_prices 
                        WHERE ticker = :ticker AND close IS NOT NULL 
                        ORDER BY timestamp DESC 
                        LIMIT 90
                    """),
                    {"ticker": ticker}
                ).fetchall()
                if len(rows) >= 15:
                    # Store prices chronologically
                    dates = [r[0] for r in rows][::-1]
                    closes = [float(r[1]) for r in rows][::-1]
                    price_data[ticker] = pd.Series(closes, index=dates)
                    
            if len(price_data) < 2:
                # Not enough assets to perform optimization, return equal weights
                equal_weight = 1.0 / len(tickers) if tickers else 0.0
                return {ticker: equal_weight for ticker in tickers}
                
            # Align series into a DataFrame
            df_prices = pd.DataFrame(price_data).ffill().bfill()
            # Calculate daily log-returns
            df_returns = np.log(df_prices / df_prices.shift(1)).dropna()
            
            if df_returns.empty or df_returns.shape[0] < 10:
                equal_weight = 1.0 / len(tickers) if tickers else 0.0
                return {ticker: equal_weight for ticker in tickers}
                
            # Calculate expected annualized returns and covariance matrix
            mean_returns = df_returns.mean() * 252
            cov_matrix = df_returns.cov() * 252
            
            num_assets = len(price_data)
            
            # Define objective function (negative Sharpe Ratio)
            def negative_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=0.03):
                p_ret = np.sum(mean_returns * weights)
                p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                if p_vol == 0:
                    return 0.0
                return -(p_ret - risk_free_rate) / p_vol
                
            # Constraints: sum of weights is 1.0
            constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
            # Bounded between 0% and 50% max per single stock to ensure diversification
            bounds = tuple((0.0, 0.50) for _ in range(num_assets))
            # Initial guess (equal weights)
            initial_guess = num_assets * [1.0 / num_assets]
            
            # Optimize
            result = minimize(
                negative_sharpe_ratio,
                initial_guess,
                args=(mean_returns, cov_matrix),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if result.success:
                weights = result.x
                optimized_weights = {}
                # Map optimized weights back to tickers
                for i, ticker in enumerate(df_returns.columns):
                    optimized_weights[ticker] = float(np.round(weights[i], 4))
                    
                # Fill missing active tickers (if any got filtered out due to insufficient data) with 0.0
                for ticker in tickers:
                    if ticker not in optimized_weights:
                        optimized_weights[ticker] = 0.0
                return optimized_weights
            else:
                print(f"Portfolio optimization solver failed: {result.message}. Falling back to equal weight.")
                equal_weight = 1.0 / len(tickers) if tickers else 0.0
                return {ticker: equal_weight for ticker in tickers}
                
    except Exception as e:
        print(f"Error calculating portfolio optimization: {e}")
        equal_weight = 1.0 / len(tickers) if tickers else 0.0
        return {ticker: equal_weight for ticker in tickers}
