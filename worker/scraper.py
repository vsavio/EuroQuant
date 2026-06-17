import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import time
from sqlalchemy import text
from database import SessionLocal
import urllib.parse

def clean_html(html_content):
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove semantic trash and noisy elements
    for element in soup(["script", "style", "meta", "noscript", "header", "footer", "nav", "aside", "form"]):
        element.extract()
        
    # Remove common trash classes/ids
    import re
    trash_patterns = re.compile(r'cookie|banner|ad-|advert|social|share|popup|newsletter|subscribe', re.I)
    for element in soup.find_all(attrs={"class": trash_patterns}):
        element.extract()
    for element in soup.find_all(attrs={"id": trash_patterns}):
        element.extract()
    # Get text
    text_content = soup.get_text(separator=" ")
    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text_content.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    return " ".join(chunk for chunk in chunks if chunk)

def parse_rss_date(entry):
    for date_key in ('published_parsed', 'created_parsed', 'updated_parsed'):
        if entry.get(date_key):
            try:
                struct = entry[date_key]
                dt = datetime(*struct[:6], tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return datetime.now(timezone.utc)

def fetch_article_text(url):
    """
    Downloads and extracts the clean text of an article using BeautifulSoup.
    We use standard request with timeout to avoid blocking.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return clean_html(response.text)
    except Exception as e:
        print(f"Error fetching text for {url}: {e}")
    return ""

def scrape_feeds():
    """
    Scrapes all RSS feeds in the database, extracts articles, and saves them.
    """
    db = SessionLocal()
    try:
        # Get active RSS feeds
        result = db.execute(text("SELECT id, source_name, feed_url, country, trust_score FROM rss_feeds"))
        feeds = result.fetchall()
        
        print(f"Starting news scraping for {len(feeds)} RSS feeds...")
        new_articles_count = 0
        
        for feed in feeds:
            feed_id, source_name, feed_url, country, trust_score = feed
            print(f"Scraping feed {source_name} ({country}) - {feed_url}")
            
            try:
                # Use feedparser
                parsed_feed = feedparser.parse(feed_url)
                
                for entry in parsed_feed.entries[:15]: # Limit to last 15 items per feed to avoid performance spikes
                    url = entry.get('link')
                    if not url:
                        continue
                    
                    # Clean the URL to avoid duplicate variations
                    parsed_url = urllib.parse.urlparse(url)
                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    
                    # Check if already in DB
                    exists = db.execute(
                        text("SELECT 1 FROM news_articles WHERE url = :url LIMIT 1"),
                        {"url": clean_url}
                    ).fetchone()
                    
                    if exists:
                        continue
                    
                    title = entry.get('title', 'No Title')
                    published_dt = parse_rss_date(entry)
                    
                    # Get summary or fallback description
                    summary = entry.get('summary', '')
                    summary_text = clean_html(summary)
                    
                    # Try to fetch full article text, fallback to summary
                    full_text = fetch_article_text(clean_url)
                    if not full_text or len(full_text) < 100:
                        full_text = summary_text if summary_text else title
                        
                    # Save to DB
                    db.execute(
                        text("""
                            INSERT INTO news_articles (title, content, url, source, published_date, country, processed)
                            VALUES (:title, :content, :url, :source, :published_date, :country, FALSE)
                        """),
                        {
                            "title": title[:255] if len(title) > 255 else title,
                            "content": full_text,
                            "url": clean_url,
                            "source": source_name,
                            "published_date": published_dt,
                            "country": country
                        }
                    )
                    new_articles_count += 1
                db.commit()
            except Exception as e:
                print(f"Failed scraping feed {feed_url}: {e}")
                db.rollback()
                
        print(f"Scraping complete. Added {new_articles_count} new articles.")
        return new_articles_count
    finally:
        db.close()

def scrape_reddit():
    """
    Scrapes alternative retail sentiment from Reddit (r/WallStreetBets, r/StockMarket).
    """
    db = SessionLocal()
    headers = {"User-Agent": "EuroQuant Bot 1.0"}
    subreddits = ["wallstreetbets", "StockMarket"]
    new_articles = 0
    
    try:
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
            print(f"Scraping Reddit: {sub}...")
            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    for post in posts:
                        pdata = post.get("data", {})
                        post_id = pdata.get("id")
                        title = pdata.get("title", "")
                        content = pdata.get("selftext", "")
                        permalink = "https://www.reddit.com" + pdata.get("permalink", "")
                        created_utc = pdata.get("created_utc")
                        
                        if not title or not created_utc:
                            continue
                            
                        # Avoid duplicates
                        exists = db.execute(
                            text("SELECT 1 FROM news_articles WHERE url = :url LIMIT 1"),
                            {"url": permalink}
                        ).fetchone()
                        
                        if exists:
                            continue
                            
                        pub_date = datetime.fromtimestamp(created_utc, timezone.utc)
                        full_text = content if content else title
                        
                        db.execute(
                            text("""
                                INSERT INTO news_articles (title, content, url, source, published_date, country, processed)
                                VALUES (:title, :content, :url, :source, :published_date, :country, FALSE)
                            """),
                            {
                                "title": title[:255],
                                "content": full_text,
                                "url": permalink,
                                "source": f"Reddit r/{sub}",
                                "published_date": pub_date,
                                "country": "Global"
                            }
                        )
                        new_articles += 1
                db.commit()
            except Exception as e:
                print(f"Reddit scrape failed for {sub}: {e}")
                db.rollback()
        print(f"Reddit scrape complete. Added {new_articles} retail posts.")
    finally:
        db.close()

if __name__ == "__main__":
    scrape_feeds()
    scrape_reddit()
