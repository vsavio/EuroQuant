import os
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sqlalchemy import text, create_engine

# Initialize database connection engine
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db")
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=20)

def fetch_historical_returns(tickers, db, days=90):
    if not tickers:
        return pd.DataFrame()
        
    price_data = {}
    for ticker in tickers:
        rows = db.execute(
            text("""
                SELECT timestamp, close 
                FROM stock_prices 
                WHERE ticker = :ticker AND close IS NOT NULL 
                ORDER BY timestamp DESC 
                LIMIT :limit
            """),
            {"ticker": ticker, "limit": days}
        ).fetchall()
        if len(rows) >= 15:
            dates = [r[0] for r in rows][::-1]
            closes = [float(r[1]) for r in rows][::-1]
            price_data[ticker] = pd.Series(closes, index=dates)
            
    if not price_data:
        return pd.DataFrame()
        
    df_prices = pd.DataFrame(price_data).ffill().bfill()
    df_returns = np.log(df_prices / df_prices.shift(1)).dropna()
    return df_returns

def optimize_portfolio(tickers, db, method="max_sharpe", use_black_litterman=True, rf=0.0):
    df_returns = fetch_historical_returns(tickers, db, days=90)
    
    # Fallback if insufficient data
    if df_returns.empty or df_returns.shape[1] < 2:
        eq_weight = 1.0 / len(tickers) if tickers else 0.0
        return {
            "weights": {t: eq_weight for t in tickers},
            "expected_return": 0.0,
            "expected_volatility": 0.0,
            "sharpe_ratio": 0.0
        }
        
    # Active tickers with data
    active_tickers = df_returns.columns.tolist()
    num_assets = len(active_tickers)
    
    # Historical Mean Returns & Covariance (Annualized)
    mu_hist = df_returns.mean().values * 252
    cov_matrix = df_returns.cov().values * 252
    
    # Define Posterior Mu (expected returns)
    mu_target = mu_hist.copy()
    
    # Apply Black-Litterman
    if use_black_litterman:
        views = []
        P_matrix = []
        
        # Get AI Predictions
        for i, ticker in enumerate(active_tickers):
            row = db.execute(
                text("SELECT ml_prediction_prob FROM recommendations WHERE ticker = :ticker ORDER BY timestamp DESC LIMIT 1"),
                {"ticker": ticker}
            ).fetchone()
            
            prob = row[0] if row and row[0] is not None else 0.50
            
            # Map ML prob to a target view (Assuming 0.5 is market average return, >0.5 implies positive view)
            # e.g., 0.80 probability -> 15% annualized expected return view
            # e.g., 0.20 probability -> -10% annualized expected return view
            view_return = (prob - 0.5) * 0.50  # scaled mapping
            
            # We construct the P matrix (Pick matrix)
            p_row = np.zeros(num_assets)
            p_row[i] = 1.0
            
            P_matrix.append(p_row)
            views.append(view_return)
            
        P = np.array(P_matrix)
        Q = np.array(views)
        
        # Tau is a scalar indicating the uncertainty of the prior (market equilibrium)
        tau = 0.025
        
        # Uncertainty of the views (Omega), diagonal matrix.
        # Often proportional to the variance of the asset priors.
        omega = np.diag(np.diag(P @ (tau * cov_matrix) @ P.T))
        
        # Black-Litterman Equation for Posterior Expected Returns
        try:
            # mu_BL = [(tau * Cov)^-1 + P^T * Omega^-1 * P]^-1 * [(tau * Cov)^-1 * mu_hist + P^T * Omega^-1 * Q]
            tau_cov_inv = np.linalg.inv(tau * cov_matrix)
            omega_inv = np.linalg.inv(omega)
            
            part1 = np.linalg.inv(tau_cov_inv + P.T @ omega_inv @ P)
            part2 = tau_cov_inv @ mu_hist + P.T @ omega_inv @ Q
            
            mu_target = part1 @ part2
        except np.linalg.LinAlgError:
            print("Matrix inversion failed during Black-Litterman calculation. Falling back to historical means.")
            mu_target = mu_hist

    # Objective functions for SciPy
    def negative_sharpe(weights, mu, cov, rf_rate):
        port_ret = np.dot(weights, mu)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
        if port_vol == 0:
            return 0.0
        return -(port_ret - rf_rate) / port_vol

    def portfolio_volatility(weights, cov):
        return np.sqrt(np.dot(weights.T, np.dot(cov, weights)))

    # Constraints and Bounds
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
    bounds = tuple((0.0, 0.40) for _ in range(num_assets))  # Max 40% per asset
    init_guess = np.array(num_assets * [1.0 / num_assets])
    
    if method == "min_volatility":
        res = minimize(portfolio_volatility, init_guess, args=(cov_matrix,), method='SLSQP', bounds=bounds, constraints=constraints)
    else:
        # max_sharpe
        res = minimize(negative_sharpe, init_guess, args=(mu_target, cov_matrix, rf), method='SLSQP', bounds=bounds, constraints=constraints)
        
    final_weights = {}
    expected_ret = 0.0
    expected_vol = 0.0
    sharpe = 0.0
    
    if res.success:
        opt_w = res.x
        expected_ret = float(np.dot(opt_w, mu_target))
        expected_vol = float(np.sqrt(np.dot(opt_w.T, np.dot(cov_matrix, opt_w))))
        sharpe = float((expected_ret - rf) / expected_vol) if expected_vol > 0 else 0.0
        
        for i, t in enumerate(active_tickers):
            final_weights[t] = float(np.round(opt_w[i], 4))
    else:
        print(f"Portfolio optimization solver failed: {res.message}. Falling back to equal weight.")
        eq = 1.0 / num_assets
        final_weights = {t: eq for t in active_tickers}
        opt_w = np.array([eq] * num_assets)
        expected_ret = float(np.dot(opt_w, mu_target))
        expected_vol = float(np.sqrt(np.dot(opt_w.T, np.dot(cov_matrix, opt_w))))
        sharpe = float((expected_ret - rf) / expected_vol) if expected_vol > 0 else 0.0

    # Ensure all original tickers are in the final dict (0.0 if not active)
    for t in tickers:
        if t not in final_weights:
            final_weights[t] = 0.0
            
    return {
        "weights": final_weights,
        "expected_return": expected_ret,
        "expected_volatility": expected_vol,
        "sharpe_ratio": sharpe
    }

def get_optimized_portfolio_weights():
    # Backward compatibility for any remaining legacy calls
    with engine.connect() as db:
        tickers = [r[0] for r in db.execute(text("SELECT ticker FROM companies")).fetchall()]
        res = optimize_portfolio(tickers, db, method="max_sharpe", use_black_litterman=False)
        return res["weights"]
