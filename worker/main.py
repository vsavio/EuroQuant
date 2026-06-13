import time
import sys
import json
from datetime import datetime, timezone

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
from database import init_db_connection
from scraper import scrape_feeds
from nlp import process_unprocessed_news
from quant import fetch_and_calculate_all
from recommender import generate_recommendations
from config import RUN_ONCE_AND_LOOP, LOOP_INTERVAL_HOURS

def archive_historical_data():
    print("Running database archiving routine...")
    from database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Archive stock prices older than 90 days
        db.execute(text("""
            INSERT INTO stock_prices_archive (ticker, timestamp, open, high, low, close, volume, rsi, macd, macd_signal, sma_20, sma_50, sma_200, adx, atr)
            SELECT ticker, timestamp, open, high, low, close, volume, rsi, macd, macd_signal, sma_20, sma_50, sma_200, adx, atr
            FROM stock_prices
            WHERE timestamp < NOW() - INTERVAL '90 days'
            ON CONFLICT DO NOTHING
        """))
        deleted_prices = db.execute(text("""
            DELETE FROM stock_prices
            WHERE timestamp < NOW() - INTERVAL '90 days'
        """)).rowcount
        
        # Archive news articles older than 90 days
        db.execute(text("""
            INSERT INTO news_articles_archive (id, title, content, url, source, published_date, country, sentiment_score, sentiment_label, processed, parent_article_id)
            SELECT id, title, content, url, source, published_date, country, sentiment_score, sentiment_label, processed, parent_article_id
            FROM news_articles
            WHERE published_date < NOW() - INTERVAL '90 days'
            ON CONFLICT (id) DO NOTHING
        """))
        deleted_news = db.execute(text("""
            DELETE FROM news_articles
            WHERE published_date < NOW() - INTERVAL '90 days'
        """)).rowcount
        
        db.commit()
        print(f"Archived and cleaned up {deleted_prices} price rows and {deleted_news} news rows.")
    except Exception as e:
        print(f"Error during database archiving: {e}")
        db.rollback()
    finally:
        db.close()

def run_pipeline():
    print("=========================================")
    print(f"Pipeline Execution Triggered: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=========================================")
    
    # 0. Scrape Economic Calendar
    try:
        from calendar_scraper import scrape_economic_calendar
        scrape_economic_calendar()
    except Exception as e:
        print(f"Pipeline Error in Economic Calendar Scraper: {e}")

    # 1. Scrape News
    try:
        scrape_feeds()
    except Exception as e:
        print(f"Pipeline Error in News Scraper: {e}")
        
    # 2. Process News (NER + Sentiment)
    try:
        process_unprocessed_news()
    except Exception as e:
        print(f"Pipeline Error in NLP Processor: {e}")
        
    # 3. Market Data Ingestion & Technical calculations
    try:
        fetch_and_calculate_all()
    except Exception as e:
        print(f"Pipeline Error in Quantitative Engine: {e}")

    # 3b. Classify Market Regimes
    try:
        from regimes import classify_market_regimes
        classify_market_regimes()
    except Exception as e:
        print(f"Pipeline Error in Regime Classifier: {e}")
        
    # 4. Generate Recommendations (LLM)
    try:
        generate_recommendations()
    except Exception as e:
        print(f"Pipeline Error in Recommender Engine: {e}")
        
    # 5. Archive historical data
    try:
        archive_historical_data()
    except Exception as e:
        print(f"Pipeline Error in Database Archiver: {e}")
        
    print("=========================================")
    print(f"Pipeline Execution Completed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=========================================\n")

def main():
    print("Starting EuroQuant Background Worker...")
    
    # Wait for DB to be active
    db_attempts = 0
    while not init_db_connection() and db_attempts < 10:
        print("Waiting for PostgreSQL database connection...")
        time.sleep(3)
        db_attempts += 1
        
    if db_attempts >= 10:
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
        
    print("Database connected. Creating job queue table if not exists...")
    from sqlalchemy import text
    from database import SessionLocal
    
    db = SessionLocal()
    # Run migrations to support high nominal value stocks (KRW / JPY)
    migrations = [
        "ALTER TABLE stock_prices ALTER COLUMN macd TYPE NUMERIC(15,4)",
        "ALTER TABLE stock_prices ALTER COLUMN macd_signal TYPE NUMERIC(15,4)",
        "ALTER TABLE stock_prices ALTER COLUMN adx TYPE NUMERIC(15,4)",
        "ALTER TABLE stock_prices_archive ALTER COLUMN macd TYPE NUMERIC(15,4)",
        "ALTER TABLE stock_prices_archive ALTER COLUMN macd_signal TYPE NUMERIC(15,4)",
        "ALTER TABLE stock_prices_archive ALTER COLUMN adx TYPE NUMERIC(15,4)",
        "ALTER TABLE recommendations ALTER COLUMN price_change_24h TYPE NUMERIC(15,4)",
        "ALTER TABLE recommendations ALTER COLUMN adx TYPE NUMERIC(15,4)",
        "ALTER TABLE recommendations ALTER COLUMN volatility_lot_sizing TYPE NUMERIC(15,4)",
        "ALTER TABLE recommendation_history ALTER COLUMN price_change_24h TYPE NUMERIC(15,4)",
        "ALTER TABLE recommendation_history ALTER COLUMN adx TYPE NUMERIC(15,4)",
        "ALTER TABLE recommendation_history ALTER COLUMN volatility_lot_sizing TYPE NUMERIC(15,4)"
    ]
    for mig in migrations:
        try:
            db.execute(text(mig))
            db.commit()
        except Exception:
            db.rollback()

    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                telegram_bot_token VARCHAR(255) DEFAULT '',
                telegram_chat_id VARCHAR(50) DEFAULT '',
                discord_webhook_url TEXT DEFAULT '',
                CONSTRAINT single_row CHECK (id = 1)
            )
        """))
        db.execute(text("""
            INSERT INTO system_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS job_queue (
                id SERIAL PRIMARY KEY,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_prices_archive (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                open NUMERIC(15, 4),
                high NUMERIC(15, 4),
                low NUMERIC(15, 4),
                close NUMERIC(15, 4),
                volume BIGINT,
                rsi NUMERIC(8, 4),
                macd NUMERIC(15, 4),
                macd_signal NUMERIC(15, 4),
                sma_20 NUMERIC(15, 4),
                sma_50 NUMERIC(15, 4),
                sma_200 NUMERIC(15, 4),
                adx NUMERIC(15, 4),
                atr NUMERIC(15, 4),
                archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS news_articles_archive (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                url TEXT NOT NULL,
                source VARCHAR(100) NOT NULL,
                published_date TIMESTAMP WITH TIME ZONE NOT NULL,
                country VARCHAR(50) NOT NULL,
                sentiment_score NUMERIC(5, 4),
                sentiment_label VARCHAR(20),
                processed BOOLEAN DEFAULT FALSE,
                parent_article_id INTEGER,
                archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.execute(text("ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS adx NUMERIC(15,4)"))
        db.execute(text("ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS atr NUMERIC(15,4)"))
        
        db.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS adx NUMERIC(15,4)"))
        db.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS atr NUMERIC(15,4)"))
        db.execute(text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS volatility_lot_sizing NUMERIC(15,4)"))
        
        db.execute(text("ALTER TABLE recommendation_history ADD COLUMN IF NOT EXISTS adx NUMERIC(15,4)"))
        db.execute(text("ALTER TABLE recommendation_history ADD COLUMN IF NOT EXISTS atr NUMERIC(15,4)"))
        db.execute(text("ALTER TABLE recommendation_history ADD COLUMN IF NOT EXISTS volatility_lot_sizing NUMERIC(15,4)"))
        
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS recommendation_history (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                signal VARCHAR(20) NOT NULL,
                sentiment_score NUMERIC(5, 4),
                price_change_24h NUMERIC(15, 4),
                reason_technical TEXT
            )
        """))
        db.execute(text("""
            INSERT INTO companies (ticker, name, country, sector, industry, trust_score) VALUES
            ('EURUSD=X', 'EUR/USD', 'Global', 'Forex', 'Currency', 1.00),
            ('GBPUSD=X', 'GBP/USD', 'Global', 'Forex', 'Currency', 1.00),
            ('EURGBP=X', 'EUR/GBP', 'Global', 'Forex', 'Currency', 1.00),
            ('EURJPY=X', 'EUR/JPY', 'Global', 'Forex', 'Currency', 1.00),
            ('EURCHF=X', 'EUR/CHF', 'Global', 'Forex', 'Currency', 1.00)
            ON CONFLICT (ticker) DO NOTHING
        """))
        db.commit()

        # Seed global markets (USA & Asia)
        try:
            from seed_global import seed_global_data
            seed_global_data()
        except Exception as seed_err:
            print(f"Error executing global seeding: {seed_err}")

    except Exception as e:
        print(f"Error executing db initialization: {e}")
        db.rollback()
    finally:
        db.close()
        
    print("Executing initial sync...")
    # Execute immediately on start
    run_pipeline()
    last_run_time = time.time()
    
    if RUN_ONCE_AND_LOOP:
        interval_seconds = LOOP_INTERVAL_HOURS * 3600
        print(f"Worker scheduled to run every {LOOP_INTERVAL_HOURS} hours ({interval_seconds}s) or on-demand via job_queue.")
        try:
            while True:
                # Sleep in small blocks to check queue frequently
                time.sleep(5)
                
                # Check for pending jobs in database
                db = SessionLocal()
                has_pending = False
                try:
                    job = db.execute(text("SELECT id FROM job_queue WHERE status = 'pending' LIMIT 1")).fetchone()
                    if job:
                        has_pending = True
                        # Delete the job or update status to run
                        db.execute(text("DELETE FROM job_queue WHERE id = :id"), {"id": job[0]})
                        db.commit()
                except Exception as e:
                    print(f"Error checking job queue: {e}")
                    db.rollback()
                finally:
                    db.close()
                
                current_time = time.time()
                time_since_last_run = current_time - last_run_time
                
                if has_pending:
                    print("Pending job found in queue. Triggering pipeline run...")
                    run_pipeline()
                    last_run_time = time.time()
                elif time_since_last_run >= interval_seconds:
                    print(f"Periodic interval ({LOOP_INTERVAL_HOURS}h) reached. Triggering pipeline run...")
                    run_pipeline()
                    last_run_time = time.time()
        except KeyboardInterrupt:
            print("Worker stopped by user.")
    else:
        print("Worker completed execution. Exiting.")

if __name__ == "__main__":
    main()
