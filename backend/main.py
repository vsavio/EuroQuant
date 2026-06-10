from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import yfinance as yf
from sqlalchemy import create_engine, text
import os

app = FastAPI(title="EuroQuant institutional API", version="1.0.0")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db")
engine = create_engine(DATABASE_URL)

# Global tracker for MT5 clients and manual overrides
mt5_clients = {}
manual_overrides = {}

class OverridePayload(BaseModel):
    ticker: str
    action: str

class SignalHistoryItem(BaseModel):
    signal: str
    sentiment_score: Optional[float]
    price_change_24h: Optional[float]
    reason_technical: Optional[str]
    timestamp: str

# Models
class IndexSummary(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float

class VolatilitySummary(BaseModel):
    price: float
    status: str # SAFE, ELEVATED, RISK_WARNING
    message: str

class ForexSummary(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float

class MarketSummaryResponse(BaseModel):
    indices: List[IndexSummary]
    v2tx: VolatilitySummary
    forex: List[ForexSummary]

class ScreenerRow(BaseModel):
    ticker: str
    name: str
    country: str
    sector: str
    price: float
    price_change_24h: float
    sentiment_score: float
    signal: str # STRONG BUY, BUY, HOLD, SELL, STRONG SELL
    timestamp: datetime

class StockDetailResponse(BaseModel):
    ticker: str
    name: str
    country: str
    sector: str
    industry: str
    price: float
    price_change_24h: float
    sentiment_score: float
    signal: str
    reason_macro: Optional[str]
    reason_micro: Optional[str]
    reason_technical: Optional[str]
    history: List[dict]
    beta: float
    correlation: Optional[float]
    hedging_suggestion: str
    mt5_symbol: str
    stop_loss: float
    take_profit: float

class NewsArticleSchema(BaseModel):
    id: int
    title: str
    content: str
    url: str
    source: str
    published_date: datetime
    country: str
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]
    tickers: List[str]

# Helper to fetch index daily percent change
def get_index_performance(ticker: str) -> dict:
    try:
        # We can try to read from the stock_prices database first (faster)
        with engine.connect() as conn:
            query = text("""
                SELECT close, timestamp FROM stock_prices
                WHERE ticker = :ticker
                ORDER BY timestamp DESC
                LIMIT 2
            """)
            rows = conn.execute(query, {"ticker": ticker}).fetchall()
            
            if len(rows) >= 2:
                latest = float(rows[0][0])
                prev = float(rows[1][0])
                change_pct = ((latest - prev) / prev) * 100.0
                return {"price": latest, "change_pct": change_pct}
                
        # Fallback to yfinance if database lacks data
        t = yf.Ticker(ticker)
        history = t.history(period="2d")
        if not history.empty and len(history) >= 2:
            latest = float(history["Close"].iloc[-1])
            prev = float(history["Close"].iloc[-2])
            change_pct = ((latest - prev) / prev) * 100.0
            return {"price": latest, "change_pct": change_pct}
        elif not history.empty:
            latest = float(history["Close"].iloc[-1])
            return {"price": latest, "change_pct": 0.0}
    except Exception as e:
        print(f"Error fetching index performance for {ticker}: {e}")
    return {"price": 0.0, "change_pct": 0.0}

@app.get("/api/market-summary", response_model=MarketSummaryResponse)
def get_market_summary():
    indices_tickers = {
        "^STOXX": "STOXX Europe 600",
        "^GDAXI": "DAX 40",
        "^FCHI": "CAC 40",
        "FTSEMIB.MI": "FTSE MIB",
        "^IBEX": "IBEX 35"
    }
    
    indices_list = []
    for ticker, name in indices_tickers.items():
        perf = get_index_performance(ticker)
        indices_list.append(
            IndexSummary(
                ticker=ticker,
                name=name,
                price=round(perf["price"], 2),
                change_pct=round(perf["change_pct"], 2)
            )
        )
        
    forex_tickers = {
        "EURUSD=X": "EUR/USD",
        "GBPUSD=X": "GBP/USD",
        "EURGBP=X": "EUR/GBP",
        "EURJPY=X": "EUR/JPY",
        "EURCHF=X": "EUR/CHF"
    }
    
    forex_list = []
    for ticker, name in forex_tickers.items():
        perf = get_index_performance(ticker)
        forex_list.append(
            ForexSummary(
                ticker=ticker,
                name=name,
                price=round(perf["price"], 4),
                change_pct=round(perf["change_pct"], 2)
            )
        )
        
    # Get Volatility Index (V2TX)
    v2tx_perf = get_index_performance("^V2TX")
    v2tx_price = v2tx_perf["price"]
    
    # Evaluate risk status
    if v2tx_price >= 30.0:
        status = "RISK_WARNING"
        message = "SYSTEMIC RISK DETECTED: VSTOXX volatility is extreme. Buying is restricted."
    elif v2tx_price >= 20.0:
        status = "ELEVATED"
        message = "Volatility is elevated. Institutional hedges recommended."
    else:
        status = "SAFE"
        message = "Volatility environment is safe for standard execution."
        
    return MarketSummaryResponse(
        indices=indices_list,
        v2tx=VolatilitySummary(
            price=round(v2tx_price, 2) if v2tx_price > 0.0 else 18.50, # fallback default
            status=status,
            message=message
        ),
        forex=forex_list
    )

@app.get("/api/screener", response_model=List[ScreenerRow])
def get_screener():
    query = text("""
        SELECT c.ticker, c.name, c.country, c.sector,
               r.signal, r.sentiment_score, r.price_change_24h, r.timestamp,
               (SELECT close FROM stock_prices p WHERE p.ticker = c.ticker ORDER BY p.timestamp DESC LIMIT 1) as latest_close
        FROM companies c
        JOIN recommendations r ON c.ticker = r.ticker
        WHERE c.sector NOT IN ('Index', 'Forex')
        ORDER BY r.sentiment_score DESC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query).fetchall()
        
    rows = []
    for r in result:
        ticker, name, country, sector, signal, sent_score, change_24h, ts, price = r
        rows.append(
            ScreenerRow(
                ticker=ticker,
                name=name,
                country=country,
                sector=sector,
                price=float(price) if price else 0.0,
                price_change_24h=float(change_24h) if change_24h else 0.0,
                sentiment_score=float(sent_score) if sent_score else 0.0,
                signal=signal,
                timestamp=ts
            )
        )
    return rows

@app.get("/api/stock/{ticker}", response_model=StockDetailResponse)
def get_stock_detail(ticker: str):
    # Fetch company base details
    with engine.connect() as conn:
        comp = conn.execute(
            text("SELECT name, country, sector, industry FROM companies WHERE ticker = :ticker"),
            {"ticker": ticker}
        ).fetchone()
        
        if not comp:
            raise HTTPException(status_code=404, detail="Company not found")
            
        name, country, sector, industry = comp
        
        # Fetch recommendation details
        rec = conn.execute(
            text("""
                SELECT signal, sentiment_score, price_change_24h, reason_macro, reason_micro, reason_technical
                FROM recommendations
                WHERE ticker = :ticker
            """),
            {"ticker": ticker}
        ).fetchone()
        
        signal = "HOLD"
        sent_score = 0.0
        change_24h = 0.0
        reason_macro = "No analysis available yet."
        reason_micro = "No analysis available yet."
        reason_technical = "No analysis available yet."
        
        if rec:
            signal, sent_score, change_24h, reason_macro, reason_micro, reason_technical = rec
            
        # Fetch price history (last 100 rows for rich charts)
        prices = conn.execute(
            text("""
                SELECT timestamp, open, high, low, close, volume, rsi, macd, macd_signal, sma_20, sma_50, sma_200
                FROM stock_prices
                WHERE ticker = :ticker
                ORDER BY timestamp ASC
                LIMIT 100
            """),
            {"ticker": ticker}
        ).fetchall()
        
        history_list = []
        latest_price = 0.0
        for p in prices:
            ts, o, h, l, c, v, rsi, macd, macd_sig, sma20, sma50, sma200 = p
            latest_price = float(c) if c else latest_price
            history_list.append({
                "date": ts.strftime("%Y-%m-%d"),
                "open": float(o) if o else None,
                "high": float(h) if h else None,
                "low": float(l) if l else None,
                "close": float(c) if c else None,
                "volume": int(v) if v else None,
                "rsi": float(rsi) if rsi else None,
                "macd": float(macd) if macd else None,
                "macd_signal": float(macd_sig) if macd_sig else None,
                "sma_20": float(sma20) if sma20 else None,
                "sma_50": float(sma50) if sma50 else None,
                "sma_200": float(sma200) if sma200 else None
            })
            
        # 1. Fetch price returns for Beta calculation (last 60 trading days)
        stock_prices_60 = conn.execute(
            text("""
                SELECT close, timestamp FROM stock_prices
                WHERE ticker = :ticker
                ORDER BY timestamp DESC
                LIMIT 61
            """),
            {"ticker": ticker}
        ).fetchall()
        
        market_prices_60 = conn.execute(
            text("""
                SELECT close, timestamp FROM stock_prices
                WHERE ticker = '^STOXX'
                ORDER BY timestamp DESC
                LIMIT 61
            """),
            {"ticker": ticker}
        ).fetchall()
        
        def get_returns_by_date(rows):
            rows_asc = list(reversed(rows))
            returns = {}
            for i in range(1, len(rows_asc)):
                prev_close = float(rows_asc[i-1][0])
                curr_close = float(rows_asc[i][0])
                date_str = rows_asc[i][1].strftime("%Y-%m-%d")
                if prev_close > 0:
                    returns[date_str] = (curr_close - prev_close) / prev_close
            return returns
            
        stock_returns = get_returns_by_date(stock_prices_60)
        market_returns = get_returns_by_date(market_prices_60)
        
        # Align returns
        common_dates = sorted(list(set(stock_returns.keys()) & set(market_returns.keys())))
        beta = 1.0
        if len(common_dates) >= 10:
            s_ret = [stock_returns[d] for d in common_dates]
            m_ret = [market_returns[d] for d in common_dates]
            
            mean_s = sum(s_ret) / len(s_ret)
            mean_m = sum(m_ret) / len(m_ret)
            
            covariance = sum((s - mean_s) * (m - mean_m) for s, m in zip(s_ret, m_ret))
            variance_m = sum((m - mean_m) ** 2 for m in m_ret)
            
            if variance_m > 0:
                beta = round(covariance / variance_m, 2)
                
        # 2. Fetch sentiment-return correlation (Pearson r)
        sent_rows = conn.execute(
            text("""
                SELECT a.published_date, a.sentiment_score
                FROM news_articles a
                JOIN news_company_mappings m ON a.id = m.article_id
                WHERE m.company_ticker = :ticker AND a.sentiment_score IS NOT NULL
            """),
            {"ticker": ticker}
        ).fetchall()
        
        sent_by_date = {}
        for row in sent_rows:
            date_str = row[0].strftime("%Y-%m-%d")
            score = float(row[1])
            if date_str not in sent_by_date:
                sent_by_date[date_str] = []
            sent_by_date[date_str].append(score)
            
        avg_sent_by_date = {d: sum(vals)/len(vals) for d, vals in sent_by_date.items()}
        
        trading_dates = sorted(list(stock_returns.keys()))
        x_sent = []
        y_ret = []
        for s_date, s_val in avg_sent_by_date.items():
            next_dates = [t_date for t_date in trading_dates if t_date > s_date]
            if next_dates:
                d_next = next_dates[0]
                x_sent.append(s_val)
                y_ret.append(stock_returns[d_next])
                
        correlation = None
        if len(x_sent) >= 3:
            mean_x = sum(x_sent) / len(x_sent)
            mean_y = sum(y_ret) / len(y_ret)
            num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x_sent, y_ret))
            den_x = sum((xi - mean_x) ** 2 for xi in x_sent)
            den_y = sum((yi - mean_y) ** 2 for yi in y_ret)
            if den_x > 0 and den_y > 0:
                correlation = round(num / ((den_x * den_y) ** 0.5), 3)
                
        v2tx_perf = get_index_performance("^V2TX")
        v2tx_price = v2tx_perf["price"] if v2tx_perf["price"] > 0.0 else 18.5
        
        if beta > 1.2:
            if v2tx_price >= 20.0:
                hedging_suggestion = f"Rischio sistemico elevato (Beta: {beta:.2f}, VSTOXX: {v2tx_price:.1f}). Si raccomanda una copertura aggressiva vendendo allo scoperto contratti futures sull'indice benchmark (^STOXX) pari al {int(beta * 100)}% del controvalore del portafoglio."
            else:
                hedging_suggestion = f"Sensibilità elevata al mercato (Beta: {beta:.2f}). Consigliata copertura parziale del {int(beta * 50)}% tramite short sull'indice benchmark (^STOXX) in vista di possibili aumenti di volatilità."
        elif beta >= 0.8:
            if v2tx_price >= 20.0:
                hedging_suggestion = f"Sensibilità neutrale (Beta: {beta:.2f}). In condizioni di volatilità elevata (VSTOXX: {v2tx_price:.1f}), coprire il 50% della posizione sull'indice di riferimento."
            else:
                hedging_suggestion = f"Profilo di rischio standard (Beta: {beta:.2f}). Nessuna azione di copertura immediata richiesta in contesti di mercato stabile."
        else:
            hedging_suggestion = f"Titolo difensivo (Beta: {beta:.2f}). Mostra bassa correlazione con le fluttuazioni dell'indice generale. Ideale come copertura naturale di portafoglio."
            
        # 3. Calculate MT5 parameters using 14-day ATR
        atr_prices = conn.execute(
            text("""
                SELECT high, low, close
                FROM stock_prices
                WHERE ticker = :ticker
                ORDER BY timestamp DESC
                LIMIT 15
            """),
            {"ticker": ticker}
        ).fetchall()
        
        atr = 0.0
        if len(atr_prices) >= 2:
            prices_asc = list(reversed(atr_prices))
            tr_list = []
            for i in range(1, len(prices_asc)):
                high = float(prices_asc[i][0]) if prices_asc[i][0] is not None else 0.0
                low = float(prices_asc[i][1]) if prices_asc[i][1] is not None else 0.0
                close = float(prices_asc[i][2]) if prices_asc[i][2] is not None else 0.0
                prev_close = float(prices_asc[i-1][2]) if prices_asc[i-1][2] is not None else close
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_list.append(tr)
            if tr_list:
                atr = sum(tr_list) / len(tr_list)
                
        mt5_symbol = ticker.split(".")[0].replace("=X", "").replace("^", "")
        sl = 0.0
        tp = 0.0
        
        if signal == "BUY":
            sl = max(0.0, round(latest_price - 1.5 * atr, 4)) if atr > 0 else round(latest_price * 0.98, 4)
            tp = max(0.0, round(latest_price + 3.0 * atr, 4)) if atr > 0 else round(latest_price * 1.04, 4)
        elif signal == "SELL":
            sl = max(0.0, round(latest_price + 1.5 * atr, 4)) if atr > 0 else round(latest_price * 1.02, 4)
            tp = max(0.0, round(latest_price - 3.0 * atr, 4)) if atr > 0 else round(latest_price * 0.96, 4)
            
        return StockDetailResponse(
            ticker=ticker,
            name=name,
            country=country,
            sector=sector,
            industry=industry,
            price=latest_price,
            price_change_24h=float(change_24h) if change_24h else 0.0,
            sentiment_score=float(sent_score) if sent_score else 0.0,
            signal=signal,
            reason_macro=reason_macro,
            reason_micro=reason_micro,
            reason_technical=reason_technical,
            history=history_list,
            beta=beta,
            correlation=correlation,
            hedging_suggestion=hedging_suggestion,
            mt5_symbol=mt5_symbol,
            stop_loss=sl,
            take_profit=tp
        )

@app.get("/api/news", response_model=List[NewsArticleSchema])
def get_news():
    query = text("""
        SELECT a.id, a.title, '' as content, a.url, a.source, a.published_date, a.country, a.sentiment_label, a.sentiment_score
        FROM news_articles a
        ORDER BY a.published_date DESC
        LIMIT 50
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query).fetchall()
        
        articles = []
        for r in result:
            art_id, title, content, url, source, pub_date, country, sent_lbl, sent_scr = r
            
            # Fetch mapped tickers for this article
            ticker_query = text("""
                SELECT company_ticker FROM news_company_mappings
                WHERE article_id = :article_id
            """)
            tickers = [row[0] for row in conn.execute(ticker_query, {"article_id": art_id}).fetchall()]
            
            articles.append(
                NewsArticleSchema(
                    id=art_id,
                    title=title,
                    content=content or "",
                    url=url,
                    source=source,
                    published_date=pub_date,
                    country=country,
                    sentiment_label=sent_lbl,
                    sentiment_score=float(sent_scr) if sent_scr is not None else None,
                    tickers=tickers
                )
            )
        return articles

@app.post("/api/trigger-job")
def trigger_job():
    """
    Inserts a job into the queue to trigger the scraping and calculation worker.
    """
    with engine.connect() as conn:
        # Create queue table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS job_queue (
                id SERIAL PRIMARY KEY,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        conn.commit()
        
        # Insert pending job
        conn.execute(text("INSERT INTO job_queue (status) VALUES ('pending')"))
        conn.commit()
        
    return {"message": "Job successfully queued. Worker will execute immediately."}

class BacktestRequest(BaseModel):
    ticker: str
    buy_rsi: float = 30.0
    sell_rsi: float = 70.0
    buy_sentiment: float = 0.1
    sell_sentiment: float = -0.1

class BacktestResponse(BaseModel):
    total_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    equity_curve: List[dict]

@app.post("/api/backtest", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest):
    with engine.connect() as conn:
        prices = conn.execute(
            text("""
                SELECT timestamp, close, rsi
                FROM stock_prices
                WHERE ticker = :ticker
                ORDER BY timestamp ASC
                LIMIT 250
            """),
            {"ticker": req.ticker}
        ).fetchall()
        
        if not prices:
            raise HTTPException(status_code=404, detail="No price data available for backtest")
            
        sent_rows = conn.execute(
            text("""
                SELECT a.published_date, a.sentiment_score
                FROM news_articles a
                JOIN news_company_mappings m ON a.id = m.article_id
                WHERE m.company_ticker = :ticker AND a.sentiment_score IS NOT NULL
            """),
            {"ticker": req.ticker}
        ).fetchall()
        
        sent_by_date = {}
        for r in sent_rows:
            d_str = r[0].strftime("%Y-%m-%d")
            score = float(r[1])
            if d_str not in sent_by_date:
                sent_by_date[d_str] = []
            sent_by_date[d_str].append(score)
        avg_sent_by_date = {d: sum(vals)/len(vals) for d, vals in sent_by_date.items()}
        
        cash = 10000.0
        position = 0.0
        peak_equity = 10000.0
        max_drawdown = 0.0
        trades = 0
        winning_trades = 0
        entry_price = 0.0
        
        equity_curve = []
        initial_close = float(prices[0][1]) if prices[0][1] else 1.0
        final_close = float(prices[-1][1]) if prices[-1][1] else 1.0
        
        for p in prices:
            ts, close, rsi = p
            close_val = float(close) if close else 0.0
            rsi_val = float(rsi) if rsi else 50.0
            d_str = ts.strftime("%Y-%m-%d")
            sentiment_val = avg_sent_by_date.get(d_str, 0.0)
            
            if close_val <= 0.0:
                continue
                
            if position == 0.0:
                if rsi_val <= req.buy_rsi or sentiment_val >= req.buy_sentiment:
                    position = cash / close_val
                    cash = 0.0
                    entry_price = close_val
            elif position > 0.0:
                if rsi_val >= req.sell_rsi or sentiment_val <= req.sell_sentiment:
                    cash = position * close_val
                    position = 0.0
                    exit_price = close_val
                    trades += 1
                    if exit_price > entry_price:
                        winning_trades += 1
                        
            current_equity = cash + (position * close_val)
            equity_curve.append({
                "date": d_str,
                "equity": round(current_equity, 2)
            })
            
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = ((peak_equity - current_equity) / peak_equity) * 100.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        if position > 0.0:
            cash = position * final_close
            position = 0.0
            trades += 1
            if final_close > entry_price:
                winning_trades += 1
            current_equity = cash
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = ((peak_equity - current_equity) / peak_equity) * 100.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            if len(equity_curve) > 0:
                equity_curve[-1]["equity"] = round(current_equity, 2)
                
        total_return = ((current_equity - 10000.0) / 10000.0) * 100.0
        benchmark_return = ((final_close - initial_close) / initial_close) * 100.0
        win_rate = (winning_trades / trades * 100.0) if trades > 0 else 0.0
        
        sharpe_ratio = 0.0
        if len(equity_curve) >= 5:
            daily_returns = []
            for i in range(1, len(equity_curve)):
                prev = equity_curve[i-1]["equity"]
                curr = equity_curve[i]["equity"]
                if prev > 0:
                    daily_returns.append((curr - prev) / prev)
            if daily_returns:
                mean_ret = sum(daily_returns) / len(daily_returns)
                variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
                std_ret = variance ** 0.5
                if std_ret > 0:
                    sharpe_ratio = round((mean_ret / std_ret) * (252 ** 0.5), 2)
                    
        return BacktestResponse(
            total_return=round(total_return, 2),
            benchmark_return=round(benchmark_return, 2),
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=sharpe_ratio,
            win_rate=round(win_rate, 2),
            equity_curve=equity_curve
        )

from fastapi.responses import StreamingResponse
import asyncio
import json
import random

@app.get("/api/events")
async def get_events():
    async def event_generator():
        baselines = {
            "EURUSD=X": {"name": "EUR/USD", "price": 1.1528, "change_pct": 0.04},
            "GBPUSD=X": {"name": "GBP/USD", "price": 1.3333, "change_pct": -0.02},
            "EURGBP=X": {"name": "EUR/GBP", "price": 0.8645, "change_pct": 0.06},
            "EURJPY=X": {"name": "EUR/JPY", "price": 184.65, "change_pct": -0.04},
            "EURCHF=X": {"name": "EUR/CHF", "price": 0.9201, "change_pct": 0.26}
        }
        
        try:
            with engine.connect() as conn:
                res = conn.execute(text("""
                    SELECT ticker, price, change_pct, name
                    FROM (
                        SELECT ticker, close as price, change_pct, name,
                               ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
                        FROM stock_prices
                        WHERE sector = 'Forex'
                    ) tmp WHERE rn = 1
                """)).fetchall()
                for r in res:
                    ticker, price, change, name = r
                    if price:
                        baselines[ticker] = {
                            "name": name or ticker,
                            "price": float(price),
                            "change_pct": float(change) if change else 0.0
                        }
        except Exception:
            pass

        while True:
            forex_updates = []
            for ticker, data in baselines.items():
                tick = 1.0 + random.uniform(-0.0002, 0.0002)
                data["price"] = round(data["price"] * tick, 4)
                data["change_pct"] = round(data["change_pct"] + random.uniform(-0.01, 0.01), 2)
                forex_updates.append({
                    "ticker": ticker,
                    "name": data["name"],
                    "price": data["price"],
                    "change_pct": data["change_pct"]
                })
            
            yield f"data: {json.dumps({'forex': forex_updates})}\n\n"
            await asyncio.sleep(5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

class MT5Signal(BaseModel):
    ticker: str
    mt5_symbol: str
    action: str
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    timestamp: str

@app.get("/api/mt5/signals")
def get_mt5_signals(request: Request, ticker: Optional[str] = None):
    # Log ping
    client_ip = request.headers.get("x-forwarded-for")
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"
    else:
        client_ip = client_ip.split(",")[0].strip()
        
    mt5_clients[client_ip] = {
        "ip": client_ip,
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker or "ALL (Multi-Symbol)"
    }
    with engine.connect() as conn:
        # Fetch active symbols, matching either the exact ticker (e.g., EURUSD=X) or the cleaned MT5 symbol (e.g., EURUSD)
        if ticker:
            rows = conn.execute(
                text("""
                    SELECT r.ticker, r.signal, r.reason_technical, p.close, r.timestamp
                    FROM recommendations r
                    JOIN (
                        SELECT ticker, close, ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
                        FROM stock_prices
                    ) p ON r.ticker = p.ticker AND p.rn = 1
                    WHERE r.ticker = :ticker OR 
                          REPLACE(REPLACE(REPLACE(split_part(r.ticker, '.', 1), '=X', ''), '^', ''), ' ', '') = :ticker
                    ORDER BY r.timestamp DESC
                    LIMIT 1
                """),
                {"ticker": ticker}
            ).fetchall()
        else:
            rows = conn.execute(
                text("""
                    SELECT r.ticker, r.signal, r.reason_technical, p.close, r.timestamp
                    FROM recommendations r
                    JOIN (
                        SELECT ticker, close, ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
                        FROM stock_prices
                    ) p ON r.ticker = p.ticker AND p.rn = 1
                    ORDER BY r.timestamp DESC
                """)
            ).fetchall()

        signals = []
        for r_ticker, r_signal, r_reason, r_price, r_gen in rows:
            # Check for manual overrides
            active_signal = r_signal
            active_reason = r_reason
            
            clean_ticker = r_ticker.split(".")[0].replace("=X", "").replace("^", "")
            override_key = None
            if r_ticker in manual_overrides:
                override_key = r_ticker
            elif clean_ticker in manual_overrides:
                override_key = clean_ticker
            else:
                for k in manual_overrides.keys():
                    if k.split(".")[0].replace("=X", "").replace("^", "") == clean_ticker:
                        override_key = k
                        break
            
            if override_key:
                active_signal = manual_overrides[override_key]["action"]
                active_reason = f"OVERRIDE MANUALE DALLA DASHBOARD WEB ({manual_overrides[override_key]['timestamp']})"

            # Calculate ATR for SL/TP
            atr_prices = conn.execute(
                text("""
                    SELECT high, low, close
                    FROM stock_prices
                    WHERE ticker = :ticker
                    ORDER BY timestamp DESC
                    LIMIT 15
                """),
                {"ticker": r_ticker}
            ).fetchall()
            
            atr = 0.0
            if len(atr_prices) >= 2:
                prices_asc = list(reversed(atr_prices))
                tr_list = []
                for i in range(1, len(prices_asc)):
                    high = float(prices_asc[i][0]) if prices_asc[i][0] is not None else 0.0
                    low = float(prices_asc[i][1]) if prices_asc[i][1] is not None else 0.0
                    close = float(prices_asc[i][2]) if prices_asc[i][2] is not None else 0.0
                    prev_close = float(prices_asc[i-1][2]) if prices_asc[i-1][2] is not None else close
                    tr = max(
                        high - low,
                        abs(high - prev_close),
                        abs(low - prev_close)
                    )
                    tr_list.append(tr)
                if tr_list:
                    atr = sum(tr_list) / len(tr_list)
            
            latest_price = float(r_price)
            mt5_symbol = r_ticker.split(".")[0].replace("=X", "").replace("^", "")
            
            sl = 0.0
            tp = 0.0
            if active_signal == "BUY":
                sl = max(0.0, round(latest_price - 1.5 * atr, 4)) if atr > 0 else round(latest_price * 0.98, 4)
                tp = max(0.0, round(latest_price + 3.0 * atr, 4)) if atr > 0 else round(latest_price * 1.04, 4)
            elif active_signal == "SELL":
                sl = max(0.0, round(latest_price + 1.5 * atr, 4)) if atr > 0 else round(latest_price * 1.02, 4)
                tp = max(0.0, round(latest_price - 3.0 * atr, 4)) if atr > 0 else round(latest_price * 0.96, 4)
                
            signals.append(MT5Signal(
                ticker=r_ticker,
                mt5_symbol=mt5_symbol,
                action=active_signal,
                entry_price=latest_price,
                stop_loss=sl,
                take_profit=tp,
                reason=active_reason or "Nessun dettaglio aggiuntivo.",
                timestamp=r_gen.strftime("%Y-%m-%d %H:%M:%S") + " Z" if r_gen else ""
            ))
            
        if ticker:
            if not signals:
                raise HTTPException(status_code=404, detail="Ticker non trovato o nessun segnale generato.")
            return signals[0]
        return signals

@app.get("/api/mt5/clients")
def get_mt5_clients():
    now = datetime.now(timezone.utc)
    active_clients = []
    for ip, data in list(mt5_clients.items()):
        try:
            last_seen = datetime.fromisoformat(data["last_seen"])
            age = (now - last_seen).total_seconds()
            if age < 300: # 5 minutes
                active_clients.append(data)
            else:
                mt5_clients.pop(ip, None)
        except Exception:
            active_clients.append(data)
    return active_clients

@app.get("/api/forex/screener", response_model=List[ScreenerRow])
def get_forex_screener():
    query = text("""
        SELECT c.ticker, c.name, c.country, c.sector,
               r.signal, r.sentiment_score, r.price_change_24h, r.timestamp,
               (SELECT close FROM stock_prices p WHERE p.ticker = c.ticker ORDER BY p.timestamp DESC LIMIT 1) as latest_close
        FROM companies c
        JOIN recommendations r ON c.ticker = r.ticker
        WHERE c.sector = 'Forex'
        ORDER BY c.ticker ASC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query).fetchall()
        
    rows = []
    for r in result:
        ticker, name, country, sector, signal, sent_score, change_24h, ts, price = r
        rows.append(
            ScreenerRow(
                ticker=ticker,
                name=name,
                country=country,
                sector=sector,
                price=float(price) if price else 0.0,
                price_change_24h=float(change_24h) if change_24h else 0.0,
                sentiment_score=float(sent_score) if sent_score else 0.0,
                signal=signal,
                timestamp=ts
            )
        )
    return rows

@app.get("/api/mt5/overrides")
def get_overrides():
    return manual_overrides

@app.post("/api/mt5/overrides")
def set_override(payload: OverridePayload):
    ticker = payload.ticker
    action = payload.action
    if action == "CLEAR":
        manual_overrides.pop(ticker, None)
    else:
        manual_overrides[ticker] = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    return {"status": "success", "overrides": manual_overrides}

@app.get("/api/recommendations/history", response_model=List[SignalHistoryItem])
def get_recommendations_history(ticker: str):
    query = text("""
        SELECT signal, sentiment_score, price_change_24h, reason_technical, timestamp
        FROM recommendation_history
        WHERE ticker = :ticker
        ORDER BY timestamp DESC
        LIMIT 15
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"ticker": ticker}).fetchall()
    
    history = []
    for r in result:
        sig, sent, chg, tech, ts = r
        history.append(
            SignalHistoryItem(
                signal=sig,
                sentiment_score=float(sent) if sent is not None else 0.0,
                price_change_24h=float(chg) if chg is not None else 0.0,
                reason_technical=tech or "",
                timestamp=ts.isoformat() if ts else ""
            )
        )
    return history
