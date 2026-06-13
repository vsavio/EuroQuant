from sqlalchemy import text
from database import SessionLocal

def seed_global_data():
    print("Database seeding: Running global markets insertion...")
    db = SessionLocal()
    try:
        # Seed US & Asian companies
        companies = [
            # USA
            ('AAPL', 'Apple Inc.', 'USA', 'Technology', 'Consumer Electronics', 0.95),
            ('MSFT', 'Microsoft Corporation', 'USA', 'Technology', 'Software - Infrastructure', 0.95),
            ('AMZN', 'Amazon.com, Inc.', 'USA', 'Consumer Cyclical', 'Internet Retail', 0.90),
            ('NVDA', 'NVIDIA Corporation', 'USA', 'Technology', 'Semiconductors', 0.95),
            ('GOOGL', 'Alphabet Inc.', 'USA', 'Technology', 'Internet Content & Information', 0.90),
            ('TSLA', 'Tesla, Inc.', 'USA', 'Consumer Cyclical', 'Auto Manufacturers', 0.90),
            ('META', 'Meta Platforms, Inc.', 'USA', 'Technology', 'Internet Content & Information', 0.85),
            ('JPM', 'JPMorgan Chase & Co.', 'USA', 'Financial Services', 'Banks - Diversified', 0.90),
            ('V', 'Visa Inc.', 'USA', 'Financial Services', 'Credit Services', 0.90),
            ('LLY', 'Eli Lilly and Company', 'USA', 'Healthcare', 'Drug Manufacturers - General', 0.90),
            # Japan
            ('7203.T', 'Toyota Motor Corporation', 'Japan', 'Consumer Cyclical', 'Auto Manufacturers', 0.85),
            ('9984.T', 'SoftBank Group Corp.', 'Japan', 'Technology', 'Telecom Services', 0.80),
            ('6758.T', 'Sony Group Corporation', 'Japan', 'Consumer Cyclical', 'Consumer Electronics', 0.85),
            # Hong Kong
            ('0700.HK', 'Tencent Holdings Limited', 'Hong Kong', 'Technology', 'Internet Content & Information', 0.85),
            ('9988.HK', 'Alibaba Group Holding Limited', 'Hong Kong', 'Consumer Cyclical', 'Internet Retail', 0.80),
            ('1211.HK', 'BYD Company Limited', 'Hong Kong', 'Consumer Cyclical', 'Auto Manufacturers', 0.80),
            # Taiwan
            ('2330.TW', 'Taiwan Semiconductor Manufacturing Co.', 'Taiwan', 'Technology', 'Semiconductors', 0.95),
            # South Korea
            ('005930.KS', 'Samsung Electronics Co., Ltd.', 'South Korea', 'Technology', 'Consumer Electronics', 0.90),
            # Crypto
            ('BTC-USD', 'Bitcoin', 'Crypto', 'Crypto', 'Cryptocurrency', 0.95),
            ('ETH-USD', 'Ethereum', 'Crypto', 'Crypto', 'Cryptocurrency', 0.90),
            ('XRP-USD', 'Ripple', 'Crypto', 'Crypto', 'Cryptocurrency', 0.85),
            ('SOL-USD', 'Solana', 'Crypto', 'Crypto', 'Cryptocurrency', 0.85),
            ('ADA-USD', 'Cardano', 'Crypto', 'Crypto', 'Cryptocurrency', 0.80),
            ('DOT-USD', 'Polkadot', 'Crypto', 'Crypto', 'Cryptocurrency', 0.80)
        ]
        
        for ticker, name, country, sector, industry, trust in companies:
            db.execute(text("""
                INSERT INTO companies (ticker, name, country, sector, industry, trust_score)
                VALUES (:ticker, :name, :country, :sector, :industry, :trust)
                ON CONFLICT (ticker) DO UPDATE SET
                    name = EXCLUDED.name,
                    country = EXCLUDED.country,
                    sector = EXCLUDED.sector,
                    industry = EXCLUDED.industry,
                    trust_score = EXCLUDED.trust_score
            """), {"ticker": ticker, "name": name, "country": country, "sector": sector, "industry": industry, "trust": trust})
            
        # Seed US & Asian RSS feeds
        feeds = [
            # USA
            ('CNBC Finance', 'https://search.cnbc.com/rs/search/all/view.xml?partnerId=2000&keywords=finance', 'USA', 0.90),
            ('Bloomberg Markets', 'https://www.bloomberg.com/feeds/bpol/markets.xml', 'USA', 0.90),
            ('WSJ Markets', 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml', 'USA', 0.90),
            ('MarketWatch Market', 'https://feeds.content.marketwatch.com/marketwatch/rss/marketalerts', 'USA', 0.85),
            ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex', 'USA', 0.80),
            # Asia
            ('Nikkei Asia', 'https://asia.nikkei.com/rss/feed/nar', 'Japan', 0.85),
            ('SCMP Business', 'https://www.scmp.com/rss/92/feed.xml', 'Hong Kong', 0.80),
            ('Caixin Global', 'https://www.caixinglobal.com/rss/', 'China', 0.80),
            ('Channel NewsAsia Business', 'https://www.channelnewsasia.com/api/v1/rss-outbound-feed?category=6911', 'Singapore', 0.80),
            # Crypto
            ('CoinDesk Feed', 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'Crypto', 0.85),
            ('Cointelegraph Feed', 'https://cointelegraph.com/rss', 'Crypto', 0.85),
            ('Decrypt Feed', 'https://decrypt.co/feed', 'Crypto', 0.80)
        ]
        
        for source, url, country, trust in feeds:
            db.execute(text("""
                INSERT INTO rss_feeds (source_name, feed_url, country, trust_score)
                VALUES (:source, :url, :country, :trust)
                ON CONFLICT (feed_url) DO UPDATE SET
                    source_name = EXCLUDED.source_name,
                    country = EXCLUDED.country,
                    trust_score = EXCLUDED.trust_score
            """), {"source": source, "url": url, "country": country, "trust": trust})
            
        db.commit()
        print("Database seeding: Global markets successfully upserted.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_global_data()
