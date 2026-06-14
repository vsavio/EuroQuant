# EuroQuant: Professional Algorithmic Trading Bridge & Web Dashboard

EuroQuant is a containerized, institutional-grade algorithmic trading ecosystem that bridges local AI news sentiment, advanced quantitative indicators, real-time market telemetry, and **MetaTrader 5 (MT5)** client accounts.

By combining real-time news scraping, semantic text clustering, local Hugging Face embedding models, local LLM sentiment inference, and classic quantitative indicators, EuroQuant produces optimized trade signals. Local MetaTrader 5 Expert Advisors (EAs) poll these signals and execute orders autonomously. The system features a premium Web Terminal dashboard built with Next.js and Tailwind, offering real-time telemetry updates, backtesting simulations, manual override controls, and centralized emergency risk management.

---

## 🛠️ System Architecture

```mermaid
graph TD
    A[Next.js Web Dashboard] <-->|REST API & WebSockets| B(FastAPI Backend)
    C[MetaTrader 5 Client EA] <-->|REST API & Telemetry Sync| B
    B <-->|PostgreSQL| D[(EuroQuant DB)]
    E[Worker Sync Pipeline] -->|Writes Recommendations| D
    E -->|Queries Quotes & Indicators| D
    E <-->|Local Embeddings| F[HuggingFace sentence-transformers]
    E <-->|Local Inference| G[Ollama AI Engine]
    E -->|Scrapes News Feeds| H[Yahoo Finance / RSS Sources]
```

The ecosystem is split into 5 core services:
1. **Frontend (`frontend/`)**: A Next.js Web Terminal styled with a high-fidelity terminal developer aesthetic. Includes chart indicators (Bollinger Bands, RSI, MACD, SMAs), backtest parameter configuration, manual override triggers, dynamic Asset Config, and a real-time WebSocket connection.
2. **Backend (`backend/`)**: A FastAPI ASGI gateway managing live client connections, active signal endpoints, overrides, asset management APIs, broker account telemetry sync, and WebSocket telemetry broadcasts.
3. **Database (`db/`)**: A PostgreSQL instance initialized with schemas for stock prices, news articles, recommendation logs, manual overrides, dynamic companies/tickers, and MT5 broker account telemetry.
4. **Worker Pipeline (`worker/`)**: A Python background orchestrator that scrapes financial feeds, clusters similar/duplicate news using a local Hugging Face embedding model, evaluates technical indicators, queries systemic risk, uses Ollama for sentiment analysis, and persists recommendation logs.
5. **MetaTrader 5 EA (`mt5_ea/`)**: MQL5 Expert Advisors (`EuroQuant_MultiSymbol_Bridge.mq5`) that poll the FastAPI backend, report broker account telemetry, resolve symbol suffixes dynamically, and execute orders with advanced Break-Even logic and dynamic ATR-based Trailing Stops.

---

## ✨ Enterprise Upgrades & Features

### 1. Dynamic Asset Management
The frontend includes a self-service **Asset Config** dashboard:
*   Activate or deactivate assets (Equities, Indices, Crypto) dynamically without restarting containers.
*   The backend and worker nodes immediately respect the asset status (`is_active` flag), isolating disabled symbols from scraping and inference cycles.
*   Provides an intuitive form to seamlessly add new symbols (e.g., `NFLX`, `BTCUSD`) bridging them directly to the MT5 Terminal.

### 2. Advanced EA Risk Management (Break-Even & Trailing Stop)
The MT5 Multi-Symbol EA employs robust institutional safeguards:
*   **Two-Stage Profit Protection**: Incorporates a Smart Break-Even system that first snaps the Stop Loss to the entry price once a specific profit margin (configured via ATR) is achieved, securing the trade.
*   **ATR-Based Dynamic Trailing Stop**: Once break-even is secured, the EA trails the price at an adaptive distance derived from daily Average True Range (ATR) to avoid premature exits on volatile assets like Bitcoin.
*   **Fail-Safe Error Logging**: Comprehensive fallback logic captures all MT5 native error codes (`GetLastError()`) mapping execution failures for deep visibility.

### 3. Server-side Backtesting Engine
The backtesting simulator runs entirely on the Python backend (`/api/backtest`). It evaluates trading performance across 250 daily periods by correlating historical price data, RSI indicators, and historical news sentiment scores. It computes key quantitative performance metrics including:
*   **Total return %** and **Benchmark buy-and-hold return %**
*   **Max Drawdown %**
*   **Sharpe Ratio** (annualized based on 252 trading days)
*   **Win Rate %**

### 4. Real-Time WebSockets Communication Channel
The system establishes a full-duplex WebSocket connection (`/ws/telemetry`) between the web browser, the FastAPI backend, and the background worker. Whenever an EA checks in with telemetry or a manual override is engaged, the backend broadcasts a message. The React frontend immediately triggers a re-fetch of account balances, open positions, and active signals, rendering changes instantly.

### 5. Local Embeddings & News Clustering (Worker NLP)
To prevent duplicate stories from cluttering the dashboard and wasting local LLM resources, the background worker utilizes the **`sentence-transformers/all-MiniLM-L6-v2`** model. 
*   Scraped headlines are embedded locally on CPU/GPU.
*   Cosine similarity is computed for all unprocessed stories.
*   Stories with a similarity score $> 0.78$ are grouped.
*   Duplicate child articles share the parent's LLM sentiment score and ticker mapping, saving API/Ollama call latency.

### 6. Centralized Risk Control & Emergency Kill Switch
Centralized risk features protect capital from market anomalies:
*   **Aggregate Drawdown Check**: The backend automatically sums the balance and equity across all active MT5 accounts. If the aggregate drawdown exceeds the user-defined limit, a global risk state is triggered.
*   **Emergency Kill-Switch**: A global toggle on the dashboard allows immediate manual suspension of all trading.
*   **Downstream EA Close All**: When either risk limit is breached or the kill-switch is activated, all symbol signals are overridden with the `CLOSE_ALL` action. The downstream Expert Advisors pick up this status within their polling cycle, immediately close all open trades, and abort new order entry.

### 7. Compliance Audit Log (Security Trail)
An immutable ledger tracking security-critical events:
*   **User Action Logging**: Stores login success/failure, administrative overrides, VSTOXX threshold changes, and manual signal execution.
*   **SQL Persistence**: Saved in PostgreSQL table `audit_log` with IP addresses, timestamps, and JSON-formatted modification payloads.
*   **Web Console**: Accessible via the `🔐 Compliance Audit` tab in the web terminal for administrators.

---

## 🚀 Getting Started

### Prerequisites
*   Docker & Docker Compose.
*   MetaTrader 5 terminal installed on a Windows host or Wine on Linux.
*   Ollama running locally with the `llama3` model pulled:
    ```bash
    ollama pull llama3
    ```

### 1. Setup Environment
Clone the repository and inspect the configurations in `docker-compose.yml`. Ensure your `.env` contains the proper secret keys. You can customize the news scrape loop interval and local Ollama endpoint using the environment variables in the `worker` service block:
```yaml
LOOP_INTERVAL_HOURS: 1  # Scraping frequency
OLLAMA_HOST: "http://host.docker.internal:11434" # Host Ollama address
DISABLE_FINBERT: "true" # Forces fallback to Ollama/Llama3 for reasoning
```

### 2. Launch the Services
Start the backend, frontend, database, and background worker containers:
```bash
sudo docker compose up -d --build
```
Verify all containers are up and healthy:
```bash
sudo docker compose ps
```

*   **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
*   **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📈 MetaTrader 5 EA Configuration

To connect MetaTrader 5 to your local EuroQuant server:

1. Open MetaTrader 5.
2. Go to **Tools** > **Options** > **Expert Advisors**.
3. Check **Allow WebRequest for listed URL** and add:
   ```text
   http://localhost:8000
   http://127.0.0.1:8000
   ```
4. Copy `EuroQuant_MultiSymbol_Bridge.mq5` into your MT5 directory:
   `MQL5/Experts/`
5. Compile the EA and attach it to your desired chart.
6. Configure the inputs:
   *   `InpApiUrl`: `http://localhost:8000/api/mt5/signals`
   *   `InpUseBreakEven`: Enables smart protection by trailing SL to `open_price` first.
   *   `InpBreakEvenAtrMult`: Distance multiplier defining when to trigger Break-Even.
   *   `InpMaxSpreadPercent`: Dynamic spread threshold percentage of Ask (e.g. `0.25` for 0.25%). Set to `0` to fall back to static points.

---

## 📡 API Reference

### Asset Management
*   **`GET /api/tickers`**: Fetch the list of dynamically configurable assets.
*   **`POST /api/tickers/add`**: Provision a new instrument to the pipeline.
*   **`POST /api/tickers/toggle`**: Enable/Disable scraping and trading for a specific instrument.

### MT5 Signals & Telemetry
*   **`GET /api/mt5/signals`**: Invoked by MT5 EAs to fetch active recommendation signals, entries, Stop Loss, Take Profit, and reasoning details. Automatically checks global risk drawdowns, manual overrides, and the kill switch state.
*   **`POST /api/mt5/positions`**: Submits active MT5 positions arrays to synchronize dashboard states.

### Centralized Risk Settings
*   **`GET /api/mt5/risk`**: Retrieves current risk limits, kill switch active status, and current aggregate drawdown %.
*   **`POST /api/mt5/risk`**: Update maximum allowed aggregate drawdown percentage.
*   **`POST /api/mt5/risk/kill-switch`**: Enable or disable the emergency kill switch.

### Manual Overrides
*   **`GET /api/mt5/overrides`**: Returns all currently active manual overrides.
*   **`POST /api/mt5/overrides`**: Force a manual signal for a ticker symbol.

### Compliance & AI/ML Control
*   **`GET /api/audit-log`**: Retrieves recent administrative and risk override audit trail logs.
*   **`GET /api/ml/metrics`**: Returns walk-forward validation accuracy and statistics for all trained models.
*   **`POST /api/ml/retrain`**: Triggers a background thread to initiate online model retraining across all symbol companies.

---

## 🔒 License
This repository is licensed under the MIT License. Feel free to modify and customize it for your personal trading systems.
