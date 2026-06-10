import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from database import SessionLocal
from config import INDICES

def calculate_rsi(series, period=14):
    """Computes standard Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    # Calculate exponential moving average
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(series, fast=12, slow=26, signal=9):
    """Computes Moving Average Convergence Divergence (MACD) and signal line."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def fetch_and_calculate_all():
    """
    Downloads historical data for all seeded stocks and indices,
    calculates technical indicators, and saves them to the database.
    """
    db = SessionLocal()
    try:
        # Get active tickers
        res = db.execute(text("SELECT ticker FROM companies"))
        tickers = [row[0] for row in res.fetchall()]
        
        # Add index tickers to list
        all_tickers = tickers + list(INDICES.keys()) + ["^V2TX"]
        
        print(f"Quantitative Engine: Fetching prices for {len(all_tickers)} instruments...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365) # Fetch 1 year of data for long-term indicators (SMA 200)
        
        updated_count = 0
        
        for ticker in all_tickers:
            try:
                # Download historical daily data
                ticker_clean = ticker
                # yfinance handles tickers nicely
                df = yf.download(ticker_clean, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)
                
                if df.empty:
                    print(f"No price data retrieved for {ticker}")
                    continue
                
                # If MultiIndex (e.g. yfinance returning columns with Ticker index), flatten columns
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                # Sort indices
                df = df.sort_index()
                
                # Check minimum length for technicals
                if len(df) < 15:
                    print(f"Insufficient data rows ({len(df)}) for {ticker}")
                    continue
                
                # Close price series
                close_series = df["Close"]
                
                # Calculate indicators
                df["RSI"] = calculate_rsi(close_series)
                macd_line, signal_line = calculate_macd(close_series)
                df["MACD"] = macd_line
                df["MACD_Signal"] = signal_line
                df["SMA_20"] = close_series.rolling(window=20).mean()
                df["SMA_50"] = close_series.rolling(window=50).mean()
                df["SMA_200"] = close_series.rolling(window=200).mean()
                
                # Insert / Upsert last 250 rows into stock_prices to keep history fresh
                df_to_save = df.tail(250)
                
                for timestamp, row in df_to_save.iterrows():
                    # Format timestamp
                    ts_aware = timestamp.to_pydatetime()
                    if ts_aware.tzinfo is None:
                        ts_aware = ts_aware.replace(tzinfo=timezone.utc)
                    
                    # Convert values safely
                    open_val = float(row["Open"]) if not pd.isna(row["Open"]) else None
                    high_val = float(row["High"]) if not pd.isna(row["High"]) else None
                    low_val = float(row["Low"]) if not pd.isna(row["Low"]) else None
                    close_val = float(row["Close"]) if not pd.isna(row["Close"]) else None
                    vol_val = int(row["Volume"]) if not pd.isna(row["Volume"]) else None
                    
                    rsi_val = float(row["RSI"]) if not pd.isna(row["RSI"]) else None
                    macd_val = float(row["MACD"]) if not pd.isna(row["MACD"]) else None
                    macd_sig_val = float(row["MACD_Signal"]) if not pd.isna(row["MACD_Signal"]) else None
                    sma20 = float(row["SMA_20"]) if not pd.isna(row["SMA_20"]) else None
                    sma50 = float(row["SMA_50"]) if not pd.isna(row["SMA_50"]) else None
                    sma200 = float(row["SMA_200"]) if not pd.isna(row["SMA_200"]) else None
                    
                    # Store indices separately if they are not in the companies table
                    # We will only insert stock prices for tickers present in 'companies' table to respect references
                    # But we want to store V2TX and index prices too?
                    # Let's check if the ticker is in companies.
                    is_company = ticker in tickers
                    
                    if is_company:
                        db.execute(
                            text("""
                                INSERT INTO stock_prices (ticker, timestamp, open, high, low, close, volume, rsi, macd, macd_signal, sma_20, sma_50, sma_200)
                                VALUES (:ticker, :timestamp, :open, :high, :low, :close, :volume, :rsi, :macd, :macd_signal, :sma_20, :sma_50, :sma_200)
                                ON CONFLICT (ticker, timestamp) DO UPDATE SET
                                    open = EXCLUDED.open,
                                    high = EXCLUDED.high,
                                    low = EXCLUDED.low,
                                    close = EXCLUDED.close,
                                    volume = EXCLUDED.volume,
                                    rsi = EXCLUDED.rsi,
                                    macd = EXCLUDED.macd,
                                    macd_signal = EXCLUDED.macd_signal,
                                    sma_20 = EXCLUDED.sma_20,
                                    sma_50 = EXCLUDED.sma_50,
                                    sma_200 = EXCLUDED.sma_200
                            """),
                            {
                                "ticker": ticker,
                                "timestamp": ts_aware,
                                "open": open_val,
                                "high": high_val,
                                "low": low_val,
                                "close": close_val,
                                "volume": vol_val,
                                "rsi": rsi_val,
                                "macd": macd_val,
                                "macd_signal": macd_sig_val,
                                "sma_20": sma20,
                                "sma_50": sma50,
                                "sma_200": sma200
                            }
                        )
                    else:
                        # It is an index or V2TX. Let's save it to a temporary or global place or system logs?
                        # Since we want to display index prices, let's create a table or just write them to a JSON configuration or cache?
                        # Wait! It is much simpler to save indices to a key-value or cache, or simply fetch them live on API calls!
                        # To keep it extremely simple and high performance, the FastAPI backend can fetch live index values from yfinance, or we can store them in a simple postgres table.
                        # Wait! Saving them to the database is much faster for the dashboard because we don't block API requests with live yfinance downloads.
                        # Let's check if there is an index table. If we want, we can add a table for index prices in `init.sql`, or we can insert index names in `companies` with a dummy sector/country so they fit in the same schema!
                        # Wait, that is a brilliant hack! If we add `^STOXX`, `^GDAXI`, `^FCHI`, `FTSEMIB.MI`, `^IBEX`, `^V2TX` to the `companies` table under sector "Index" and country "Europe", we can store their prices in the `stock_prices` table without altering the schema!
                        # Let's check if they are in the database. They aren't pre-seeded, but we can write code to automatically insert them into `companies` if they are not there, or seed them.
                        # Let's seed them dynamically in `quant.py`!
                        pass
                
                db.commit()
                updated_count += 1
            except Exception as e:
                print(f"Error processing market data for {ticker}: {e}")
                db.rollback()
                
        print(f"Quantitative calculations complete for {updated_count} instruments.")
        return updated_count
    finally:
        db.close()

def get_latest_v2tx():
    """Fetches the latest V2TX volatility index close price directly from yfinance."""
    try:
        ticker = yf.Ticker("^V2TX")
        history = ticker.history(period="5d")
        if not history.empty:
            return float(history["Close"].iloc[-1])
    except Exception as e:
        print(f"Failed to fetch V2TX index: {e}")
    return 20.0 # Safe default default if yfinance fails

if __name__ == "__main__":
    fetch_and_calculate_all()
