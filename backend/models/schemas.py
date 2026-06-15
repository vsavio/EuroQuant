"""
backend/models/schemas.py
=========================
All Pydantic request/response schemas centralised in one place.
Routers import from here; main.py no longer needs inline class definitions.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# ─── Risk ─────────────────────────────────────────────────────────────────────
class RiskSettingsPayload(BaseModel):
    max_drawdown_percent: float

class AccountRiskPayload(BaseModel):
    max_drawdown_percent: float

class KillSwitchPayload(BaseModel):
    active: bool

# ─── Overrides / Tickers ──────────────────────────────────────────────────────
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

# ─── Market Summary ───────────────────────────────────────────────────────────
class IndexSummary(BaseModel):
    ticker: str
    name: str
    price: float
    change_pct: float

class VolatilitySummary(BaseModel):
    price: float
    status: str   # SAFE | ELEVATED | RISK_WARNING
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

# ─── Screener / Stock ─────────────────────────────────────────────────────────
class ScreenerRow(BaseModel):
    ticker: str
    name: str
    country: str
    sector: str
    price: float
    price_change_24h: float
    sentiment_score: float
    signal: str
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

class SignalHistoryItem(BaseModel):
    signal: str
    sentiment_score: Optional[float]
    price_change_24h: Optional[float]
    reason_technical: Optional[str]
    timestamp: str

# ─── News ─────────────────────────────────────────────────────────────────────
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

# ─── MT5 Bridge ───────────────────────────────────────────────────────────────
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
    regime: Optional[str] = "REGIME_MEAN_REVERTING"
    chandelier_exit_distance: Optional[float] = 0.0

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

class MT5Position(BaseModel):
    ticket: int
    symbol: str
    type: str
    volume: float
    open_price: float
    current_price: float
    profit: float
    sl: float
    tp: float

class MT5PositionsPayload(BaseModel):
    account_id: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    positions: List[MT5Position]

class MT5ExecutionLog(BaseModel):
    ticker: str
    action: str
    quantity: float
    fill_price: float
    slippage: float = 0.0
    broker: str = "MT5"

# ─── Portfolio & Backtest ─────────────────────────────────────────────────────
class BacktestRequest(BaseModel):
    ticker: str
    strategy: str = "ML_ENSEMBLE"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 10000.0

class BacktestResponse(BaseModel):
    ticker: str
    strategy: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    trades: List[dict]

class BacktestOptimizeRequest(BaseModel):
    ticker: str
    initial_capital: float = 10000.0

class OptimizationItem(BaseModel):
    strategy: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int

class BacktestOptimizeResponse(BaseModel):
    ticker: str
    results: List[OptimizationItem]
    best_strategy: str

class PortfolioBacktestRequest(BaseModel):
    tickers: List[str]
    weights: Optional[List[float]] = None
    initial_capital: float = 10000.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class PortfolioBacktestResponse(BaseModel):
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    volatility_pct: float
    equity_curve: List[dict]
    allocation: List[dict]

class OptimizePortfolioPayload(BaseModel):
    tickers: List[str]
    capital: float = 10000.0

class OptimizeParamsPayload(BaseModel):
    ticker: str
    initial_capital: float = 10000.0

# ─── System ───────────────────────────────────────────────────────────────────
class SystemSettingsPayload(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None

class SystemLogResponse(BaseModel):
    id: int
    level: str
    source: str
    message: str
    timestamp: str

class OrderPayload(BaseModel):
    account_id: str
    ticker: str
    action: str
    quantity: float
    order_type: str = "MARKET"
    price: Optional[float] = None
