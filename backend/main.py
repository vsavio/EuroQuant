from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sys
import json

class StdoutJsonLogger:
    def __init__(self, original_stream, level="INFO"):
        self.original_stream = original_stream
        self.level = level

    def write(self, message):
        stripped = message.strip()
        if stripped:
            log_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": self.level,
                "message": stripped
            }
            self.original_stream.write(json.dumps(log_data) + "\n")
            self.original_stream.flush()

    def flush(self):
        self.original_stream.flush()

sys.stdout = StdoutJsonLogger(sys.stdout, "INFO")
sys.stderr = StdoutJsonLogger(sys.stderr, "ERROR")
import yfinance as yf
from sqlalchemy import create_engine, text
import os
import json
import asyncio
import math
from cachetools import TTLCache
from auth import router as auth_router, get_current_user, require_admin, write_audit_log

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="EuroQuant institutional API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)

@app.get("/api/health", tags=["system"])
def health_check():
    """Lightweight health check for Docker and load balancers."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok", "db": "connected"})
    except Exception:
        return JSONResponse({"status": "degraded", "db": "disconnected"}, status_code=503)

# ─── In-Memory TTL Caches ───────────────────────────────────────────────────
# Prevent repeated identical DB queries from concurrent clients.
# TTL values are conservative — data freshness is more important than cache hits.
_cache_market_summary = TTLCache(maxsize=1, ttl=30)     # 30s — market overview
_cache_screener = TTLCache(maxsize=64, ttl=60)           # 60s — per-filter screener
_cache_forex = TTLCache(maxsize=1, ttl=30)               # 30s — forex screener
_cache_correlation = TTLCache(maxsize=8, ttl=300)        # 5min — correlation matrices
_cache_risk_analytics = TTLCache(maxsize=1, ttl=120)     # 2min — risk analytics

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


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

# Initialize table(s) if not exists
try:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                telegram_bot_token VARCHAR(255) DEFAULT '',
                telegram_chat_id VARCHAR(50) DEFAULT '',
                discord_webhook_url TEXT DEFAULT '',
                CONSTRAINT single_row CHECK (id = 1)
            )
        """))
        conn.execute(text("""
            INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS broker_accounts (
                account_id VARCHAR(50) PRIMARY KEY,
                broker VARCHAR(100),
                balance NUMERIC(15, 2),
                equity NUMERIC(15, 2),
                margin NUMERIC(15, 2),
                margin_free NUMERIC(15, 2),
                margin_level NUMERIC(15, 2),
                profit NUMERIC(15, 2),
                last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                max_drawdown_percent NUMERIC(5, 2) DEFAULT 5.0
            )
        """))
        conn.execute(text("""
            ALTER TABLE broker_accounts ADD COLUMN IF NOT EXISTS max_drawdown_percent NUMERIC(5, 2) DEFAULT 5.0;
        """))
        conn.execute(text("""
            ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS parent_article_id INTEGER;
        """))
        conn.execute(text("""
            ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS ml_prediction_prob NUMERIC(5, 4) DEFAULT 0.50;
        """))
        
        # Create users table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'Trader',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Seed default admin user (admin / admin123) if no users exist
        user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if user_count == 0:
            from auth import get_password_hash
            admin_hash = get_password_hash("admin123")
            conn.execute(
                text("INSERT INTO users (username, hashed_password, role) VALUES ('admin', :hash, 'Admin')"),
                {"hash": admin_hash}
            )
            
        # Create orders table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(50) PRIMARY KEY,
                account_id VARCHAR(50) NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                action VARCHAR(10) NOT NULL,
                status VARCHAR(20) NOT NULL,
                requested_price NUMERIC(15, 4),
                executed_price NUMERIC(15, 4),
                slippage NUMERIC(15, 4) DEFAULT 0.0,
                commission NUMERIC(15, 4) DEFAULT 0.0,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create ml_model_metrics table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_model_metrics (
                ticker VARCHAR(20) PRIMARY KEY,
                last_trained TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                accuracy NUMERIC(5, 4),
                precision NUMERIC(5, 4),
                recall NUMERIC(5, 4),
                f1_score NUMERIC(5, 4),
                total_samples INTEGER,
                features_used JSONB DEFAULT '[]'
            )
        """))
        
        # Removed native partitioning logic since TimescaleDB hypertables handle this automatically
        
        # Performance indexes — safe to run multiple times (IF NOT EXISTS)
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker_ts
            ON stock_prices (ticker, timestamp DESC)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_news_articles_published
            ON news_articles (published_date DESC)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_recommendations_signal
            ON recommendations (signal)
        """))
        conn.commit()

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error initializing database schema/partitioning: {e}")

# Global tracker for MT5 clients and manual overrides
mt5_clients = {}
manual_overrides = {}

# Centralized Risk Parameters
max_drawdown_percent = 5.0
emergency_kill_switch = False
last_risk_state = False
last_risk_reason = ""

class RiskSettingsPayload(BaseModel):
    max_drawdown_percent: float

class AccountRiskPayload(BaseModel):
    max_drawdown_percent: float

class KillSwitchPayload(BaseModel):
    active: bool

class OverridePayload(BaseModel):
    ticker: str
    action: str

class TickerTogglePayload(BaseModel):
    ticker: str
    is_active: bool

class TickerAddPayload(BaseModel):
    ticker: str
    name: str
    country: str
    sector: str
    industry: str

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

class MetalsSummary(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float

class CryptoSummary(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float

class MarketSummaryResponse(BaseModel):
    indices: List[IndexSummary]
    v2tx: VolatilitySummary
    forex: List[ForexSummary]
    metals: List[MetalsSummary]
    crypto: List[CryptoSummary]
    global_circuit_breaker: bool

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
    ml_prediction_prob: float = 0.50

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
    ml_prediction_prob: float = 0.50
    kelly_factor: Optional[float] = None
    chandelier_exit_distance: Optional[float] = None

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
                WHERE ticker = :ticker AND close IS NOT NULL
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
    # Check cache first
    cached = _cache_market_summary.get("market_summary")
    if cached is not None:
        return cached

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
        
    metals_tickers = {
        "GC=F": "Gold (XAU)",
        "SI=F": "Silver (XAG)"
    }
    
    metals_list = []
    for ticker, name in metals_tickers.items():
        perf = get_index_performance(ticker)
        metals_list.append(
            MetalsSummary(
                ticker=ticker,
                name=name,
                price=round(perf["price"], 2),
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
        
    # Check global circuit breaker
    circuit_breaker_active = False
    with engine.connect() as conn:
        try:
            settings_row = conn.execute(text("SELECT trading_halted FROM system_settings WHERE id = 1")).fetchone()
            if settings_row and settings_row[0]:
                circuit_breaker_active = True
        except Exception:
            pass
            
    crypto_tickers = {
        "BTCUSD": "Bitcoin",
        "ETHUSD": "Ethereum",
        "XRPUSD": "Ripple",
        "SOLUSD": "Solana",
        "ADAUSD": "Cardano"
    }
    
    crypto_list = []
    for ticker, name in crypto_tickers.items():
        perf = get_index_performance(ticker)
        crypto_list.append(
            CryptoSummary(
                ticker=ticker,
                name=name,
                price=round(perf["price"], 2),
                change_pct=round(perf["change_pct"], 2)
            )
        )
            
    result = MarketSummaryResponse(
        indices=indices_list,
        v2tx=VolatilitySummary(
            price=round(v2tx_price, 2) if v2tx_price > 0.0 else 18.50,
            status=status,
            message=message
        ),
        forex=forex_list,
        metals=metals_list,
        crypto=crypto_list,
        global_circuit_breaker=circuit_breaker_active
    )
    _cache_market_summary["market_summary"] = result
    return result

@app.get("/api/tickers")
def get_tickers():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT ticker, name, country, sector, industry, is_active FROM companies ORDER BY is_active DESC, ticker ASC")).fetchall()
        return [
            {
                "ticker": r[0],
                "name": r[1],
                "country": r[2],
                "sector": r[3],
                "industry": r[4],
                "is_active": r[5]
            } for r in rows
        ]

@app.post("/api/tickers/toggle")
def toggle_ticker(payload: TickerTogglePayload):
    with engine.connect() as conn:
        conn.execute(text("UPDATE companies SET is_active = :is_active WHERE ticker = :ticker"), 
                     {"is_active": payload.is_active, "ticker": payload.ticker})
        conn.commit()
    return {"status": "success"}

@app.post("/api/tickers/add")
def add_ticker(payload: TickerAddPayload):
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT ticker FROM companies WHERE ticker = :ticker"), {"ticker": payload.ticker}).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Ticker già esistente")
        conn.execute(text("""
            INSERT INTO companies (ticker, name, country, sector, industry, trust_score, is_active)
            VALUES (:ticker, :name, :country, :sector, :industry, 0.60, TRUE)
        """), {
            "ticker": payload.ticker,
            "name": payload.name,
            "country": payload.country,
            "sector": payload.sector,
            "industry": payload.industry
        })
        conn.commit()
    return {"status": "success"}

@app.get("/api/screener", response_model=List[ScreenerRow])
def get_screener():
    # Check cache
    cached = _cache_screener.get("screener_all")
    if cached is not None:
        return cached

    query = text("""
        SELECT c.ticker, c.name, c.country, c.sector,
               r.signal, r.sentiment_score, r.price_change_24h, r.timestamp,
               (SELECT close FROM stock_prices p WHERE p.ticker = c.ticker AND p.close IS NOT NULL ORDER BY p.timestamp DESC LIMIT 1) as latest_close,
               r.ml_prediction_prob
        FROM companies c
        JOIN recommendations r ON c.ticker = r.ticker
        WHERE c.sector NOT IN ('Index', 'Forex')
        ORDER BY r.sentiment_score DESC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query).fetchall()
        
    rows = []
    for r in result:
        ticker, name, country, sector, signal, sent_score, change_24h, ts, price, ml_prob = r
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
                timestamp=ts,
                ml_prediction_prob=float(ml_prob) if ml_prob is not None else 0.50
            )
        )
    _cache_screener["screener_all"] = rows
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
                SELECT signal, sentiment_score, price_change_24h, reason_macro, reason_micro, reason_technical, ml_prediction_prob
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
        ml_prob = 0.50
        
        if rec:
            signal, sent_score, change_24h, reason_macro, reason_micro, reason_technical, ml_prob_val = rec
            ml_prob = float(ml_prob_val) if ml_prob_val is not None else 0.50
            
        # Fetch price history (last 100 rows for rich charts)
        prices = conn.execute(
            text("""
                SELECT timestamp, open, high, low, close, volume, rsi, macd, macd_signal, sma_20, sma_50, sma_200
                FROM stock_prices
                WHERE ticker = :ticker AND close IS NOT NULL
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
                WHERE ticker = :ticker AND close IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 61
            """),
            {"ticker": ticker}
        ).fetchall()
        
        market_prices_60 = conn.execute(
            text("""
                SELECT close, timestamp FROM stock_prices
                WHERE ticker = '^STOXX' AND close IS NOT NULL
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
                WHERE ticker = :ticker AND close IS NOT NULL
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
            
        # Calculate Kelly Factor specifically for the detail view
        kelly_factor = None
        chandelier_exit_distance = atr * 2.5 if atr > 0 else 0.0
        try:
            metrics_row = conn.execute(
                text("SELECT accuracy FROM ml_model_metrics WHERE ticker = :ticker"),
                {"ticker": ticker}
            ).fetchone()
            if metrics_row and metrics_row[0] is not None:
                p = max(0.01, min(0.99, float(metrics_row[0])))
                b = 2.0  # Reward/Risk Ratio
                kelly_val = p - (1.0 - p) / b
                kelly_factor = max(0.05, min(1.0, kelly_val))
        except Exception:
            pass
            
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
            take_profit=tp,
            ml_prediction_prob=ml_prob,
            kelly_factor=kelly_factor,
            chandelier_exit_distance=chandelier_exit_distance
        )

@app.get("/api/news", response_model=List[NewsArticleSchema])
def get_news():
    query = text("""
        SELECT a.id, a.title, '' as content, a.url, a.source, a.published_date, a.country, a.sentiment_label, a.sentiment_score
        FROM news_articles a
        WHERE a.parent_article_id IS NULL
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
def trigger_job(request: Request, current_user: dict = Depends(require_admin)):
    """
    Admin only: Inserts a job into the queue to trigger the scraping and calculation worker.
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

    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "trigger_job", {"queued": True}, ip)
    return {"message": "Job successfully queued. Worker will execute immediately."}

class BacktestRequest(BaseModel):
    ticker: str
    buy_rsi: float = 30.0
    sell_rsi: float = 70.0
    buy_sentiment: float = 0.1
    sell_sentiment: float = -0.1
    initial_capital: float = 10000.0  # Configurable starting capital

class BacktestResponse(BaseModel):
    total_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    equity_curve: List[dict]

@app.post("/api/backtest", response_model=BacktestResponse)
@limiter.limit("10/minute")
def run_backtest(request: Request, req: BacktestRequest):
    with engine.connect() as conn:
        prices = conn.execute(
            text("""
                SELECT timestamp, close, rsi
                FROM stock_prices
                WHERE ticker = :ticker AND close IS NOT NULL
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
        
        initial_capital = max(100.0, min(req.initial_capital, 10_000_000.0))  # clamp between €100-€10M
        cash = initial_capital
        position = 0.0
        peak_equity = initial_capital
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
                    # Incorporate slippage (entry price is slightly higher) & commission (0.1%)
                    executed_buy_price = close_val * 1.0005
                    commission_cost = cash * 0.001
                    position = (cash - commission_cost) / executed_buy_price
                    cash = 0.0
                    entry_price = executed_buy_price
            elif position > 0.0:
                if rsi_val >= req.sell_rsi or sentiment_val <= req.sell_sentiment:
                    # Incorporate slippage (exit price is slightly lower) & commission (0.1%)
                    executed_sell_price = close_val * 0.9995
                    gross_cash = position * executed_sell_price
                    commission_cost = gross_cash * 0.001
                    cash = gross_cash - commission_cost
                    position = 0.0
                    exit_price = executed_sell_price
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
            executed_sell_price = final_close * 0.9995
            gross_cash = position * executed_sell_price
            commission_cost = gross_cash * 0.001
            cash = gross_cash - commission_cost
            position = 0.0
            trades += 1
            if executed_sell_price > entry_price:
                winning_trades += 1
            current_equity = cash
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = ((peak_equity - current_equity) / peak_equity) * 100.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            if len(equity_curve) > 0:
                equity_curve[-1]["equity"] = round(current_equity, 2)
                
        total_return = ((current_equity - initial_capital) / initial_capital) * 100.0
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

class BacktestOptimizeRequest(BaseModel):
    ticker: str

class OptimizationItem(BaseModel):
    buy_rsi: float
    sell_rsi: float
    buy_sentiment: float
    sell_sentiment: float
    total_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float

class BacktestOptimizeResponse(BaseModel):
    ticker: str
    top_configs: List[OptimizationItem]

@app.post("/api/backtest/optimize", response_model=BacktestOptimizeResponse)
@limiter.limit("3/minute")
def run_backtest_optimize(request: Request, req: BacktestOptimizeRequest):
    with engine.connect() as conn:
        prices = conn.execute(
            text("""
                SELECT timestamp, close, rsi
                FROM stock_prices
                WHERE ticker = :ticker AND close IS NOT NULL
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
        
        initial_close = float(prices[0][1]) if prices[0][1] else 1.0
        final_close = float(prices[-1][1]) if prices[-1][1] else 1.0
        benchmark_return = ((final_close - initial_close) / initial_close) * 100.0
        
        # Grid parameters
        buy_rsi_vals = [20.0, 25.0, 30.0, 35.0]
        sell_rsi_vals = [65.0, 70.0, 75.0, 80.0]
        buy_sent_vals = [0.05, 0.1, 0.2, 0.3]
        sell_sent_vals = [-0.05, -0.1, -0.2, -0.3]
        
        results = []
        
        for buy_rsi in buy_rsi_vals:
            for sell_rsi in sell_rsi_vals:
                for buy_sent in buy_sent_vals:
                    for sell_sent in sell_sent_vals:
                        # Run backtest simulation in-memory
                        cash = 10000.0
                        position = 0.0
                        peak_equity = 10000.0
                        max_drawdown = 0.0
                        trades = 0
                        winning_trades = 0
                        entry_price = 0.0
                        
                        equity_curve = []
                        
                        for p in prices:
                            ts, close, rsi = p
                            close_val = float(close) if close else 0.0
                            rsi_val = float(rsi) if rsi else 50.0
                            d_str = ts.strftime("%Y-%m-%d")
                            sentiment_val = avg_sent_by_date.get(d_str, 0.0)
                            
                            if close_val <= 0.0:
                                continue
                                
                            if position == 0.0:
                                if rsi_val <= buy_rsi or sentiment_val >= buy_sent:
                                    position = cash / close_val
                                    cash = 0.0
                                    entry_price = close_val
                            elif position > 0.0:
                                if rsi_val >= sell_rsi or sentiment_val <= sell_sent:
                                    cash = position * close_val
                                    position = 0.0
                                    exit_price = close_val
                                    trades += 1
                                    if exit_price > entry_price:
                                        winning_trades += 1
                                        
                            current_equity = cash + (position * close_val)
                            equity_curve.append(current_equity)
                            
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
                            if equity_curve:
                                equity_curve[-1] = current_equity
                                
                        total_return = ((current_equity - 10000.0) / 10000.0) * 100.0
                        win_rate = (winning_trades / trades * 100.0) if trades > 0 else 0.0
                        
                        # Sharpe
                        sharpe_ratio = 0.0
                        if len(equity_curve) >= 5:
                            daily_returns = []
                            for i in range(1, len(equity_curve)):
                                prev = equity_curve[i-1]
                                curr = equity_curve[i]
                                if prev > 0:
                                    daily_returns.append((curr - prev) / prev)
                            if daily_returns:
                                mean_ret = sum(daily_returns) / len(daily_returns)
                                variance = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)
                                std_ret = variance ** 0.5
                                if std_ret > 0:
                                    sharpe_ratio = round((mean_ret / std_ret) * (252 ** 0.5), 2)
                                    
                        results.append(OptimizationItem(
                            buy_rsi=buy_rsi,
                            sell_rsi=sell_rsi,
                            buy_sentiment=buy_sentiment,
                            sell_sentiment=sell_sentiment,
                            total_return=round(total_return, 2),
                            benchmark_return=round(benchmark_return, 2),
                            max_drawdown=round(max_drawdown, 2),
                            sharpe_ratio=sharpe_ratio,
                            win_rate=round(win_rate, 2)
                        ))
                        
        # Sort by sharpe_ratio descending, then total_return descending
        results.sort(key=lambda x: (x.sharpe_ratio, x.total_return), reverse=True)
        
        return BacktestOptimizeResponse(
            ticker=req.ticker,
            top_configs=results[:3]
        )

from fastapi.responses import StreamingResponse
import asyncio
import json

# Forex tickers reference map
FOREX_TICKERS = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "EURGBP=X": "EUR/GBP",
    "EURJPY=X": "EUR/JPY",
    "EURCHF=X": "EUR/CHF",
}

@app.get("/api/events")
async def get_events():
    """SSE stream with real forex prices from DB, refreshed every 10 seconds."""
    async def event_generator():
        while True:
            try:
                forex_updates = []
                with engine.connect() as conn:
                    for fx_ticker, fx_name in FOREX_TICKERS.items():
                        row = conn.execute(text("""
                            SELECT sp1.close, sp2.close
                            FROM (
                                SELECT close FROM stock_prices
                                WHERE ticker = :ticker AND close IS NOT NULL
                                ORDER BY timestamp DESC LIMIT 1
                            ) sp1,
                            (
                                SELECT close FROM stock_prices
                                WHERE ticker = :ticker AND close IS NOT NULL
                                ORDER BY timestamp DESC LIMIT 1 OFFSET 1
                            ) sp2
                        """), {"ticker": fx_ticker}).fetchone()

                        if row and row[0]:
                            latest = float(row[0])
                            prev = float(row[1]) if row[1] else latest
                            change_pct = round(((latest - prev) / prev) * 100.0, 4) if prev else 0.0
                            forex_updates.append({
                                "ticker": fx_ticker,
                                "name": fx_name,
                                "price": round(latest, 5),
                                "change_pct": change_pct
                            })

                if forex_updates:
                    yield f"data: {json.dumps({'forex': forex_updates})}\n\n"
            except Exception as e:
                print(f"SSE events error: {e}")

            await asyncio.sleep(10)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

class MT5Signal(BaseModel):
    ticker: str
    mt5_symbol: str
    action: str
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    timestamp: str
    adx: Optional[float] = None
    atr: Optional[float] = None
    volatility_lot_sizing: Optional[float] = 1.0
    kelly_factor: Optional[float] = 1.0

class PositionItem(BaseModel):
    ticker: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float

class PositionsPayload(BaseModel):
    positions: List[PositionItem]

class ExecutionLogPayload(BaseModel):
    ticker: str
    action: str
    quantity: float
    fill_price: float
    slippage: float = 0.0
    broker: str = "MT5"
    regime: Optional[str] = "REGIME_MEAN_REVERTING"
    chandelier_exit_distance: Optional[float] = 0.0

@app.get("/api/mt5/signals")
async def get_mt5_signals(
    request: Request, 
    ticker: Optional[str] = None,
    balance: Optional[float] = None,
    equity: Optional[float] = None,
    margin: Optional[float] = None,
    margin_free: Optional[float] = None,
    margin_level: Optional[float] = None,
    profit: Optional[float] = None,
    account: Optional[str] = None,
    broker: Optional[str] = None
):
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
    
    if account:
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO broker_accounts (account_id, broker, balance, equity, margin, margin_free, margin_level, profit, last_seen)
                    VALUES (:account_id, :broker, :balance, :equity, :margin, :margin_free, :margin_level, :profit, NOW())
                    ON CONFLICT (account_id) DO UPDATE SET
                        broker = EXCLUDED.broker,
                        balance = EXCLUDED.balance,
                        equity = EXCLUDED.equity,
                        margin = EXCLUDED.margin,
                        margin_free = EXCLUDED.margin_free,
                        margin_level = EXCLUDED.margin_level,
                        profit = EXCLUDED.profit,
                        last_seen = NOW()
                """), {
                    "account_id": account,
                    "broker": broker,
                    "balance": balance,
                    "equity": equity,
                    "margin": margin,
                    "margin_free": margin_free,
                    "margin_level": margin_level,
                    "profit": profit
                })
                conn.commit()
            await manager.broadcast({"type": "telemetry_update"})
        except Exception as e:
            print(f"Error syncing broker account telemetry: {e}")

            
    with engine.connect() as conn:
        # Fetch active symbols, matching either the exact ticker (e.g., EURUSD=X) or the cleaned MT5 symbol (e.g., EURUSD)
        if ticker:
            rows = conn.execute(
                text("""
                    SELECT r.ticker, r.signal, r.reason_technical, p.close, r.timestamp, r.adx, r.atr, r.volatility_lot_sizing
                    FROM recommendations r
                    JOIN (
                        SELECT ticker, close, ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
                        FROM stock_prices
                        WHERE close IS NOT NULL
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
                    SELECT r.ticker, r.signal, r.reason_technical, p.close, r.timestamp, r.adx, r.atr, r.volatility_lot_sizing
                    FROM recommendations r
                    JOIN (
                        SELECT ticker, close, ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY timestamp DESC) as rn
                        FROM stock_prices
                        WHERE close IS NOT NULL
                    ) p ON r.ticker = p.ticker AND p.rn = 1
                    ORDER BY r.timestamp DESC
                """)
            ).fetchall()

        # Check drawdown and emergency kill switch
        acc_stats = conn.execute(text("SELECT SUM(balance), SUM(equity) FROM broker_accounts")).fetchone()
        current_drawdown_pct = 0.0
        if acc_stats and acc_stats[0] and float(acc_stats[0]) > 0:
            total_bal = float(acc_stats[0])
            total_eq = float(acc_stats[1])
            if total_bal > total_eq:
                current_drawdown_pct = ((total_bal - total_eq) / total_bal) * 100.0
        
        specific_risk_triggered = False
        specific_risk_reason = ""
        if account:
            account_row = conn.execute(
                text("SELECT balance, equity, max_drawdown_percent FROM broker_accounts WHERE account_id = :account_id"),
                {"account_id": account}
            ).fetchone()
            if account_row:
                acc_bal = float(account_row[0]) if account_row[0] else 0.0
                acc_eq = float(account_row[1]) if account_row[1] else 0.0
                acc_max_dd = float(account_row[2]) if account_row[2] is not None else 5.0
                if acc_bal > 0 and acc_bal > acc_eq:
                    acc_dd_pct = ((acc_bal - acc_eq) / acc_bal) * 100.0
                    if acc_dd_pct > acc_max_dd:
                        specific_risk_triggered = True
                        specific_risk_reason = f"DRAWDOWN ACCOUNT {account} ({acc_dd_pct:.2f}%) SUPERA IL LIMITE INDIVIDUALE ({acc_max_dd:.2f}%)"
                        
        global last_risk_state, last_risk_reason
        
        # Check system_settings trading_halted (AI Circuit Breaker)
        trading_halted = False
        try:
            settings_row = conn.execute(text("SELECT trading_halted FROM system_settings WHERE id = 1")).fetchone()
            if settings_row and settings_row[0]:
                trading_halted = True
        except Exception:
            pass

        is_risk_triggered = (current_drawdown_pct > max_drawdown_percent) or emergency_kill_switch or specific_risk_triggered or trading_halted
        risk_reason = ""
        if emergency_kill_switch:
            risk_reason = "EMERGENCY KILL-SWITCH ATTIVATO DA DASHBOARD"
        elif current_drawdown_pct > max_drawdown_percent:
            risk_reason = f"DRAWDOWN ATTUALE ({current_drawdown_pct:.2f}%) SUPERA IL LIMITE ({max_drawdown_percent:.2f}%)"
        elif trading_halted:
            risk_reason = "GLOBAL AI CIRCUIT BREAKER (PANIC REGIME / VSTOXX SURGE)"
        elif specific_risk_triggered:
            risk_reason = specific_risk_reason

        # State transition triggers notification
        if is_risk_triggered and not last_risk_state:
            last_risk_state = True
            last_risk_reason = risk_reason
            send_system_notifications(
                f"🚨 <b>EuroQuant Risk Safeguard TRIGGERED</b>\n"
                f"Status: CLOSE_ALL forced downstream.\n"
                f"Reason: {risk_reason}"
            )
        elif not is_risk_triggered and last_risk_state:
            last_risk_state = False
            last_risk_reason = ""
            send_system_notifications(
                f"✅ <b>EuroQuant Risk Safeguard CLEARED</b>\n"
                f"Status: Normal trading resumed."
            )

        # Check macroeconomic news freeze zone (impact = 'High' within +/- 15 minutes)
        now_utc = datetime.now(timezone.utc)
        news_freeze = False
        news_event_title = ""
        try:
            news_row = conn.execute(
                text("""
                    SELECT title, country, scheduled_time 
                    FROM economic_calendar 
                    WHERE scheduled_time >= :start AND scheduled_time <= :end 
                      AND impact = 'High'
                    LIMIT 1
                """),
                {
                    "start": now_utc - timedelta(minutes=15),
                    "end": now_utc + timedelta(minutes=15)
                }
            ).fetchone()
            if news_row:
                news_freeze = True
                news_event_title = f"{news_row[0]} ({news_row[1]}) alle {news_row[2].strftime('%H:%M')} UTC"
        except Exception as ex:
            print(f"Error checking news freeze zone: {ex}")

        signals = []
        for r_ticker, r_signal, r_reason, r_price, r_gen, r_adx, r_atr, r_vol in rows:
            # Check for manual overrides or risk trigger
            if is_risk_triggered:
                active_signal = "CLOSE_ALL"
                active_reason = f"RISCHIO ATTIVATO: {risk_reason}"
            elif news_freeze and r_signal not in ["CLOSE_ALL", "HOLD"]:
                active_signal = "HOLD"
                active_reason = f"CONGELAMENTO OPERATIVO: Notizia Macroeconomica Imminente: {news_event_title}"
            else:
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

            # Fetch regime
            regime = "REGIME_MEAN_REVERTING"
            try:
                regime_row = conn.execute(
                    text("SELECT regime FROM market_regimes WHERE ticker = :ticker"),
                    {"ticker": r_ticker}
                ).fetchone()
                if regime_row:
                    regime = regime_row[0]
            except Exception:
                pass

            # Calculate Kelly Factor
            kelly_factor = 1.0
            try:
                metrics_row = conn.execute(
                    text("SELECT accuracy FROM ml_model_metrics WHERE ticker = :ticker"),
                    {"ticker": r_ticker}
                ).fetchone()
                
                # Basic Correlation Penalty: Check how many same-direction signals are currently active in the top 10
                correlated_signals = 1
                try:
                    corr_row = conn.execute(
                        text("SELECT COUNT(*) FROM recommendations WHERE signal IN ('BUY', 'STRONG BUY') AND timestamp >= NOW() - INTERVAL '24 HOURS'")
                    ).scalar()
                    if corr_row and corr_row > 0:
                        correlated_signals = max(1, corr_row)
                except Exception:
                    pass
                    
                if metrics_row and metrics_row[0] is not None:
                    p = max(0.01, min(0.99, float(metrics_row[0])))
                    b = 2.0  # Reward/Risk Ratio (TP ATR 3.0 / SL ATR 1.5)
                    kelly_val = p - (1.0 - p) / b
                    
                    # Apply correlation penalty (diversification)
                    kelly_val = kelly_val / (math.sqrt(correlated_signals) if correlated_signals > 1 else 1.0)
                    
                    # Fractional Kelly (cap at 1.0, floor at 0.05)
                    kelly_factor = max(0.05, min(1.0, kelly_val))
            except Exception:
                pass

            # Calculate ATR for SL/TP
            atr_prices = conn.execute(
                text("""
                    SELECT high, low, close
                    FROM stock_prices
                    WHERE ticker = :ticker AND close IS NOT NULL
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
            
            if r_price is None:
                continue
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
                
            # Chandelier Exit Distance (ATR Trailing Stop)
            chandelier_exit_distance = atr * 2.5 if atr > 0 else 0.0
            
            signals.append(MT5Signal(
                ticker=r_ticker,
                mt5_symbol=mt5_symbol,
                action=active_signal,
                entry_price=latest_price,
                stop_loss=sl,
                take_profit=tp,
                reason=active_reason or "Nessun dettaglio aggiuntivo.",
                timestamp=r_gen.strftime("%Y-%m-%d %H:%M:%S") + " Z" if r_gen else "",
                adx=float(r_adx) if r_adx is not None else None,
                atr=float(r_atr) if r_atr is not None else None,
                volatility_lot_sizing=float(r_vol) if r_vol is not None else 1.0,
                kelly_factor=round(kelly_factor, 4),
                regime=regime,
                chandelier_exit_distance=chandelier_exit_distance
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
               (SELECT close FROM stock_prices p WHERE p.ticker = c.ticker AND p.close IS NOT NULL ORDER BY p.timestamp DESC LIMIT 1) as latest_close
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

@app.get("/api/mt5/accounts")
def get_broker_accounts():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT account_id, broker, balance, equity, margin, margin_free, margin_level, profit, last_seen 
                FROM broker_accounts 
                ORDER BY last_seen DESC
            """)).fetchall()
            return [
                {
                    "account_id": r[0],
                    "broker": r[1],
                    "balance": float(r[2]) if r[2] is not None else 0.0,
                    "equity": float(r[3]) if r[3] is not None else 0.0,
                    "margin": float(r[4]) if r[4] is not None else 0.0,
                    "margin_free": float(r[5]) if r[5] is not None else 0.0,
                    "margin_level": float(r[6]) if r[6] is not None else 0.0,
                    "profit": float(r[7]) if r[7] is not None else 0.0,
                    "last_seen": r[8].isoformat() if r[8] else None
                } for r in rows
            ]
    except Exception as e:
        print(f"Error fetching broker accounts: {e}")
        return []

@app.post("/api/mt5/overrides")
async def set_override(payload: OverridePayload, current_user: dict = Depends(get_current_user)):
    ticker = payload.ticker
    action = payload.action
    if action == "CLEAR":
        manual_overrides.pop(ticker, None)
        send_system_notifications(f"ℹ️ <b>EuroQuant Manual Override</b>\nOverride for <code>{ticker}</code> cleared by user <b>{current_user['username']}</b>.")
    else:
        manual_overrides[ticker] = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        send_system_notifications(f"⚠️ <b>EuroQuant Manual Override FORCE</b>\nOverride for <code>{ticker}</code> set to <b>{action}</b> by user <b>{current_user['username']}</b>.")
    await manager.broadcast({"type": "overrides_update"})
    return {"status": "success", "overrides": manual_overrides}

@app.post("/api/mt5/positions")
async def sync_mt5_positions(payload: PositionsPayload):
    try:
        with engine.connect() as conn:
            for pos in payload.positions:
                conn.execute(text("""
                    INSERT INTO live_positions (ticker, quantity, avg_price, current_price, unrealized_pnl, updated_at)
                    VALUES (:ticker, :qty, :avg_price, :current_price, :pnl, NOW())
                    ON CONFLICT (ticker) DO UPDATE SET 
                        quantity = EXCLUDED.quantity,
                        avg_price = EXCLUDED.avg_price,
                        current_price = EXCLUDED.current_price,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        updated_at = NOW();
                """), {
                    "ticker": pos.ticker,
                    "qty": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                    "pnl": pos.unrealized_pnl
                })
            conn.commit()
            
            await manager.broadcast({"type": "positions_update"})
            return {"status": "ok"}
    except Exception as e:
        print(f"Error syncing positions: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.post("/api/mt5/execution-log")
async def sync_execution_log(payload: ExecutionLogPayload):
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO execution_logs (ticker, action, quantity, fill_price, slippage, broker, timestamp)
                VALUES (:ticker, :action, :qty, :fill_price, :slippage, :broker, NOW())
            """), {
                "ticker": payload.ticker,
                "action": payload.action,
                "qty": payload.quantity,
                "fill_price": payload.fill_price,
                "slippage": payload.slippage,
                "broker": payload.broker
            })
            conn.commit()
            
            await manager.broadcast({"type": "execution_logs_update"})
            return {"status": "ok"}
    except Exception as e:
        print(f"Error saving execution log: {e}")
        raise HTTPException(status_code=500, detail="Database error")


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

@app.get("/api/mt5/risk")
def get_risk_settings():
    # Calculate current aggregate drawdown and fetch all accounts
    with engine.connect() as conn:
        acc_stats = conn.execute(text("SELECT SUM(balance), SUM(equity) FROM broker_accounts")).fetchone()
        current_drawdown_pct = 0.0
        if acc_stats and acc_stats[0] and float(acc_stats[0]) > 0:
            total_bal = float(acc_stats[0])
            total_eq = float(acc_stats[1])
            if total_bal > total_eq:
                current_drawdown_pct = ((total_bal - total_eq) / total_bal) * 100.0
                
        accounts_rows = conn.execute(text("SELECT account_id, broker, balance, equity, profit, max_drawdown_percent FROM broker_accounts")).fetchall()
        accounts_data = []
        for r in accounts_rows:
            acc_id, broker, bal, eq, prof, max_dd = r
            bal_val = float(bal) if bal else 0.0
            eq_val = float(eq) if eq else 0.0
            dd = ((bal_val - eq_val) / bal_val * 100.0) if bal_val > eq_val and bal_val > 0 else 0.0
            accounts_data.append({
                "account_id": acc_id,
                "broker": broker or "Unknown",
                "balance": bal_val,
                "equity": eq_val,
                "profit": float(prof) if prof else 0.0,
                "max_drawdown_percent": float(max_dd) if max_dd is not None else 5.0,
                "current_drawdown_percent": round(dd, 2)
            })
                
    return {
        "max_drawdown_percent": max_drawdown_percent,
        "emergency_kill_switch": emergency_kill_switch,
        "current_drawdown_percent": round(current_drawdown_pct, 2),
        "accounts": accounts_data
    }

@app.post("/api/mt5/risk")
async def update_risk_settings(request: Request, payload: RiskSettingsPayload, current_user: dict = Depends(require_admin)):
    """Admin only: updates global max drawdown risk threshold."""
    global max_drawdown_percent
    max_drawdown_percent = payload.max_drawdown_percent
    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "risk_settings_updated",
                    {"max_drawdown_percent": payload.max_drawdown_percent}, ip)
    send_system_notifications(f"🛡️ <b>EuroQuant Risk System</b>\nMax drawdown limit updated to {max_drawdown_percent}% by admin user <b>{current_user['username']}</b>.")
    await manager.broadcast({"type": "risk_update"})
    return {"status": "success", "max_drawdown_percent": max_drawdown_percent}

@app.post("/api/mt5/risk/kill-switch")
async def toggle_kill_switch(request: Request, payload: KillSwitchPayload, current_user: dict = Depends(require_admin)):
    """Admin only: activates or deactivates the emergency kill switch."""
    global emergency_kill_switch
    emergency_kill_switch = payload.active
    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "kill_switch_toggled",
                    {"active": payload.active}, ip)
    status_text = "ATTIVATO" if emergency_kill_switch else "DISATTIVATO"
    send_system_notifications(f"⚠️ <b>EuroQuant EMERGENCY ALERT</b>\nKill switch <b>{status_text}</b> by admin user <b>{current_user['username']}</b>!")
    await manager.broadcast({"type": "risk_update"})
    return {"status": "success", "emergency_kill_switch": emergency_kill_switch}

@app.post("/api/mt5/accounts/{account_id}/risk")
async def update_account_risk_settings(account_id: str, request: Request, payload: AccountRiskPayload, current_user: dict = Depends(require_admin)):
    """Admin only: updates per-account drawdown limit."""
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE broker_accounts SET max_drawdown_percent = :max_dd WHERE account_id = :account_id"),
            {"max_dd": payload.max_drawdown_percent, "account_id": account_id}
        )
        conn.commit()
    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "account_risk_updated",
                    {"account_id": account_id, "max_drawdown_percent": payload.max_drawdown_percent}, ip)
    send_system_notifications(f"🛡️ <b>EuroQuant Risk System</b>\nAccount <code>{account_id}</code> drawdown limit updated to {payload.max_drawdown_percent}% by admin <b>{current_user['username']}</b>.")
    await manager.broadcast({"type": "risk_update"})
    return {"status": "success", "account_id": account_id, "max_drawdown_percent": payload.max_drawdown_percent}

class SystemSettingsPayload(BaseModel):
    telegram_bot_token: str
    telegram_chat_id: str
    discord_webhook_url: str

class PortfolioBacktestRequest(BaseModel):
    tickers: List[str]
    capital: float = 10000.0
    buy_rsi: float = 30.0
    sell_rsi: float = 70.0
    buy_sentiment: float = 0.3
    sell_sentiment: float = -0.3

class PortfolioBacktestResponse(BaseModel):
    initial_capital: float
    final_capital: float
    total_return_percent: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: List[dict]

@app.get("/api/system-settings")
def get_system_settings():
    with engine.connect() as conn:
        row = conn.execute(text("SELECT telegram_bot_token, telegram_chat_id, discord_webhook_url FROM system_settings WHERE id = 1")).fetchone()
        if row:
            from crypto_utils import decrypt_data
            return {
                "telegram_bot_token": decrypt_data(row[0]) or "",
                "telegram_chat_id": decrypt_data(row[1]) or "",
                "discord_webhook_url": decrypt_data(row[2]) or ""
            }
    return {"telegram_bot_token": "", "telegram_chat_id": "", "discord_webhook_url": ""}

@app.post("/api/system-settings")
def update_system_settings(request: Request, payload: SystemSettingsPayload, current_user: dict = Depends(require_admin)):
    """Admin only: updates Telegram/Discord alert credentials."""
    from crypto_utils import encrypt_data
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE system_settings
            SET telegram_bot_token = :tg_token,
                telegram_chat_id = :tg_chat,
                discord_webhook_url = :discord_url
            WHERE id = 1
        """), {
            "tg_token": encrypt_data(payload.telegram_bot_token),
            "tg_chat": encrypt_data(payload.telegram_chat_id),
            "discord_url": encrypt_data(payload.discord_webhook_url)
        })
        conn.commit()
    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "system_settings_updated",
                    {"telegram_configured": bool(payload.telegram_bot_token),
                     "discord_configured": bool(payload.discord_webhook_url)}, ip)
    return {"status": "success"}


import urllib.request
import threading

def send_telegram_alert(message: str):
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT telegram_bot_token, telegram_chat_id FROM system_settings WHERE id = 1")).fetchone()
            if row:
                from crypto_utils import decrypt_data
                token = decrypt_data(row[0])
                chat_id = decrypt_data(row[1])
                if token and chat_id:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    data = json.dumps({
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }).encode('utf-8')
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={'Content-Type': 'application/json'}
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        response.read()
    except Exception as e:
        print(f"Error sending Telegram alert: {e}", flush=True)

def send_discord_alert(message: str):
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT discord_webhook_url FROM system_settings WHERE id = 1")).fetchone()
            if row:
                from crypto_utils import decrypt_data
                webhook_url = decrypt_data(row[2])
                if webhook_url:
                    data = json.dumps({
                        "content": message
                    }).encode('utf-8')
                    req = urllib.request.Request(
                        webhook_url,
                        data=data,
                        headers={'Content-Type': 'application/json'}
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        response.read()
    except Exception as e:
        print(f"Error sending Discord alert: {e}", flush=True)

def send_system_notifications(message: str):
    threading.Thread(target=send_telegram_alert, args=(message,), daemon=True).start()
    threading.Thread(target=send_discord_alert, args=(message,), daemon=True).start()


@app.get("/api/ml/metrics")
def get_ml_metrics(current_user: dict = Depends(require_admin)):
    """Admin only: returns accuracy, precision, and validation stats for ML models."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT ticker, last_trained, accuracy, precision, recall, f1_score, total_samples, features_used
            FROM ml_model_metrics
            ORDER BY ticker ASC
        """)).fetchall()
        result = []
        for r in rows:
            result.append({
                "ticker": r[0],
                "last_trained": r[1].isoformat() if r[1] else None,
                "accuracy": float(r[2]) if r[2] is not None else 0.5,
                "precision": float(r[3]) if r[3] is not None else 0.5,
                "recall": float(r[4]) if r[4] is not None else 0.5,
                "f1_score": float(r[5]) if r[5] is not None else 0.5,
                "total_samples": r[6],
                "features_used": json.loads(r[7]) if isinstance(r[7], str) else (r[7] or [])
            })
        return result


@app.post("/api/ml/retrain")
async def retrain_ml_models(request: Request, current_user: dict = Depends(require_admin)):
    """Admin only: forces online retraining of GradientBoostingClassifier for all active tickers."""
    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "ml_models_retrain_triggered", {}, ip)

    def run_retraining():
        try:
            with engine.connect() as conn:
                tickers_rows = conn.execute(text("SELECT ticker FROM companies")).fetchall()
                tickers = [t[0] for t in tickers_rows]

                from ml_engine import train_and_predict_direction
                success_count = 0
                for ticker in tickers:
                    try:
                        prob = train_and_predict_direction(ticker, conn)
                        conn.execute(text("""
                            UPDATE recommendations
                            SET ml_prediction_prob = :prob,
                                timestamp = NOW()
                            WHERE ticker = :ticker
                        """), {"prob": prob, "ticker": ticker})
                        conn.commit()
                        success_count += 1
                    except Exception as ex:
                        print(f"Error retraining model for {ticker}: {ex}", flush=True)

                send_system_notifications(
                    f"⚠️ <b>EuroQuant Notification</b>\n"
                    f"ML model online retraining completed.\n"
                    f"Successfully updated models for {success_count}/{len(tickers)} tickers."
                )
        except Exception as err:
            print(f"Error in retraining thread: {err}", flush=True)

    threading.Thread(target=run_retraining, daemon=True).start()
    send_system_notifications(
        f"⚠️ <b>EuroQuant Notification</b>\n"
        f"ML model online retraining triggered by admin user: <b>{current_user['username']}</b>."
    )
    return {"status": "success", "message": "Retraining thread started successfully."}



@app.get("/api/market-regimes")
def get_market_regimes():
    """Returns the classified market regimes for all tracked companies."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT ticker, regime, volatility_30d, atr_ratio, timestamp 
                FROM market_regimes 
                ORDER BY ticker ASC
            """)
        ).fetchall()
    return [
        {
            "ticker": r[0],
            "regime": r[1],
            "volatility_30d": r[2],
            "atr_ratio": r[3],
            "timestamp": r[4].isoformat() if r[4] else None
        }
        for r in rows
    ]

@app.get("/api/economic-calendar")
def get_economic_calendar(limit: int = 50):
    """Returns upcoming macroeconomic events from the economic calendar."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, event_key, title, country, impact, scheduled_time, timestamp 
                FROM economic_calendar 
                ORDER BY scheduled_time DESC 
                LIMIT :limit
            """),
            {"limit": limit}
        ).fetchall()
    return [
        {
            "id": r[0],
            "event_key": r[1],
            "title": r[2],
            "country": r[3],
            "impact": r[4],
            "scheduled_time": r[5].isoformat() if r[5] else None,
            "timestamp": r[6].isoformat() if r[6] else None
        }
        for r in rows
    ]



@app.get("/api/portfolio/weights")
def get_portfolio_weights():
    """Returns the optimized Markowitz portfolio weights."""
    from portfolio_opt import get_optimized_portfolio_weights
    weights = get_optimized_portfolio_weights()
    return weights



@app.get("/api/audit-log")
def get_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """Admin only: returns recent audit log entries for compliance review."""
    with engine.connect() as conn:
        if action:
            rows = conn.execute(
                text("""
                    SELECT id, username, action, details, ip_address, timestamp
                    FROM audit_log
                    WHERE action = :action
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"action": action, "limit": min(limit, 1000)}
            ).fetchall()
        else:
            rows = conn.execute(
                text("""
                    SELECT id, username, action, details, ip_address, timestamp
                    FROM audit_log
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"limit": min(limit, 1000)}
            ).fetchall()
    return [
        {
            "id": r[0],
            "username": r[1],
            "action": r[2],
            "details": r[3],
            "ip_address": r[4],
            "timestamp": r[5].isoformat() if r[5] else None
        }
        for r in rows
    ]

class OrderPayload(BaseModel):
    id: str
    account_id: str
    ticker: str
    action: str
    status: str
    requested_price: float
    executed_price: float
    slippage: Optional[float] = 0.0
    commission: Optional[float] = 0.0

@app.get("/api/orders")
def get_orders():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, account_id, ticker, action, status, requested_price, executed_price, slippage, commission, timestamp FROM orders ORDER BY timestamp DESC LIMIT 100")).fetchall()
        return [
            {
                "id": r[0],
                "account_id": r[1],
                "ticker": r[2],
                "action": r[3],
                "status": r[4],
                "requested_price": float(r[5]) if r[5] is not None else 0.0,
                "executed_price": float(r[6]) if r[6] is not None else 0.0,
                "slippage": float(r[7]) if r[7] is not None else 0.0,
                "commission": float(r[8]) if r[8] is not None else 0.0,
                "timestamp": r[9].isoformat() if r[9] else None
            }
            for r in rows
        ]

@app.post("/api/orders")
def create_order(payload: OrderPayload):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO orders (id, account_id, ticker, action, status, requested_price, executed_price, slippage, commission)
                VALUES (:id, :account_id, :ticker, :action, :status, :requested_price, :executed_price, :slippage, :commission)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    executed_price = EXCLUDED.executed_price,
                    slippage = EXCLUDED.slippage,
                    commission = EXCLUDED.commission
            """),
            {
                "id": payload.id,
                "account_id": payload.account_id,
                "ticker": payload.ticker,
                "action": payload.action,
                "status": payload.status,
                "requested_price": payload.requested_price,
                "executed_price": payload.executed_price,
                "slippage": payload.slippage,
                "commission": payload.commission
            }
        )
        conn.commit()
    return {"status": "success", "order_id": payload.id}

@app.get("/api/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/stock/{ticker}/summary")
def get_stock_llm_summary(ticker: str):
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    with engine.connect() as conn:
        articles = conn.execute(text("""
            SELECT a.title, a.sentiment_label, a.sentiment_score
            FROM news_articles a
            JOIN news_company_mappings m ON a.id = m.article_id
            WHERE m.company_ticker = :ticker
            ORDER BY a.published_date DESC
            LIMIT 5
        """), {"ticker": ticker}).fetchall()
        
        if not articles:
            return {"summary": "Nessuna notizia recente disponibile per analizzare il sentiment di questo asset."}
            
        articles_text = "\n".join([f"- {a[0]} (Sentiment: {a[1]}, Score: {a[2]})" for a in articles])
        
        prompt = f"""Sei un analista finanziario istituzionale.
Basandoti sulle seguenti notizie recenti per l'asset {ticker}:
{articles_text}

Fornisci una sintesi esplicativa del sentiment generale di massimo 3 righe in italiano. Sii estremamente sintetico, professionale e focalizzato sulle notizie reali. Non inserire commenti personali, markdown o link.
"""
        try:
            import requests
            url = f"{OLLAMA_HOST}/api/generate"
            payload = {
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 120,
                    "num_thread": 4
                }
            }
            response = requests.post(url, json=payload, timeout=25)
            if response.status_code != 200:
                payload["model"] = "llama3"
                response = requests.post(url, json=payload, timeout=30)
                
            if response.status_code == 200:
                return {"summary": response.json().get("response", "").strip()}
        except Exception as e:
            print(f"Error calling Ollama for summary: {e}")
            
        return {"summary": "Impossibile contattare il modello locale Ollama per sintetizzare il sentiment."}

@app.get("/api/market-correlation")
def get_market_correlation():
    # Predefined list of 12 major assets for multi-asset matrix
    assets = ['BTCUSD', 'ETHUSD', 'XRPUSD', 'AAPL', 'TSLA', 'NVDA', 'ENI.MI', 'ENEL.MI', 'TTE.PA', 'MC.PA', 'SAP.DE', 'EURUSD=X']
    
    with engine.connect() as conn:
        # Fetch last 60 days of prices for all these assets
        rows = conn.execute(text("""
            SELECT ticker, timestamp, close
            FROM stock_prices
            WHERE ticker IN :assets AND close IS NOT NULL
            ORDER BY timestamp ASC
        """), {"assets": tuple(assets)}).fetchall()
        
    # Organize data by date and ticker
    data_by_ticker = {ticker: {} for ticker in assets}
    all_dates = set()
    
    for ticker, ts, close in rows:
        d_str = ts.strftime("%Y-%m-%d")
        data_by_ticker[ticker][d_str] = float(close)
        all_dates.add(d_str)
        
    sorted_dates = sorted(list(all_dates))
    
    # Calculate daily percentage changes for each ticker
    returns_by_ticker = {ticker: [] for ticker in assets}
    for ticker in assets:
        prices = []
        for d in sorted_dates:
            val = data_by_ticker[ticker].get(d, None)
            if val is None and prices:
                val = prices[-1]
            if val is not None:
                prices.append(val)
            else:
                prices.append(0.0)
                
        daily_returns = []
        for i in range(1, len(prices)):
            prev = prices[i-1]
            curr = prices[i]
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
            else:
                daily_returns.append(0.0)
        returns_by_ticker[ticker] = daily_returns
        
    # Calculate Pearson Correlation Matrix
    def pearson_corr(x, y):
        n = len(x)
        if n == 0:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        diff_x = [val - mean_x for val in x]
        diff_y = [val - mean_y for val in y]
        num = sum(dx * dy for dx, dy in zip(diff_x, diff_y))
        den_x = sum(dx ** 2 for dx in diff_x)
        den_y = sum(dy ** 2 for dy in diff_y)
        if den_x == 0 or den_y == 0:
            return 0.0
        return num / ((den_x * den_y) ** 0.5)
        
    matrix = []
    for t1 in assets:
        row = []
        for t2 in assets:
            row.append(round(pearson_corr(returns_by_ticker[t1], returns_by_ticker[t2]), 3))
        matrix.append(row)
        
    return {
        "tickers": assets,
        "matrix": matrix
    }

@app.get("/api/mt5/risk-analytics")
def get_risk_analytics():
    with engine.connect() as conn:
        live_rows = conn.execute(text("SELECT ticker, quantity, current_price FROM live_positions")).fetchall()
        
        if not live_rows:
            return {
                "value_at_risk_95": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
                "equity_curve": []
            }
            
        tickers = []
        weights = []
        total_value = 0.0
        portfolio_positions = []
        
        for r in live_rows:
            t = r[0]
            q = float(r[1])
            p = float(r[2]) if r[2] else 1.0
            val = q * p
            total_value += val
            portfolio_positions.append({"ticker": t, "value": val})
            
        if total_value <= 0:
            return {"value_at_risk_95": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0, "equity_curve": []}
            
        for pos in portfolio_positions:
            tickers.append(pos["ticker"])
            weights.append(pos["value"] / total_value)
            
        rows = conn.execute(text("""
            SELECT ticker, timestamp, close
            FROM stock_prices
            WHERE ticker IN :tickers AND close IS NOT NULL
            ORDER BY timestamp ASC
        """), {"tickers": tuple(tickers)}).fetchall()
        
    data_by_ticker = {ticker: {} for ticker in tickers}
    all_dates = set()
    for ticker, ts, close in rows:
        d_str = ts.strftime("%Y-%m-%d")
        data_by_ticker[ticker][d_str] = float(close)
        all_dates.add(d_str)
        
    sorted_dates = sorted(list(all_dates))
    if len(sorted_dates) < 2:
        return {
            "value_at_risk_95": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "equity_curve": []
        }
        
    aligned_prices = []
    for d in sorted_dates:
        row_prices = []
        for t in tickers:
            val = data_by_ticker[t].get(d, None)
            if val is None and aligned_prices:
                val = aligned_prices[-1][tickers.index(t)]
            row_prices.append(val if val is not None else 1.0)
        aligned_prices.append(row_prices)
        
    equity = 100000.0
    equity_curve = [{"date": sorted_dates[0], "equity": equity}]
    daily_returns = []
    
    for i in range(1, len(aligned_prices)):
        prev_row = aligned_prices[i-1]
        curr_row = aligned_prices[i]
        
        day_return = 0.0
        for j in range(len(tickers)):
            prev_p = prev_row[j]
            curr_p = curr_row[j]
            if prev_p > 0:
                day_return += weights[j] * ((curr_p - prev_p) / prev_p)
                
        equity = equity * (1.0 + day_return)
        equity_curve.append({"date": sorted_dates[i], "equity": round(equity, 2)})
        daily_returns.append(day_return)
        
    mean_ret = sum(daily_returns) / len(daily_returns) if daily_returns else 0.0
    var_ret = sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns) if len(daily_returns) > 1 else 0.0
    std_ret = var_ret ** 0.5
    
    downside_returns = [r for r in daily_returns if r < 0]
    downside_var = sum((r - mean_ret) ** 2 for r in downside_returns) / len(downside_returns) if downside_returns else 0.00001
    downside_std = downside_var ** 0.5
    
    sharpe = round((mean_ret / std_ret * (252 ** 0.5)), 2) if std_ret > 0 else 0.0
    sortino = round((mean_ret / downside_std * (252 ** 0.5)), 2) if downside_std > 0 else 0.0
    
    peak = 100000.0
    max_dd = 0.0
    for eq_item in equity_curve:
        val = eq_item["equity"]
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
            
    sorted_returns = sorted(daily_returns)
    var_idx = int(0.05 * len(sorted_returns))
    var_95 = sorted_returns[var_idx] if sorted_returns else 0.0
    
    return {
        "value_at_risk_95": round(abs(var_95) * 100.0, 2),
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": round(max_dd, 2),
        "equity_curve": equity_curve
    }

@app.get("/api/mt5/stress-test")
def get_stress_test():
    with engine.connect() as conn:
        live_rows = conn.execute(text("SELECT ticker, quantity, current_price FROM live_positions")).fetchall()
        if not live_rows:
            return {"scenarios": []}
            
        total_value = sum([float(r[1]) * (float(r[2]) if r[2] else 1.0) for r in live_rows])
        if total_value <= 0:
            return {"scenarios": []}
            
        # Simplified heuristics based on static scenario historical drops adjusted by portfolio beta
        # In a full institutional system, we would calculate exact daily historical prices for the portfolio during these dates.
        scenarios = [
            {"name": "COVID Crash (Feb-Mar 2020)", "max_drawdown": -32.5},
            {"name": "Tech Selloff (2022)", "max_drawdown": -21.4},
            {"name": "Flash Crash Simulation (VIX > 40)", "max_drawdown": -12.8}
        ]
        return {"scenarios": scenarios}

@app.get("/api/mt5/hedging/beta")
def get_hedging_beta():
    with engine.connect() as conn:
        live_rows = conn.execute(text("SELECT ticker, quantity, current_price FROM live_positions")).fetchall()
        total_value = sum([float(r[1]) * (float(r[2]) if r[2] else 1.0) for r in live_rows])
        
        if total_value <= 0:
            return {"index": "US500", "required_short_lots": 0.0, "portfolio_value": 0.0, "beta": 1.0}
            
        us500_price = 5400.0
        portfolio_beta = 1.15
        
        hedge_value = total_value * portfolio_beta
        required_lots = round(hedge_value / us500_price, 2)
        
        return {
            "index": "US500",
            "portfolio_value": round(total_value, 2),
            "beta": portfolio_beta,
            "required_short_lots": required_lots
        }

@app.post("/api/backtest/portfolio", response_model=PortfolioBacktestResponse)
def run_portfolio_backtest(req: PortfolioBacktestRequest):
    if not req.tickers:
        raise HTTPException(status_code=400, detail="Must provide at least one ticker.")
        
    with engine.connect() as conn:
        prices_rows = conn.execute(text("""
            SELECT ticker, timestamp, close, rsi
            FROM stock_prices
            WHERE ticker IN :tickers AND close IS NOT NULL
            ORDER BY timestamp ASC
        """), {"tickers": tuple(req.tickers)}).fetchall()
        
        sent_rows = conn.execute(text("""
            SELECT m.company_ticker, a.published_date, a.sentiment_score
            FROM news_articles a
            JOIN news_company_mappings m ON a.id = m.article_id
            WHERE m.company_ticker IN :tickers AND a.sentiment_score IS NOT NULL
        """), {"tickers": tuple(req.tickers)}).fetchall()
        
    sent_by_ticker_date = {ticker: {} for ticker in req.tickers}
    for tick, dt, score in sent_rows:
        d_str = dt.strftime("%Y-%m-%d")
        if d_str not in sent_by_ticker_date[tick]:
            sent_by_ticker_date[tick][d_str] = []
        sent_by_ticker_date[tick][d_str].append(float(score))
        
    avg_sent_by_ticker_date = {tick: {} for tick in req.tickers}
    for tick in req.tickers:
        for d, vals in sent_by_ticker_date[tick].items():
            avg_sent_by_ticker_date[tick][d] = sum(vals)/len(vals)
            
    prices_by_date = {}
    for ticker, ts, close, rsi in prices_rows:
        d_str = ts.strftime("%Y-%m-%d")
        if d_str not in prices_by_date:
            prices_by_date[d_str] = {}
        prices_by_date[d_str][ticker] = (float(close), float(rsi) if rsi else 50.0)
        
    sorted_dates = sorted(list(prices_by_date.keys()))
    if not sorted_dates:
        raise HTTPException(status_code=404, detail="No price data available for the backtest period.")
        
    cash = req.capital
    positions = {}
    equity_curve = []
    
    trades = 0
    winning_trades = 0
    peak_equity = req.capital
    max_dd = 0.0
    
    max_pos = len(req.tickers)
    allocation_per_pos = req.capital / max_pos
    
    for d in sorted_dates:
        day_prices = prices_by_date[d]
        
        liquidated = []
        for ticker, pos_info in list(positions.items()):
            if ticker in day_prices:
                close_val, rsi_val = day_prices[ticker]
                sentiment_val = avg_sent_by_ticker_date[ticker].get(d, 0.0)
                
                if rsi_val >= req.sell_rsi or sentiment_val <= req.sell_sentiment:
                    # Incorporate slippage (exit price is slightly lower) & commission (0.1%)
                    executed_sell_price = close_val * 0.9995
                    gross_cash = pos_info["units"] * executed_sell_price
                    commission_cost = gross_cash * 0.001
                    cash += gross_cash - commission_cost
                    trades += 1
                    if executed_sell_price > pos_info["entry_price"]:
                        winning_trades += 1
                    liquidated.append(ticker)
                    
        for t in liquidated:
            positions.pop(t)
            
        for ticker in req.tickers:
            if ticker not in positions and ticker in day_prices:
                close_val, rsi_val = day_prices[ticker]
                sentiment_val = avg_sent_by_ticker_date[ticker].get(d, 0.0)
                
                if (rsi_val <= req.buy_rsi or sentiment_val >= req.buy_sentiment) and cash >= allocation_per_pos:
                    # Incorporate slippage (entry price is slightly higher) & commission (0.1%)
                    executed_buy_price = close_val * 1.0005
                    commission_cost = allocation_per_pos * 0.001
                    net_cash = allocation_per_pos - commission_cost
                    units = net_cash / executed_buy_price
                    positions[ticker] = {"units": units, "entry_price": executed_buy_price}
                    cash -= allocation_per_pos
                    
        current_eq = cash
        for ticker, pos_info in positions.items():
            if ticker in day_prices:
                current_eq += pos_info["units"] * day_prices[ticker][0]
            else:
                current_eq += pos_info["units"] * pos_info["entry_price"]
                
        if current_eq > peak_equity:
            peak_equity = current_eq
        dd = (peak_equity - current_eq) / peak_equity * 100.0
        if dd > max_dd:
            max_dd = dd
            
        equity_curve.append({"date": d, "equity": round(current_eq, 2)})
        
    final_cap = current_eq
    win_rate = (winning_trades / trades * 100.0) if trades > 0 else 0.0
    tot_ret = ((final_cap - req.capital) / req.capital) * 100.0
    
    return PortfolioBacktestResponse(
        initial_capital=req.capital,
        final_capital=round(final_cap, 2),
        total_return_percent=round(tot_ret, 2),
        max_drawdown=round(max_dd, 2),
        win_rate=round(win_rate, 2),
        total_trades=trades,
        equity_curve=equity_curve
    )

class OptimizePortfolioPayload(BaseModel):
    tickers: List[str]
    method: str = "max_sharpe"
    use_black_litterman: bool = True
    rf_rate: float = 0.0

@app.post("/api/portfolio/optimize")
def post_optimize_portfolio(payload: OptimizePortfolioPayload):
    from portfolio_opt import optimize_portfolio
    try:
        with engine.connect() as db:
            res = optimize_portfolio(
                payload.tickers, 
                db, 
                method=payload.method, 
                use_black_litterman=payload.use_black_litterman, 
                rf=payload.rf_rate
            )
            return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio/monte-carlo")
def get_portfolio_monte_carlo(capital: float = 10000.0, days: int = 30, runs: int = 1000):
    try:
        import numpy as np
        import pandas as pd
        from portfolio_opt import fetch_historical_returns
        
        with engine.connect() as db:
            tickers_query = db.execute(text("SELECT ticker FROM companies WHERE sector NOT IN ('Index', 'Forex')")).fetchall()
            tickers = [t[0] for t in tickers_query]
            
            returns_df = fetch_historical_returns(tickers, db, days=60)
            
        if returns_df.empty or returns_df.shape[1] < 2:
            mu_d = 0.0005
            sigma_d = 0.01
        else:
            port_returns = returns_df.mean(axis=1)
            mu_d = float(port_returns.mean())
            sigma_d = float(port_returns.std())
            if np.isnan(mu_d) or mu_d is None:
                mu_d = 0.0005
            if np.isnan(sigma_d) or sigma_d is None or sigma_d == 0:
                sigma_d = 0.01

        sim_paths = np.zeros((runs, days + 1))
        sim_paths[:, 0] = capital
        
        for t in range(1, days + 1):
            shocks = np.random.normal(mu_d, sigma_d, runs)
            sim_paths[:, t] = sim_paths[:, t - 1] * (1.0 + shocks)
            
        drawdowns = []
        for i in range(runs):
            path = sim_paths[i, :]
            max_val = np.maximum.accumulate(path)
            max_val[max_val == 0] = 1.0
            dd = (max_val - path) / max_val * 100.0
            drawdowns.append(np.max(dd))
            
        prob_dd_5 = float(np.sum(np.array(drawdowns) > 5.0) / runs * 100.0)
        
        paths_data = []
        for t in range(days + 1):
            vals = sim_paths[:, t]
            paths_data.append({
                "day": t,
                "p5": float(np.percentile(vals, 5)),
                "p50": float(np.percentile(vals, 50)),
                "p95": float(np.percentile(vals, 95))
            })
            
        final_returns = (sim_paths[:, -1] - capital) / capital
        var_95 = float(-np.percentile(final_returns, 5) * 100.0)
        
        cutoff = np.percentile(final_returns, 5)
        cvar_95 = float(-np.mean(final_returns[final_returns <= cutoff]) * 100.0)
        
        return {
            "paths": paths_data,
            "var_95": round(var_95, 2),
            "cvar_95": round(cvar_95, 2),
            "prob_drawdown_5": round(prob_dd_5, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OptimizeParamsPayload(BaseModel):
    tickers: List[str]
    capital: float = 10000.0

@app.post("/api/backtest/optimize-params")
def post_optimize_params(payload: OptimizeParamsPayload):
    try:
        import numpy as np
        import pandas as pd
        
        with engine.connect() as conn:
            prices_rows = conn.execute(text("""
                SELECT ticker, timestamp, close, rsi
                FROM stock_prices
                WHERE ticker IN :tickers AND close IS NOT NULL
                ORDER BY timestamp ASC
            """), {"tickers": tuple(payload.tickers)}).fetchall()
            
            sent_rows = conn.execute(text("""
                SELECT m.company_ticker, a.published_date, a.sentiment_score
                FROM news_articles a
                JOIN news_company_mappings m ON a.id = m.article_id
                WHERE m.company_ticker IN :tickers AND a.sentiment_score IS NOT NULL
            """), {"tickers": tuple(payload.tickers)}).fetchall()
            
        if not prices_rows:
            return {"status": "no_data", "best_params": []}
            
        sent_by_ticker_date = {ticker: {} for ticker in payload.tickers}
        for tick, dt, score in sent_rows:
            d_str = dt.strftime("%Y-%m-%d")
            if d_str not in sent_by_ticker_date[tick]:
                sent_by_ticker_date[tick][d_str] = []
            sent_by_ticker_date[tick][d_str].append(float(score))
            
        avg_sent_by_ticker_date = {tick: {} for tick in payload.tickers}
        for tick in payload.tickers:
            for d, vals in sent_by_ticker_date[tick].items():
                avg_sent_by_ticker_date[tick][d] = sum(vals)/len(vals)
                
        prices_by_date = {}
        for ticker, ts, close, rsi in prices_rows:
            d_str = ts.strftime("%Y-%m-%d")
            if d_str not in prices_by_date:
                prices_by_date[d_str] = {}
            prices_by_date[d_str][ticker] = (float(close), float(rsi) if rsi else 50.0)
            
        sorted_dates = sorted(list(prices_by_date.keys()))
        if len(sorted_dates) < 5:
            return {"status": "insufficient_data", "best_params": []}

        buy_rsi_grid = [25, 30, 35]
        sell_rsi_grid = [65, 70, 75]
        buy_sent_grid = [0.1, 0.2, 0.3]
        sell_sent_grid = [-0.3, -0.2, -0.1]
        
        results = []
        
        for brsi in buy_rsi_grid:
            for srsi in sell_rsi_grid:
                for bsent in buy_sent_grid:
                    for ssent in sell_sent_grid:
                        cash = payload.capital
                        positions = {}
                        peak_equity = payload.capital
                        max_dd = 0.0
                        trades = 0
                        winning_trades = 0
                        max_pos = len(payload.tickers)
                        allocation_per_pos = payload.capital / max_pos if max_pos > 0 else 0.0
                        daily_eq = []
                        
                        for d in sorted_dates:
                            day_prices = prices_by_date[d]
                            
                            liquidated = []
                            for ticker, pos_info in list(positions.items()):
                                if ticker in day_prices:
                                    close_val, rsi_val = day_prices[ticker]
                                    sentiment_val = avg_sent_by_ticker_date[ticker].get(d, 0.0)
                                    
                                    if rsi_val >= srsi or sentiment_val <= ssent:
                                        cash += pos_info["units"] * close_val
                                        trades += 1
                                        if close_val > pos_info["entry_price"]:
                                            winning_trades += 1
                                        liquidated.append(ticker)
                            for t in liquidated:
                                positions.pop(t)
                                
                            for ticker in payload.tickers:
                                if ticker not in positions and ticker in day_prices:
                                    close_val, rsi_val = day_prices[ticker]
                                    sentiment_val = avg_sent_by_ticker_date[ticker].get(d, 0.0)
                                    
                                    if (rsi_val <= brsi or sentiment_val >= bsent) and cash >= allocation_per_pos:
                                        units = allocation_per_pos / close_val
                                        positions[ticker] = {"units": units, "entry_price": close_val}
                                        cash -= allocation_per_pos
                                        
                            curr_eq = cash
                            for ticker, pos_info in positions.items():
                                if ticker in day_prices:
                                    curr_eq += pos_info["units"] * day_prices[ticker][0]
                                else:
                                    curr_eq += pos_info["units"] * pos_info["entry_price"]
                                    
                            if curr_eq > peak_equity:
                                peak_equity = curr_eq
                            dd = (peak_equity - curr_eq) / peak_equity * 100.0
                            if dd > max_dd:
                                max_dd = dd
                            daily_eq.append(curr_eq)
                            
                        eq_s = pd.Series(daily_eq)
                        returns = eq_s.pct_change().dropna()
                        std_ret = returns.std()
                        if std_ret > 0:
                            sharpe = float((returns.mean() / std_ret) * np.sqrt(252))
                        else:
                            sharpe = 0.0
                            
                        tot_ret = float(((curr_eq - payload.capital) / payload.capital) * 100.0)
                        win_rate = (winning_trades / trades * 100.0) if trades > 0 else 0.0
                        
                        results.append({
                            "buy_rsi": brsi,
                            "sell_rsi": srsi,
                            "buy_sentiment": bsent,
                            "sell_sentiment": ssent,
                            "total_return_percent": round(tot_ret, 2),
                            "max_drawdown": round(max_dd, 2),
                            "sharpe_ratio": round(sharpe, 2),
                            "win_rate": round(win_rate, 2),
                            "total_trades": trades
                        })
                        
        results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
        return {
            "status": "success",
            "best_params": results[:5]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



class SystemLogResponse(BaseModel):
    id: int
    level: str
    source: str
    message: str
    timestamp: str

@app.get("/api/system-logs", response_model=List[SystemLogResponse])
def get_system_logs(limit: int = 200, current_user: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            logs = conn.execute(
                text("SELECT id, level, source, message, timestamp FROM system_logs ORDER BY timestamp DESC LIMIT :limit"),
                {"limit": limit}
            ).fetchall()
            
            return [
                {
                    "id": l[0],
                    "level": l[1],
                    "source": l[2],
                    "message": l[3],
                    "timestamp": l[4].isoformat() if l[4] else ""
                }
                for l in logs
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio-weights")
def get_portfolio_weights(current_user: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            weights = conn.execute(
                text("""
                SELECT p.ticker, p.weight, p.method, c.name, c.sector
                FROM portfolio_weights p
                JOIN companies c ON p.ticker = c.ticker
                WHERE p.timestamp >= NOW() - INTERVAL '1 day'
                ORDER BY p.weight DESC
                """)
            ).fetchall()
            
            return {
                "status": "success",
                "weights": [
                    {
                        "ticker": w[0],
                        "weight": float(w[1]),
                        "method": w[2],
                        "name": w[3],
                        "sector": w[4]
                    }
                    for w in weights if float(w[1]) > 0.01
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hedging-strategies")
def get_hedging_strategies(current_user: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            strategies = conn.execute(
                text("""
                SELECT h.ticker, h.option_type, h.strike, h.expiry_days, h.theoretical_price,
                       h.delta, h.gamma, h.theta, h.vega, c.name
                FROM hedging_strategies h
                JOIN companies c ON h.ticker = c.ticker
                WHERE h.timestamp >= NOW() - INTERVAL '1 day'
                ORDER BY h.timestamp DESC
                """)
            ).fetchall()
            
            return {
                "status": "success",
                "strategies": [
                    {
                        "ticker": s[0],
                        "option_type": s[1],
                        "strike": float(s[2]),
                        "expiry_days": s[3],
                        "theoretical_price": float(s[4]),
                        "delta": float(s[5]) if s[5] else None,
                        "gamma": float(s[6]) if s[6] else None,
                        "theta": float(s[7]) if s[7] else None,
                        "vega": float(s[8]) if s[8] else None,
                        "name": s[9]
                    }
                    for s in strategies
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/live-positions")
def get_live_positions(current_user: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            positions = conn.execute(
                text("""
                SELECT l.ticker, l.quantity, l.avg_price, l.current_price, l.unrealized_pnl, c.name
                FROM live_positions l
                LEFT JOIN companies c ON l.ticker = c.ticker
                """)
            ).fetchall()
            
            return {
                "status": "success",
                "positions": [
                    {
                        "ticker": p[0],
                        "quantity": float(p[1]),
                        "avg_price": float(p[2]),
                        "current_price": float(p[3]),
                        "unrealized_pnl": float(p[4]) if p[4] else 0.0,
                        "name": p[5]
                    }
                    for p in positions
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/execution-logs")
def get_execution_logs(current_user: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            logs = conn.execute(
                text("""
                SELECT id, ticker, action, quantity, fill_price, slippage, broker, timestamp
                FROM execution_logs
                ORDER BY timestamp DESC
                LIMIT 50
                """)
            ).fetchall()
            
            return {
                "status": "success",
                "logs": [
                    {
                        "id": l[0],
                        "ticker": l[1],
                        "action": l[2],
                        "quantity": float(l[3]),
                        "fill_price": float(l[4]),
                        "slippage": float(l[5]) if l[5] else 0.0,
                        "broker": l[6],
                        "timestamp": l[7]
                    }
                    for l in logs
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- MT5 INTEGRATION ENDPOINTS ---

class MT5Position(BaseModel):
    ticker: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float

class MT5PositionsPayload(BaseModel):
    positions: List[MT5Position]

class MT5ExecutionLog(BaseModel):
    ticker: str
    action: str
    quantity: float
    fill_price: float
    slippage: float = 0.0

@app.get("/api/mt5/signals")
def get_mt5_signals(balance: float = 0.0, equity: float = 0.0, margin: float = 0.0, margin_free: float = 0.0):
    try:
        with engine.connect() as conn:
            # We return recommendations combined with portfolio weights to generate target actions
            # For simplicity, returning just the latest BUY/SELL recommendations
            signals = conn.execute(
                text("""
                SELECT ticker, signal, volatility_lot_sizing
                FROM recommendations
                WHERE timestamp >= NOW() - INTERVAL '1 day'
                  AND signal IN ('BUY', 'SELL')
                """)
            ).fetchall()
            
            result = []
            for s in signals:
                ticker = s[0]
                action = s[1]
                vol_lot = s[2] if s[2] else 1.0
                
                # Fetch basic price info to formulate SL/TP roughly for EA
                price_row = conn.execute(
                    text("SELECT close FROM stock_prices WHERE ticker = :ticker ORDER BY timestamp DESC LIMIT 1"),
                    {"ticker": ticker}
                ).fetchone()
                
                current_price = float(price_row[0]) if price_row else 100.0
                sl = current_price * 0.95 if action == 'BUY' else current_price * 1.05
                tp = current_price * 1.10 if action == 'BUY' else current_price * 0.90
                
                result.append({
                    "ticker": ticker,
                    "mt5_symbol": ticker, # MT5 EA will resolve this using ResolveMt5Symbol
                    "action": action,
                    "entry_price": str(current_price),
                    "stop_loss": str(sl),
                    "take_profit": str(tp),
                    "reason": "AI Generated Signal",
                    "volatility_lot_sizing": str(vol_lot)
                })
                
            return result # MT5 EA expects an array of objects directly
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/positions")
def update_mt5_positions(payload: MT5PositionsPayload):
    try:
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE live_positions"))
            
            for pos in payload.positions:
                conn.execute(
                    text("""
                    INSERT INTO live_positions (ticker, quantity, avg_price, current_price, unrealized_pnl)
                    VALUES (:ticker, :quantity, :avg_price, :current_price, :unrealized_pnl)
                    """),
                    {
                        "ticker": pos.ticker,
                        "quantity": pos.quantity,
                        "avg_price": pos.avg_price,
                        "current_price": pos.current_price,
                        "unrealized_pnl": pos.unrealized_pnl
                    }
                )
            conn.commit()
            return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mt5/execution-log")
def log_mt5_execution(payload: MT5ExecutionLog):
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                INSERT INTO execution_logs (ticker, action, quantity, fill_price, slippage, broker)
                VALUES (:ticker, :action, :quantity, :fill_price, :slippage, 'mt5')
                """),
                {
                    "ticker": payload.ticker,
                    "action": payload.action,
                    "quantity": payload.quantity,
                    "fill_price": payload.fill_price,
                    "slippage": payload.slippage
                }
            )
            conn.commit()
            return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
