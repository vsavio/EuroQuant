import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sqlalchemy import text

def fetch_historical_returns(tickers, db, days=90):
    """
    Fetches historical daily close prices for tickers from the DB,
    computes returns, and returns a DataFrame of daily returns.
    """
    if not tickers:
        return pd.DataFrame()

    # Query daily stock prices
    query = text("""
        SELECT ticker, timestamp::date as date, close
        FROM stock_prices
        WHERE ticker IN :tickers AND timestamp >= NOW() - INTERVAL '1 day' * :days
        ORDER BY timestamp ASC
    """)
    rows = db.execute(query, {"tickers": tuple(tickers), "days": days}).fetchall()
    
    if not rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    
    # Pivot to wide format (rows = date, columns = ticker)
    pivot_df = df.pivot_table(index="date", columns="ticker", values="close")
    
    # Drop columns that have mostly null values, and forward-fill/back-fill the rest
    pivot_df = pivot_df.dropna(thresh=int(len(pivot_df) * 0.5), axis=1)
    pivot_df = pivot_df.ffill().bfill()
    
    # Calculate daily returns
    returns_df = pivot_df.pct_change().dropna()
    return returns_df

def optimize_portfolio(tickers, db, method="max_sharpe", use_black_litterman=True, rf=0.0):
    """
    Performs Markowitz or Black-Litterman optimization for a set of tickers.
    Returns optimal weights and expected portfolio metrics.
    """
    returns_df = fetch_historical_returns(tickers, db, days=90)
    if returns_df.empty or returns_df.shape[1] < 2:
        # Return fallback equal weights
        n = len(tickers)
        return {
            "weights": {t: 1.0/n for t in tickers},
            "expected_return": 0.0,
            "expected_volatility": 0.0,
            "sharpe_ratio": 0.0
        }
    
    active_tickers = list(returns_df.columns)
    N = len(active_tickers)
    
    # Calculate daily covariance matrix and average daily returns
    # Annualized multiplier is 252 trading days
    cov_matrix = returns_df.cov().values * 252
    mean_returns = returns_df.mean().values * 252
    
    # Fetch sentiment scores to inject into Black-Litterman
    sentiment_dict = {}
    query = text("""
        SELECT ticker, sentiment_score
        FROM recommendations
        WHERE ticker IN :tickers
    """)
    rows = db.execute(query, {"tickers": tuple(active_tickers)}).fetchall()
    for row in rows:
        sentiment_dict[row[0]] = float(row[1]) if row[1] is not None else 0.0
        
    # Standardize views
    q_views = np.array([sentiment_dict.get(t, 0.0) * 0.15 for t in active_tickers]) # view adjustment up to 15%
    
    if use_black_litterman:
        # Black-Litterman Posteriori calculation
        # Pi = historical returns (Prior)
        Pi = mean_returns
        tau = 0.05
        P = np.eye(N)
        
        # Omega: View uncertainty (diagonal of returns variance scaled)
        omega = np.diag(np.diag(cov_matrix) * tau)
        
        # BL formula: mu_bl = [(tau * Sigma)^-1 + P^T * Omega^-1 * P]^-1 * [(tau * Sigma)^-1 * Pi + P^T * Omega^-1 * Q]
        try:
            tau_cov_inv = np.linalg.inv(tau * cov_matrix)
            omega_inv = np.linalg.inv(omega)
            
            middle_inv = np.linalg.inv(tau_cov_inv + omega_inv)
            mu_bl = np.dot(middle_inv, np.dot(tau_cov_inv, Pi) + q_views)
        except Exception:
            # Fallback to mean returns if matrix inversion fails
            mu_bl = mean_returns
    else:
        mu_bl = mean_returns

    # Optimization objectives
    def portfolio_annual_variance(w):
        return np.dot(w.T, np.dot(cov_matrix, w))
        
    def portfolio_annual_return(w):
        return np.dot(w.T, mu_bl)

    def negative_sharpe(w):
        ret = portfolio_annual_return(w)
        vol = np.sqrt(portfolio_annual_variance(w))
        if vol == 0:
            return 0.0
        return - (ret - rf) / vol

    # Constraints: sum(w) = 1
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
    # Bounds: 0 <= w_i <= 1
    bounds = tuple((0.0, 1.0) for _ in range(N))
    # Initial guess: equal weight
    init_weights = np.ones(N) / N

    if method == "max_sharpe":
        res = minimize(negative_sharpe, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
    else: # min_volatility
        res = minimize(portfolio_annual_variance, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)

    if not res.success:
        # Equal weights fallback
        opt_weights = init_weights
    else:
        opt_weights = res.x

    # Calculate final portfolio statistics
    p_return = float(portfolio_annual_return(opt_weights))
    p_vol = float(np.sqrt(portfolio_annual_variance(opt_weights)))
    p_sharpe = (p_return - rf) / p_vol if p_vol > 0 else 0.0

    # Clean small weights to avoid rounding noise
    weight_map = {}
    for i, t in enumerate(active_tickers):
        w = float(opt_weights[i])
        weight_map[t] = w if w > 0.005 else 0.0
        
    # Re-normalize cleaned weights
    total_w = sum(weight_map.values())
    if total_w > 0:
        weight_map = {t: w / total_w for t, w in weight_map.items()}
    else:
        weight_map = {t: 1.0/N for t in active_tickers}

    return {
        "weights": weight_map,
        "expected_return": p_return,
        "expected_volatility": p_vol,
        "sharpe_ratio": p_sharpe
    }
