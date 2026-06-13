import math
import numpy as np
import pandas as pd
from sqlalchemy import text
from database import SessionLocal

def classify_market_regimes():
    """
    Computes rolling volatility and trend indicators to classify the active market regime 
    for each company and updates the market_regimes table.
    """
    db = SessionLocal()
    try:
        # Fetch active tickers
        tickers_rows = db.execute(text("SELECT ticker FROM companies")).fetchall()
        tickers = [r[0] for r in tickers_rows]
        
        print(f"Regime Switching: Evaluating {len(tickers)} companies...")
        
        for ticker in tickers:
            # Fetch last 120 stock price bars
            query = text("""
                SELECT timestamp, open, high, low, close 
                FROM stock_prices 
                WHERE ticker = :ticker 
                ORDER BY timestamp DESC 
                LIMIT 120
            """)
            rows = db.execute(query, {"ticker": ticker}).fetchall()
            if len(rows) < 30:
                # Not enough historical data to compute stable regime statistics
                db.execute(text("""
                    INSERT INTO market_regimes (ticker, regime, volatility_30d, atr_ratio, timestamp)
                    VALUES (:ticker, 'REGIME_MEAN_REVERTING', 0.0, 0.0, NOW())
                    ON CONFLICT (ticker) DO UPDATE 
                    SET regime = EXCLUDED.regime, timestamp = NOW()
                """), {"ticker": ticker})
                db.commit()
                continue
            
            # Load into DataFrame (reverse order to get chronological time series)
            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close'])
            df = df.iloc[::-1].reset_index(drop=True)
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            
            # Calculate daily log-returns
            df['returns'] = np.log(df['close'] / df['close'].shift(1))
            
            # Compute rolling 30-day volatility (annualized assuming 252 days)
            df['vol_30d'] = df['returns'].rolling(30).std() * math.sqrt(252)
            
            # Compute True Range (TR)
            df['prev_close'] = df['close'].shift(1)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = (df['high'] - df['prev_close']).abs()
            df['tr3'] = (df['low'] - df['prev_close']).abs()
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            # ATR Ratio: ATR(14) divided by price to get volatility percentage
            df['atr_14'] = df['tr'].rolling(14).mean()
            df['atr_ratio'] = df['atr_14'] / df['close']
            
            # Get latest values
            latest = df.iloc[-1]
            current_vol = float(latest['vol_30d']) if not pd.isna(latest['vol_30d']) else 0.0
            current_atr_ratio = float(latest['atr_ratio']) if not pd.isna(latest['atr_ratio']) else 0.0
            
            # Baseline median statistics for normalization
            median_vol = df['vol_30d'].median()
            if pd.isna(median_vol) or median_vol == 0:
                median_vol = 0.15 # fallback 15% annual vol
                
            # Short-term trend (10-day return)
            recent_return = float(df['close'].iloc[-1] / df['close'].iloc[-10] - 1.0)
            
            # Classification Logic
            if current_vol > 1.4 * median_vol:
                # High volatility regime
                if recent_return < -0.02:
                    regime = "REGIME_PANIC"
                else:
                    regime = "REGIME_HIGH_VOLATILITY"
            else:
                # Normal/Low volatility regime
                if abs(recent_return) > 0.025:
                    regime = "REGIME_QUIET_TREND"
                else:
                    regime = "REGIME_MEAN_REVERTING"
            
            # Persist to database
            db.execute(text("""
                INSERT INTO market_regimes (ticker, regime, volatility_30d, atr_ratio, timestamp)
                VALUES (:ticker, :regime, :vol, :atr, NOW())
                ON CONFLICT (ticker) DO UPDATE 
                SET regime = EXCLUDED.regime, 
                    volatility_30d = EXCLUDED.volatility_30d, 
                    atr_ratio = EXCLUDED.atr_ratio, 
                    timestamp = NOW()
            """), {
                "ticker": ticker,
                "regime": regime,
                "vol": current_vol,
                "atr": current_atr_ratio
            })
            db.commit()
            
        print("Regime Switching evaluation completed.")
    except Exception as e:
        print(f"Error classifying market regimes: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    classify_market_regimes()
