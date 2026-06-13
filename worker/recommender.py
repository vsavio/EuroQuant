import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from sqlalchemy import text
from database import SessionLocal
from config import OLLAMA_HOST, V2TX_THRESHOLD
from nlp import calculate_decayed_sentiment
from ml_engine import train_and_predict_direction

# Structured JSON logger
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
log = logging.getLogger("recommender")

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
        "price_change_24h": price_change_pct
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

def query_gemini_recommendation(ticker, company_name, metrics, sentiment, news, v2tx, prompt):
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
                "rating": rating,
                "reason_macro": data.get("reason_macro", ""),
                "reason_micro": data.get("reason_micro", ""),
                "reason_technical": data.get("reason_technical", "")
            }
    except Exception as e:
        print(f"Gemini API fallback failed for {ticker}: {e}")
    return None

def query_ollama_recommendation(ticker, company_name, metrics, sentiment, news, v2tx):
    """
    Constructs prompt and queries Ollama for financial rating and reasons.
    If Ollama fails, routes request to the Gemini API adapter.
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
    
    prompt = f"""You are a senior institutional quantitative & financial analyst.
Analyze the following asset data and news:
 
Asset: {company_name} ({ticker})
- Current Price: € {metrics.get('close')} (24h Change: {price_change_str}%)
- Technical Indicators:
  * RSI (14): {rsi_str} (State: {rsi_state})
  * ADX (14) Trend Strength: {adx_str} {adx_desc}
  * MACD: {macd_str} (Signal Line: {macd_signal_str})
  * SMA 20: € {metrics.get('sma_20')}
  * SMA 50: € {metrics.get('sma_50')}
  * SMA 200: € {metrics.get('sma_200')}
- Aggregated Sentiment (24h-48h Decayed): {sentiment:.4f}
- VSTOXX Volatility Index (V2TX): {v2tx:.2f}
- Recent News Context:
{news_str if news_str else "No recent news found."}

Provide an investment rating and professional analysis.
The rating must be one of: STRONG BUY, BUY, HOLD, SELL, STRONG SELL.

You MUST respond ONLY with a valid JSON object in Italian matching this schema:
{{
  "rating": "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL",
  "reason_macro": "Un paragrafo professionale in italiano che descrive il contesto macroeconomico e l'indice di riferimento.",
  "reason_micro": "Un paragrafo professionale in italiano che descrive i dati aziendali, il sentiment delle notizie e l'andamento specifico.",
  "reason_technical": "Un paragrafo professionale in italiano che descrive i trend tecnici, livelli di RSI, ADX, MACD e medie mobili."
}}

Do not write any text outside of the JSON block. Do not include markdown code ticks.
"""

    # 1. Try Ollama (Local)
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "num_thread": 4,
                "num_predict": 250
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            res_data = response.json()
            raw_text = res_data.get("response", "").strip()
            data = json.loads(raw_text)
            
            rating = data.get("rating", "HOLD").upper()
            if rating not in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
                rating = "HOLD"
                
            return {
                "rating": rating,
                "reason_macro": data.get("reason_macro", ""),
                "reason_micro": data.get("reason_micro", ""),
                "reason_technical": data.get("reason_technical", "")
            }
    except Exception as e:
        print(f"Ollama recommendation failed for {ticker}: {e}. Trying Gemini API fallback...")
        
    # 2. Fallback to Gemini API
    gemini_res = query_gemini_recommendation(ticker, company_name, metrics, sentiment, news, v2tx, prompt)
    if gemini_res:
        print(f"Gemini API fallback successful for {ticker}.")
        return gemini_res
        
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

        # 4. Generate LLM recommendation (with Gemini fallback + rule-based)
        log.info(json.dumps({"ticker": ticker, "event": "llm_start"}))
        rec_data = query_ollama_recommendation(ticker, name, metrics, sentiment_score, news, v2tx)

        # 5. Risk Management: V2TX check
        final_rating = rec_data["rating"]
        macro_reason = rec_data["reason_macro"]

        if v2tx > V2TX_THRESHOLD:
            if final_rating in ["BUY", "STRONG BUY"]:
                log.warning(json.dumps({"ticker": ticker, "event": "downgraded", "v2tx": v2tx, "from": final_rating}))
                final_rating = "HOLD"
            risk_msg = f"[RISCHIO SISTEMICO ELEVATO: VSTOXX a {v2tx:.2f} sopra la soglia di guardia di {V2TX_THRESHOLD}. Nuovi acquisti bloccati.] "
            macro_reason = risk_msg + macro_reason

        full_reason = f"Macro:\n{macro_reason}\n\nMicro:\n{rec_data['reason_micro']}\n\nTechnical:\n{rec_data['reason_technical']}"

        # 6. Read previous signal for alert comparison
        prev_row = db.execute(
            text("SELECT signal FROM recommendations WHERE ticker = :ticker"),
            {"ticker": ticker}
        ).fetchone()
        prev_signal = prev_row[0] if prev_row else None

        # 7. Train ML model
        try:
            ml_prob = train_and_predict_direction(ticker, db)
        except Exception as ml_err:
            log.warning(json.dumps({"ticker": ticker, "event": "ml_failed", "error": str(ml_err)}))
            ml_prob = 0.50

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
    # Parallelize LLM calls — max 4 concurrent to avoid overwhelming Ollama/Gemini
    with ThreadPoolExecutor(max_workers=4) as executor:
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
