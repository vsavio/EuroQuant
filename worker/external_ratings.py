import yfinance as yf
from tradingview_ta import TA_Handler, Interval
import logging

log = logging.getLogger("external_ratings")

def map_ticker_to_tradingview(ticker: str):
    """
    Maps a Yahoo Finance ticker to TradingView screener and exchange.
    Returns (symbol, screener, exchange).
    """
    if ticker.endswith(".MI"):
        return ticker.replace(".MI", ""), "italy", "MIL"
    elif ticker.endswith(".DE"):
        return ticker.replace(".DE", ""), "germany", "XETR"
    elif ticker.endswith(".L"):
        return ticker.replace(".L", ""), "uk", "LSE"
    elif ticker.endswith(".MC"):
        return ticker.replace(".MC", ""), "spain", "BME"
    elif ticker.endswith(".PA"):
        return ticker.replace(".PA", ""), "france", "EURONEXT"
    elif ticker.endswith(".AS"):
        return ticker.replace(".AS", ""), "netherlands", "EURONEXT"
    elif ticker.endswith(".KS"):
        return ticker.replace(".KS", ""), "korea", "KRX"
    elif ticker.endswith(".TW"):
        return ticker.replace(".TW", ""), "taiwan", "TWSE"
    elif ticker.endswith(".HK"):
        return ticker.replace(".HK", ""), "hongkong", "HKEX"
    elif ticker.endswith(".T"):
        return ticker.replace(".T", ""), "japan", "TSE"
    
    # Forex & Crypto mapping
    if "=" in ticker:
        clean = ticker.replace("=X", "").replace("=F", "")
        if "USD" in clean or len(clean) == 6:
            return clean, "forex", "FX_IDC"
        return clean, "america", "COMEX" # Commodities fallback
        
    if "USD" in ticker and len(ticker) >= 6:
        return ticker, "crypto", "BINANCE"
        
    # US Stocks
    return ticker, "america", "NASDAQ"

def get_tradingview_rating(ticker: str) -> str:
    """
    Fetches the pre-calculated Technical Analysis rating from TradingView.
    Tries multiple exchange aliases to handle naming inconsistencies.
    """
    tv_symbol, screener, exchange = map_ticker_to_tradingview(ticker)

    # Build a list of (exchange, screener) candidates to try in order
    candidates = [(exchange, screener)]

    # Add known alternate exchanges per market
    if ticker.endswith(".L"):
        candidates += [("LONDON", "uk"), ("LSE", "uk"), ("LSEETF", "uk")]
    elif ticker.endswith(".DE"):
        candidates += [("FWB", "germany"), ("XETR", "germany"), ("DB", "germany")]
    elif ticker.endswith(".PA"):
        candidates += [("EURONEXT", "france"), ("EPA", "france")]
    elif ticker.endswith(".MC"):
        candidates += [("BME", "spain"), ("BMAD", "spain")]
    elif ticker.endswith(".MI"):
        candidates += [("MIL", "italy"), ("MILSEDEX", "italy")]
    elif screener == "america":
        candidates += [("NYSE", "america"), ("NASDAQ", "america"), ("AMEX", "america")]
    
    for exch, scr in candidates:
        try:
            handler = TA_Handler(
                symbol=tv_symbol,
                screener=scr,
                exchange=exch,
                interval=Interval.INTERVAL_1_DAY
            )
            result = handler.get_analysis().summary.get("RECOMMENDATION", "HOLD")
            return result
        except Exception:
            continue

    log.warning(f"TradingView fetch failed for {ticker}: Exchange or symbol not found after all retries.")
    return "N/A"

def get_yfinance_consensus(ticker: str) -> str:
    """
    Fetches the Wall Street Analyst consensus from Yahoo Finance.
    """
    try:
        stock = yf.Ticker(ticker)
        # Alcuni ticker europei potrebbero non avere le recommendations
        rec = stock.recommendations
        if rec is not None and not rec.empty:
            # yfinance returns a DataFrame. We look for the most recent period or consensus.
            # In newer yfinance versions, recommendations is a dataframe with columns like 'strongBuy', 'buy', 'hold', 'sell', 'strongSell'
            latest = rec.iloc[0]
            
            strong_buy = latest.get("strongBuy", 0)
            buy = latest.get("buy", 0)
            hold = latest.get("hold", 0)
            sell = latest.get("sell", 0)
            strong_sell = latest.get("strongSell", 0)
            
            total_buy = strong_buy + buy
            total_sell = strong_sell + sell
            
            if total_buy > hold and total_buy > total_sell:
                return "BUY" if strong_buy < buy else "STRONG BUY"
            elif total_sell > hold and total_sell > total_buy:
                return "SELL" if strong_sell < sell else "STRONG SELL"
            else:
                return "HOLD"
        else:
            return "N/A"
    except Exception as e:
        log.warning(f"Yahoo Finance consensus failed for {ticker}: {e}")
        return "N/A"

def fetch_external_ratings(ticker: str) -> dict:
    return {
        "tradingview": get_tradingview_rating(ticker),
        "yfinance_analysts": get_yfinance_consensus(ticker)
    }
