import time
import sys
from database import init_db_connection
from scraper import scrape_feeds
from nlp import process_unprocessed_news
from quant import fetch_and_calculate_all
from recommender import generate_recommendations
from config import RUN_ONCE_AND_LOOP, LOOP_INTERVAL_HOURS

def run_pipeline():
    print("=========================================")
    print(f"Pipeline Execution Triggered: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=========================================")
    
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
        
    # 4. Generate Recommendations (LLM)
    try:
        generate_recommendations()
    except Exception as e:
        print(f"Pipeline Error in Recommender Engine: {e}")
        
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
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS job_queue (
                id SERIAL PRIMARY KEY,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS recommendation_history (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                signal VARCHAR(20) NOT NULL,
                sentiment_score NUMERIC(5, 4),
                price_change_24h NUMERIC(8, 4),
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
