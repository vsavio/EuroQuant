import os
import pandas as pd
import yfinance as yf

class DataFeed:
    def download_history(self, ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
        raise NotImplementedError("Each data feed must implement download_history")

class YFinanceFeed(DataFeed):
    def download_history(self, ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
        print(f"[YFinanceFeed] Downloading history for {ticker}...")
        if start and end:
            df = yf.download(ticker, start=start, end=end, progress=False)
        else:
            df = yf.download(ticker, period="2y", progress=False)
        if df.empty:
            raise ValueError(f"No data returned from Yahoo Finance for ticker {ticker}")
        return df

class ProfessionalFeed(DataFeed):
    def __init__(self):
        self.api_key = os.environ.get("POLYGON_API_KEY") or os.environ.get("ALPACA_API_KEY")

    def download_history(self, ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
        if not self.api_key:
            raise ValueError("Professional API credentials (POLYGON_API_KEY / ALPACA_API_KEY) not set.")
        
        # Here would go actual professional API connection code.
        raise ValueError("Professional Feed demo fallback triggered.")

def download_ticker_history(ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
    """
    Downloads historical price data trying professional feeds first,
    falling back to Yahoo Finance if they fail or are unconfigured.
    """
    feeds = [ProfessionalFeed(), YFinanceFeed()]
    for feed in feeds:
        try:
            df = feed.download_history(ticker, start, end)
            if not df.empty:
                return df
        except Exception as e:
            print(f"Feed {feed.__class__.__name__} failed for {ticker}: {e}")
            continue
    raise RuntimeError(f"All data feeds failed to download data for ticker {ticker}")
