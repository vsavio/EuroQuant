import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from sqlalchemy import text
from database import SessionLocal
from config import OLLAMA_HOST, V2TX_THRESHOLD, USE_DEEP_LEARNING, USE_REINFORCEMENT_LEARNING
from nlp import calculate_decayed_sentiment
from ml_engine import train_and_predict_direction
from external_ratings import fetch_external_ratings

# Optional experimental engines
try:
    from dl_engine import train_and_predict_dl
except ImportError:
    train_and_predict_dl = None

try:
    from rl_engine import train_rl_agent
except ImportError:
    train_rl_agent = None

# Structured JSON logger
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
log = logging.getLogger("recommender")

# ─── Ollama Health-Check ──────────────────────────────────────────────────────
# Checked once per pipeline run. If Ollama is offline we skip it immediately
# instead of wasting 30s per ticker in connection timeouts.
_ollama_available: bool = False

def check_ollama_health() -> bool:
    """Ping Ollama. Returns True if the service is up and responsive."""
    global _ollama_available
    try:
        r = requests.get(OLLAMA_HOST, timeout=3)
        _ollama_available = r.status_code == 200
    except Exception:
        _ollama_available = False
    if not _ollama_available:
        log.warning(json.dumps({"event": "ollama_offline", "host": OLLAMA_HOST,
                                 "msg": "Ollama unreachable — skipping for this pipeline run"}))
    else:
        log.info(json.dumps({"event": "ollama_online", "host": OLLAMA_HOST}))
    return _ollama_available


def get_latest_price_metrics(ticker, db):
    """Retrieves the latest two stock price records for a ticker to calculate metrics."""
    query = text("""
        SELECT close, open, high, low, volume, rsi, macd, macd_signal, sma_20, sma_50, sma_200, timestamp, adx, atr
        FROM stock_prices
        WHERE ticker = :ticker
        ORDER BY timestamp DESC
        LIMIT 2
    """)
    rows = db.execute(query, {"ticker": ticker}).fetchall()
    
    if not rows:
        return None
        
    latest = rows[0]
    prev = rows[1] if len(rows) > 1 else None
    
    price_change_pct = 0.0
    if prev and prev[0] and latest[0]:
        price_change_pct = float((latest[0] - prev[0]) / prev[0]) * 100.0
        
    # Calculate baseline ATR for volatility lot sizing
    baseline_query = text("""
        SELECT AVG(atr) FROM (
            SELECT atr FROM stock_prices 
            WHERE ticker = :ticker AND atr IS NOT NULL
            ORDER BY timestamp DESC 
            LIMIT 100
        ) sub
    """)
    baseline_atr = db.execute(baseline_query, {"ticker": ticker}).scalar()
    
    current_atr = float(latest[13]) if (len(latest) > 13 and latest[13] is not None) else None
    if baseline_atr and current_atr and current_atr > 0:
        import numpy as np
        volatility_lot_sizing = float(np.clip(float(baseline_atr) / current_atr, 0.25, 2.0))
    else:
        volatility_lot_sizing = 1.0
        
    vwap_query = text("""
        SELECT SUM(close * volume) / NULLIF(SUM(volume), 0)
        FROM (
            SELECT close, volume FROM stock_prices 
            WHERE ticker = :ticker AND close IS NOT NULL AND volume IS NOT NULL
            ORDER BY timestamp DESC 
            LIMIT 20
        ) sub
    """)
    vwap_20d = db.execute(vwap_query, {"ticker": ticker}).scalar()

    return {
        "close": float(latest[0]) if latest[0] else None,
        "open": float(latest[1]) if latest[1] else None,
        "high": float(latest[2]) if latest[2] else None,
        "low": float(latest[3]) if latest[3] else None,
        "volume": int(latest[4]) if latest[4] else None,
        "rsi": float(latest[5]) if latest[5] else None,
        "macd": float(latest[6]) if latest[6] else None,
        "macd_signal": float(latest[7]) if latest[7] else None,
        "sma_20": float(latest[8]) if latest[8] else None,
        "sma_50": float(latest[9]) if latest[9] else None,
        "sma_200": float(latest[10]) if latest[10] else None,
        "timestamp": latest[11],
        "adx": float(latest[12]) if (len(latest) > 12 and latest[12] is not None) else None,
        "atr": current_atr,
        "volatility_lot_sizing": volatility_lot_sizing,
        "price_change_24h": price_change_pct,
        "vwap_20d": float(vwap_20d) if vwap_20d else None
    }

def get_latest_v2tx_from_db(db):
    """Retrieves the latest V2TX volatility index value from the database."""
    query = text("""
        SELECT close FROM stock_prices
        WHERE ticker = '^V2TX'
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = db.execute(query).fetchone()
    return float(row[0]) if row else 20.0 # Default to 20 if not found

def get_top_news_for_company(ticker, db, limit=3):
    """Retrieves the top recent news articles for a company."""
    query = text("""
        SELECT a.title, a.source, a.sentiment_label, a.sentiment_score, a.published_date
        FROM news_articles a
        JOIN news_company_mappings m ON a.id = m.article_id
        WHERE m.company_ticker = :ticker
        ORDER BY a.published_date DESC
        LIMIT :limit
    """)
    rows = db.execute(query, {"ticker": ticker, "limit": limit}).fetchall()
    return [
        {
            "title": r[0],
            "source": r[1],
            "sentiment": r[2],
            "score": float(r[3]) if r[3] else 0.0,
            "date": r[4].strftime("%Y-%m-%d %H:%M")
        } for r in rows
    ]

def query_gemini_recommendation(ticker, company_name, metrics, sentiment, news, v2tx, ml_prob, rl_action, prompt):
    """
    Queries Google Gemini API as a high-reliability fallback if local Ollama fails.
    """
    import os
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
        
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            res_data = response.json()
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            data = json.loads(raw_text)
            
            rating = data.get("rating", "HOLD").upper()
            if rating not in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
                rating = "HOLD"
                
            return {
                "step_by_step_reasoning": data.get("step_by_step_reasoning", ""),
                "rating": rating,
                "reason_macro": data.get("reason_macro", ""),
                "reason_micro": data.get("reason_micro", ""),
                "reason_technical": data.get("reason_technical", "")
            }
        else:
            print(f"Gemini API fallback failed for {ticker}: HTTP {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Gemini API fallback failed for {ticker}: {e}")
def query_llm_recommendation(ticker, company_name, metrics, sentiment, news, v2tx, ml_prob, rl_action, alt_data=None, ext_ratings=None):
    """
    Constructs prompt and queries LLM for financial rating and reasons.
    Primary: Google Gemini API
    Fallback: Local Ollama
    """
    news_str = "\n".join([f"- [{n['source']}] {n['title']} (Sentiment: {n['sentiment']} / Score: {n['score']})" for n in news])
    
    rsi_state = "Neutral"
    if metrics.get("rsi"):
        if metrics["rsi"] > 70:
            rsi_state = "Overbought (Ipercomprato)"
        elif metrics["rsi"] < 30:
            rsi_state = "Oversold (Ipervenduto)"
            
    adx_val = metrics.get("adx")
    adx_str = f"{adx_val:.2f}" if adx_val is not None else "N/A"
    adx_desc = "(Trend Forte)" if (adx_val is not None and adx_val > 25) else "(Trend Debole / Range)"
    
    rsi_val = metrics.get("rsi")
    rsi_str = f"{rsi_val:.2f}" if rsi_val is not None else "N/A"
    
    macd_val = metrics.get("macd")
    macd_str = f"{macd_val:.4f}" if macd_val is not None else "N/A"
    
    macd_signal_val = metrics.get("macd_signal")
    macd_signal_str = f"{macd_signal_val:.4f}" if macd_signal_val is not None else "N/A"
    
    price_change = metrics.get("price_change_24h")
    price_change_str = f"{price_change:.2f}" if price_change is not None else "N/A"
    
    v2tx_str = f"{v2tx:.2f}"
    
    alt_data_str = ""
    if alt_data:
        pcr = alt_data.get('put_call_ratio', 'N/A')
        dpi = alt_data.get('dark_pool_index', 'N/A')
        gnn = alt_data.get('gnn_contagio', 'N/A')
        alt_data_str = f"""- Alternative Data (Microstructure & Graph AI):
  * Options Put/Call Ratio: {pcr} (Higher = Bearish/Hedging)
  * Dark Pool Index (DPI): {dpi} (Higher = Institutional Accumulation)
  * Sector GNN Contagion Score: {gnn} (Positive = Sector Rally, Negative = Sector Crash)"""

    ext_ratings_str = ""
    if ext_ratings:
        ext_ratings_str = f"""- External Institutional Ratings:
  * Wall Street Consensus (Yahoo Finance): {ext_ratings.get('yfinance_analysts', 'N/A')}
  * Technical Consensus (TradingView): {ext_ratings.get('tradingview', 'N/A')}"""

    prompt = f"""You are a senior institutional quantitative & financial analyst.
Analyze the following asset data and news:
 
Asset: {company_name} ({ticker})
- Current Price: € {metrics.get('close')} (24h Change: {price_change_str}%)
{ext_ratings_str}
- Technical Indicators:
  * RSI (14): {rsi_str} (State: {rsi_state})
  * ADX (14) Trend Strength: {adx_str} {adx_desc}
  * MACD: {macd_str} (Signal Line: {macd_signal_str})
  * SMA 50: € {metrics.get('sma_50')}
  * SMA 200: € {metrics.get('sma_200')}
- Aggregated Sentiment (24h-48h Decayed): {sentiment:.4f}
- Machine Learning Predictive Probability (Long): {ml_prob * 100:.2f}%
- VSTOXX Volatility Index (V2TX): {v2tx_str}
{alt_data_str}

Provide a FINAL investment rating: STRONG BUY, BUY, HOLD, SELL, STRONG SELL.
ACT AS AN ARBITER: Strongly consider the External Institutional Ratings (Yahoo/TradingView). Use the other data to confirm or deny their consensus. Keep your reasoning EXTREMELY brief.

MANDATORY ML VETO RULES (you MUST follow these, they override everything else):
- If ML Probability (Long) < 35%: rating CANNOT be STRONG BUY. Maximum allowed: BUY.
- If ML Probability (Long) < 20%: rating CANNOT be BUY or STRONG BUY. Maximum allowed: HOLD.
- If ML Probability (Long) > 65%: rating CANNOT be STRONG SELL. Minimum allowed: SELL.
- If ML Probability (Long) > 80%: rating CANNOT be SELL or STRONG SELL. Minimum allowed: HOLD.
- If ML Probability (Long) is between 40% and 60%: prefer HOLD unless external ratings strongly agree on BUY or SELL.

You MUST respond ONLY with a valid JSON object in Italian matching this schema:
{{
  "step_by_step_reasoning": "Massimo 2 frasi. Conferma o smentisci il consensus esterno basandoti su metriche interne (ML, Dark Pool).",
  "rating": "STRONG BUY/BUY/HOLD/SELL/STRONG SELL",
  "reason_macro": "Sintesi macro",
  "reason_micro": "Sintesi micro/news",
  "reason_technical": "Sintesi tecnica"
}}

Do not write any text outside of the JSON block. Do not include markdown code ticks.
"""

    # 1. Try Gemini API First
    gemini_res = query_gemini_recommendation(ticker, company_name, metrics, sentiment, news, v2tx, ml_prob, rl_action, prompt)
    if gemini_res:
        print(f"Gemini API successful for {ticker}.")
        return gemini_res

    # 2. Fallback to Ollama (Local) — only if health-check passed
    if _ollama_available:
        try:
            url = f"{OLLAMA_HOST}/api/generate"
            payload = {
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "num_thread": 4,
                    "num_predict": 600
                }
            }
            
            response = requests.post(url, json=payload, timeout=600)
            if response.status_code == 200:
                res_data = response.json()
                raw_text = res_data.get("response", "").strip()
                data = json.loads(raw_text)
                
                rating = data.get("rating", "HOLD").upper()
                if rating not in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
                    rating = "HOLD"
                    
                print(f"Ollama local fallback successful for {ticker}.")
                return {
                    "step_by_step_reasoning": data.get("step_by_step_reasoning", ""),
                    "rating": rating,
                    "reason_macro": data.get("reason_macro", ""),
                    "reason_micro": data.get("reason_micro", ""),
                    "reason_technical": data.get("reason_technical", "")
                }
        except Exception as e:
            print(f"Ollama recommendation failed for {ticker}: {e}.")
        
    # 3. Final Rule-based Fallback
    print(f"All LLM backends failed for {ticker}. Running rule-based logic.")
    return generate_rule_based_fallback(ticker, company_name, metrics, sentiment, news, v2tx)

def generate_rule_based_fallback(ticker, company_name, metrics, sentiment, news, v2tx):
    """Generates a professional rule-based recommendation when LLM fails or is capped."""
    rsi = metrics.get("rsi") or 50.0
    macd = metrics.get("macd") or 0.0
    macd_sig = metrics.get("macd_signal") or 0.0
    
    # Simple quant logic
    if rsi < 30 or (rsi < 40 and macd > macd_sig):
        rating = "BUY"
        status_it = "ipervenduto o in ripresa"
    elif rsi > 70 or (rsi > 60 and macd < macd_sig):
        rating = "SELL"
        status_it = "ipercomprato o in flessione"
    else:
        rating = "HOLD"
        status_it = "in fase neutrale"
        
    reason_macro = "L'analisi quantitativa indica una stabilizzazione dei mercati europei, con volatilità in linea con le medie storiche."
    reason_micro = f"L'asset {company_name} mostra un sentiment complessivo di {sentiment:.2f} con scambi regolari sui mercati principali."
    reason_technical = f"L'RSI a {rsi:.2f} indica una condizione {status_it}. Le medie SMA 20 (€ {metrics.get('sma_20')}) e SMA 50 (€ {metrics.get('sma_50')}) confermano il trend."
    
    return {
        "rating": rating,
        "reason_macro": reason_macro,
        "reason_micro": reason_micro,
        "reason_technical": reason_technical
    }

def _process_single_company(comp, v2tx, db_url):
    """
    Processes a single company: fetches metrics, sentiment, news,
    calls LLM, and saves the recommendation to the database.
    Runs in a worker thread with its own DB session.
    """
    from database import SessionLocal as _SessionLocal
    ticker, name = comp
    db = _SessionLocal()
    try:
        # 1. Fetch latest price metrics & indicators
        metrics = get_latest_price_metrics(ticker, db)
        if not metrics or metrics["close"] is None:
            log.warning(json.dumps({"ticker": ticker, "event": "skipped", "reason": "no price data"}))
            return None

        # 2. Fetch decayed sentiment
        sentiment_score = calculate_decayed_sentiment(ticker, db)

        # 3. Fetch recent news
        news = get_top_news_for_company(ticker, db)

        # 4. Generate Machine Learning Predictions BEFORE LLM
        rl_action = "N/A"
        try:
            ml_prob = train_and_predict_direction(ticker, db)
            
            if USE_DEEP_LEARNING and train_and_predict_dl is not None:
                dl_prob = train_and_predict_dl(ticker, db)
                ml_prob = (ml_prob + dl_prob) / 2.0  # Ensemble blending
                log.info(json.dumps({"ticker": ticker, "event": "ml_ensemble_computed", "gb_prob": round(ml_prob*2-dl_prob, 4), "lstm_prob": round(dl_prob, 4), "final_prob": round(ml_prob, 4)}))
            else:
                log.info(json.dumps({"ticker": ticker, "event": "ml_prob_computed", "prob": round(ml_prob, 4)}))
                
            if USE_REINFORCEMENT_LEARNING and train_rl_agent is not None:
                try:
                    rl_action = train_rl_agent(ticker, db)
                    log.info(json.dumps({"ticker": ticker, "event": "rl_computed", "action": rl_action}))
                except Exception as rl_err:
                    log.warning(json.dumps({"ticker": ticker, "event": "rl_failed", "error": str(rl_err)}))
        except Exception as ml_err:
            log.warning(json.dumps({"ticker": ticker, "event": "ml_failed", "error": str(ml_err)}))
            ml_prob = 0.50

        # 4.5 Fetch Alternative Data (if available)
        alt_data = {}
        try:
            opt = db.execute(text("SELECT put_call_ratio FROM options_flow WHERE ticker = :t ORDER BY timestamp DESC LIMIT 1"), {"t": ticker}).fetchone()
            if opt: alt_data['put_call_ratio'] = float(opt[0])
            
            dp = db.execute(text("SELECT institutional_buy_pct FROM dark_pool_prints WHERE ticker = :t ORDER BY timestamp DESC LIMIT 1"), {"t": ticker}).fetchone()
            if dp: alt_data['dark_pool_index'] = float(dp[0])
            
            gn = db.execute(text("SELECT gnn_contagio FROM recommendations WHERE ticker = :t"), {"t": ticker}).fetchone()
            if gn and gn[0] is not None: alt_data['gnn_contagio'] = float(gn[0])
        except Exception:
            pass

        # 4.6 Fetch External Ratings
        ext_ratings = fetch_external_ratings(ticker)
        log.info(json.dumps({"ticker": ticker, "event": "ext_ratings_fetched", "ratings": ext_ratings}))

        # 5. Generate LLM recommendation (with Gemini fallback + rule-based)
        log.info(json.dumps({"ticker": ticker, "event": "llm_start"}))
        rec_data = query_llm_recommendation(ticker, name, metrics, sentiment_score, news, v2tx, ml_prob, rl_action, alt_data, ext_ratings)

        # 6. ML Veto — Hard-coded validation (overrides LLM if needed)
        final_rating = rec_data["rating"]
        original_rating = final_rating
        if ml_prob < 0.20 and final_rating in ["STRONG BUY", "BUY"]:
            final_rating = "HOLD"
            log.warning(json.dumps({"ticker": ticker, "event": "ml_veto", "from": original_rating, "to": final_rating, "ml_prob": ml_prob, "rule": "ml_prob<20%"}))
        elif ml_prob < 0.35 and final_rating == "STRONG BUY":
            final_rating = "BUY"
            log.warning(json.dumps({"ticker": ticker, "event": "ml_veto", "from": original_rating, "to": final_rating, "ml_prob": ml_prob, "rule": "ml_prob<35%"}))
        elif ml_prob > 0.80 and final_rating in ["STRONG SELL", "SELL"]:
            final_rating = "HOLD"
            log.warning(json.dumps({"ticker": ticker, "event": "ml_veto", "from": original_rating, "to": final_rating, "ml_prob": ml_prob, "rule": "ml_prob>80%"}))
        elif ml_prob > 0.65 and final_rating == "STRONG SELL":
            final_rating = "SELL"
            log.warning(json.dumps({"ticker": ticker, "event": "ml_veto", "from": original_rating, "to": final_rating, "ml_prob": ml_prob, "rule": "ml_prob>65%"}))

        # 7. Risk Management: V2TX check
        macro_reason = rec_data["reason_macro"]

        if v2tx > V2TX_THRESHOLD:
            if final_rating in ["BUY", "STRONG BUY"]:
                log.warning(json.dumps({"ticker": ticker, "event": "downgraded", "v2tx": v2tx, "from": final_rating}))
                final_rating = "HOLD"
            risk_msg = f"[RISCHIO SISTEMICO ELEVATO: VSTOXX a {v2tx:.2f} sopra la soglia di guardia di {V2TX_THRESHOLD}. Nuovi acquisti bloccati.] "
            macro_reason = risk_msg + macro_reason

        full_reason = f"Macro:\n{macro_reason}\n\nMicro:\n{rec_data['reason_micro']}\n\nTechnical:\n{rec_data['reason_technical']}"
        
        # Inserisci il CoT (Chain of Thought) reasoning se disponibile
        if rec_data.get("step_by_step_reasoning"):
            full_reason = f"AI Reasoning:\n{rec_data['step_by_step_reasoning']}\n\n" + full_reason

        # 7. Read previous signal for alert comparison
        prev_row = db.execute(
            text("SELECT signal FROM recommendations WHERE ticker = :ticker"),
            {"ticker": ticker}
        ).fetchone()
        prev_signal = prev_row[0] if prev_row else None
            
        if USE_REINFORCEMENT_LEARNING and rl_action != "N/A":
            full_reason += f"\n\nRL Agent (DQN): {rl_action}"

        # 8. Persist to database
        db.execute(
            text("""
                INSERT INTO recommendations (ticker, timestamp, signal, sentiment_score, price_change_24h,
                    reason_macro, reason_micro, reason_technical, full_reason, adx, atr, volatility_lot_sizing, ml_prediction_prob)
                VALUES (:ticker, :timestamp, :signal, :sentiment_score, :price_change_24h,
                    :reason_macro, :reason_micro, :reason_technical, :full_reason, :adx, :atr, :volatility_lot_sizing, :ml_prediction_prob)
                ON CONFLICT (ticker) DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    signal = EXCLUDED.signal,
                    sentiment_score = EXCLUDED.sentiment_score,
                    price_change_24h = EXCLUDED.price_change_24h,
                    reason_macro = EXCLUDED.reason_macro,
                    reason_micro = EXCLUDED.reason_micro,
                    reason_technical = EXCLUDED.reason_technical,
                    full_reason = EXCLUDED.full_reason,
                    adx = EXCLUDED.adx,
                    atr = EXCLUDED.atr,
                    volatility_lot_sizing = EXCLUDED.volatility_lot_sizing,
                    ml_prediction_prob = EXCLUDED.ml_prediction_prob
            """),
            {
                "ticker": ticker, "timestamp": datetime.now(timezone.utc),
                "signal": final_rating, "sentiment_score": sentiment_score,
                "price_change_24h": metrics["price_change_24h"],
                "reason_macro": macro_reason, "reason_micro": rec_data["reason_micro"],
                "reason_technical": rec_data["reason_technical"], "full_reason": full_reason,
                "adx": metrics["adx"], "atr": metrics["atr"],
                "volatility_lot_sizing": metrics["volatility_lot_sizing"],
                "ml_prediction_prob": ml_prob
            }
        )
        db.execute(
            text("""
                INSERT INTO recommendation_history (ticker, timestamp, signal, sentiment_score,
                    price_change_24h, reason_technical, adx, atr, volatility_lot_sizing)
                VALUES (:ticker, :timestamp, :signal, :sentiment_score, :price_change_24h,
                    :reason_technical, :adx, :atr, :volatility_lot_sizing)
            """),
            {
                "ticker": ticker, "timestamp": datetime.now(timezone.utc),
                "signal": final_rating, "sentiment_score": sentiment_score,
                "price_change_24h": metrics["price_change_24h"],
                "reason_technical": rec_data["reason_technical"],
                "adx": metrics["adx"], "atr": metrics["atr"],
                "volatility_lot_sizing": metrics["volatility_lot_sizing"]
            }
        )
        db.commit()

        # 9. Send alerts if signal changed
        if prev_signal != final_rating:
            try:
                settings_row = db.execute(
                    text("SELECT telegram_bot_token, telegram_chat_id, discord_webhook_url FROM system_settings WHERE id = 1")
                ).fetchone()
                if settings_row:
                    from crypto_utils import decrypt_data
                    tg_token = decrypt_data(settings_row[0])
                    tg_chat = decrypt_data(settings_row[1])
                    discord_url = decrypt_data(settings_row[2])
                    msg = (f"🚨 **EuroQuant Alert: Cambio Segnale per {ticker}**\n"
                           f"- Da: `{prev_signal or 'N/A'}`\n- A: `{final_rating}`\n"
                           f"- Analisi Tecnica: {rec_data['reason_technical']}")
                    if tg_token and tg_chat:
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                json={"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"},
                                timeout=10
                            )
                        except Exception as tg_err:
                            log.warning(json.dumps({"event": "telegram_error", "error": str(tg_err)}))
                    if discord_url:
                        try:
                            requests.post(discord_url, json={"content": msg}, timeout=10)
                        except Exception as disc_err:
                            log.warning(json.dumps({"event": "discord_error", "error": str(disc_err)}))
            except Exception as alert_err:
                log.warning(json.dumps({"event": "alert_system_error", "error": str(alert_err)}))

        log.info(json.dumps({"ticker": ticker, "event": "signal_generated", "signal": final_rating}))
        return ticker
    except Exception as e:
        log.error(json.dumps({"ticker": ticker, "event": "error", "error": str(e)}))
        db.rollback()
        return None
    finally:
        db.close()


def generate_recommendations():
    """
    Scans all companies, calculates sentiment, reads prices/volatility,
    runs risk checks, and generates explainable AI recommendations
    using parallelized LLM calls (all tickers receive real AI analysis).
    """
    db = SessionLocal()
    try:
        # Get active companies (excluding Indices)
        result = db.execute(text("SELECT ticker, name FROM companies WHERE sector NOT IN ('Index', 'Forex')"))
        companies = result.fetchall()
        v2tx = get_latest_v2tx_from_db(db)
    finally:
        db.close()

    log.info(json.dumps({"event": "engine_start", "v2tx": round(v2tx, 2), "companies": len(companies)}))

    updated_count = 0
    # Parallelize LLM calls — max 2 concurrent to avoid overwhelming Ollama
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {
            executor.submit(_process_single_company, comp, v2tx, None): comp[0]
            for comp in companies
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if result:
                    updated_count += 1
            except Exception as exc:
                log.error(json.dumps({"ticker": ticker, "event": "future_error", "error": str(exc)}))

    log.info(json.dumps({"event": "engine_complete", "updated": updated_count, "total": len(companies)}))
    return updated_count

if __name__ == "__main__":
    generate_recommendations()
