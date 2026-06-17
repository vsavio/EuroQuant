import re
import math
import json
import requests
from datetime import datetime, timezone
from sqlalchemy import text
from database import SessionLocal
from config import OLLAMA_HOST, SOURCE_TRUST_SCORES

import os

# Initialize FinBERT
_finbert_pipeline = None
_finbert_loaded = False
DISABLE_FINBERT = os.getenv("DISABLE_FINBERT", "false").lower() == "true"

def load_finbert():
    global _finbert_pipeline, _finbert_loaded
    if DISABLE_FINBERT:
        return False
    if _finbert_loaded:
        return True
    try:
        print("Attempting to load FinBERT model...")
        import torch
        torch.set_num_threads(1)  # Fix: Force single thread to prevent CPU lockups inside Docker
        from transformers import pipeline
        # Use CPU-safe loading with pipeline
        _finbert_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            device=-1 # force CPU
        )
        _finbert_loaded = True
        print("FinBERT loaded successfully.")
        return True
    except Exception as e:
        print(f"Failed to load FinBERT model: {e}. Falling back to Ollama.")
        _finbert_loaded = False
        return False

# Custom Mapping Dictionary for Precise NER
COMPANY_ALIASES = {
    "ENI.MI": [r"\beni\b", r"\beni spa\b"],
    "ENEL.MI": [r"\benel\b", r"\benel spa\b"],
    "ISP.MI": [r"\bintesa\b", r"\bintesa sanpaolo\b", r"\bisp\b"],
    "UCG.MI": [r"\bunicredit\b", r"\bunicredit spa\b", r"\bucg\b"],
    "STLAM.MI": [r"\bstellantis\b", r"\bstellantis nv\b", r"\bstlam\b"],
    "RACE.MI": [r"\bferrari\b", r"\brace\b"],
    "TTE.PA": [r"\btotalenergies\b", r"\btotal energies\b", r"\btte\b"],
    "MC.PA": [r"\blvmh\b", r"\blouis vuitton\b", r"\bmoet hennessy\b"],
    "SAN.PA": [r"\bsanofi\b"],
    "OR.PA": [r"\bl'oreal\b", r"\bloreal\b", r"\bor\.pa\b"],
    "SU.PA": [r"\bschneider electric\b", r"\bschneider\b"],
    "BNP.PA": [r"\bbnp paribas\b", r"\bbnp\b"],
    "SAP.DE": [r"\bsap\b", r"\bsap se\b"],
    "SIE.DE": [r"\bsiemens\b", r"\bsiemens ag\b"],
    "ALV.DE": [r"\ballianz\b", r"\ballianz se\b"],
    "DTE.DE": [r"\bdeutsche telekom\b", r"\btelekom\b"],
    "BAS.DE": [r"\bbasf\b", r"\bbasf se\b"],
    "VOW3.DE": [r"\bvolkswagen\b", r"\bvw\b", r"\bvolkswagen ag\b"],
    "IBE.MC": [r"\biberdrola\b"],
    "SAN.MC": [r"\bsantander\b", r"\bbanco santander\b"],
    "BBVA.MC": [r"\bbbva\b"],
    "TEF.MC": [r"\btelefonica\b", r"\btelefónica\b"],
    "ITX.MC": [r"\binditex\b", r"\bdesign textil\b", r"\b Zara \b"],
    "REP.MC": [r"\brepsol\b"],
    "SHEL.L": [r"\bshell\b", r"\bshell plc\b"],
    "AZN.L": [r"\bastrazeneca\b", r"\bazn\b"],
    "HSBA.L": [r"\bhsbc\b", r"\bhsbc holdings\b"],
    "ULVR.L": [r"\bunilever\b"],
    "BP.L": [r"\bbp\b", r"\bbp plc\b"],
    "GSK.L": [r"\bgsk\b", r"\bglaxosmithkline\b"]
}

def map_article_to_tickers(title, content):
    """
    Scans article title and content for company names and matches them to tickers.
    """
    # Limit search content size to avoid regex backtracking on huge HTML page dumps
    search_content = content[:2000] if content else ""
    text_to_search = f"{title} {search_content}".lower()
    matched_tickers = []
    
    for ticker, patterns in COMPANY_ALIASES.items():
        for pattern in patterns:
            if re.search(pattern, text_to_search):
                matched_tickers.append(ticker)
                break # stop checking patterns for this ticker once matched
                
    return matched_tickers

def analyze_sentiment_ollama(title, content):
    """
    Fallback sentiment analysis utilizing local Ollama instance (qwen2.5:3b or llama3).
    """
    prompt = f"""You are a professional financial sentiment analyzer.
Analyze the following financial news title:
"{title}"

Respond ONLY with a valid JSON object in this exact format, providing brief reasoning first:
{{"reasoning": "string", "label": "positive" | "negative" | "neutral", "score": float}}
Note: The score must be between -1.0 (extremely negative) and 1.0 (extremely positive). Do not output any markdown formatting, code block decorators, or explanations outside the JSON object.
"""
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_predict": 150,  # Increased for CoT reasoning
                "num_thread": 4     # Fix: Limit CPU threads to reduce context switching overhead
            }
        }
        # Try qwen first (faster). If not running, fall back to llama3
        response = requests.post(url, json=payload, timeout=150) # Fix: Increased timeout to 150s for virtual CPU
        
        # If model not found or error, try llama3
        if response.status_code != 200:
            payload["model"] = "llama3"
            response = requests.post(url, json=payload, timeout=180) # Fix: Increased timeout to 180s for virtual CPU
            
        if response.status_code == 200:
            res_data = response.json()
            raw_text = res_data.get("response", "").strip()
            data = json.loads(raw_text)
            
            label = data.get("label", "neutral").lower()
            score = float(data.get("score", 0.0))
            
            # Bound checking
            if label not in ["positive", "negative", "neutral"]:
                label = "neutral"
            score = max(-1.0, min(1.0, score))
            
            return label, score
    except Exception as e:
        print(f"Ollama sentiment analysis failed: {e}")
        
    return "neutral", 0.0

def analyze_sentiment(title, content):
    """
    Determines sentiment using FinBERT, falls back to Ollama.
    """
    if load_finbert():
        try:
            # Combine title + short snippet
            text_to_analyze = f"{title}. {content[:150]}"
            res = _finbert_pipeline(text_to_analyze[:512]) # FinBERT maximum token limit is usually 512
            if res:
                label = res[0]["label"].lower() # positive, negative, neutral
                score_prob = res[0]["score"]
                
                # Convert prob to numeric scale (-1.0 to 1.0)
                if label == "positive":
                    score = score_prob
                elif label == "negative":
                    score = -score_prob
                else:
                    score = 0.0
                return label, score
        except Exception as e:
            print(f"FinBERT inference error: {e}. Falling back to Ollama.")
            
    # Ollama Fallback
    return analyze_sentiment_ollama(title, content)

def calculate_decayed_sentiment(ticker, db):
    """
    Computes aggregated sentiment score for a stock ticker.
    Applies exponential decay (half-life of 24h) and source trust weighting.
    Only considers articles from the last 48 hours.
    """
    query = text("""
        SELECT a.sentiment_score, a.published_date, a.source
        FROM news_articles a
        JOIN news_company_mappings m ON a.id = m.article_id
        WHERE m.company_ticker = :ticker
          AND a.published_date >= NOW() - INTERVAL '48 hours'
          AND a.sentiment_score IS NOT NULL
    """)
    results = db.execute(query, {"ticker": ticker}).fetchall()
    
    if not results:
        return 0.0
        
    now = datetime.now(timezone.utc)
    total_weight = 0.0
    weighted_sentiment_sum = 0.0
    
    # Half life of 24 hours -> lambda = ln(2)/24
    decay_lambda = math.log(2) / 24.0
    
    for row in results:
        score, pub_date, source = row
        
        # Ensure pub_date is timezone-aware
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
            
        age_hours = (now - pub_date).total_seconds() / 3600.0
        age_hours = max(0.0, age_hours)
        
        # 1. Decay Factor = e ^ (-lambda * t)
        decay_factor = math.exp(-decay_lambda * age_hours)
        
        # 2. Source Trust weight
        trust_weight = SOURCE_TRUST_SCORES.get(source, 0.60)
        
        combined_weight = decay_factor * trust_weight
        
        weighted_sentiment_sum += float(score) * combined_weight
        total_weight += combined_weight
        
    if total_weight == 0.0:
        return 0.0
        
    return weighted_sentiment_sum / total_weight

_tokenizer = None
_model = None

def get_embeddings(texts):
    global _tokenizer, _model
    if _tokenizer is None or _model is None:
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        print(f"Loading local embedding model: {model_name}...")
        import torch
        from transformers import AutoTokenizer, AutoModel
        torch.set_num_threads(1) # CPU-safe thread count
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModel.from_pretrained(model_name)
    
    import torch
    
    def mean_pooling(model_output, attention_mask):
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    encoded_input = _tokenizer(texts, padding=True, truncation=True, max_length=128, return_tensors='pt')
    with torch.no_grad():
        model_output = _model(**encoded_input)

    sentence_embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
    sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
    return sentence_embeddings.numpy()

def cluster_articles(articles):
    if not articles or len(articles) < 2:
        return []
    
    import numpy as np
    texts = [art[1] for art in articles] # Get titles
    try:
        embeddings = get_embeddings(texts)
    except Exception as e:
        print(f"Error computing local embeddings for news clustering: {e}")
        return []
        
    n = len(articles)
    visited = [False] * n
    clusters = []
    
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        cluster = [i]
        
        for j in range(i + 1, n):
            if visited[j]:
                continue
            sim = np.dot(embeddings[i], embeddings[j])
            if sim > 0.78:
                visited[j] = True
                cluster.append(j)
                
        if len(cluster) > 1:
            clusters.append(cluster)
            
    return clusters

def process_unprocessed_news():
    """
    Retrieves unprocessed articles, clusters near-duplicates using a local model,
    runs NER ticker mapping, and updates sentiment in the database.
    """
    db = SessionLocal()
    try:
        # Mark older unprocessed articles as neutral to keep database clean and pipeline fast
        db.execute(text("""
            UPDATE news_articles 
            SET processed = TRUE, sentiment_score = 0.0, sentiment_label = 'neutral'
            WHERE processed = FALSE AND published_date < NOW() - INTERVAL '48 hours'
        """))
        db.commit()

        # Fetch unprocessed articles from the last 48 hours
        articles = db.execute(
            text("SELECT id, title, content, url, source, country FROM news_articles WHERE processed = FALSE")
        ).fetchall()
        
        if not articles:
            print("No new articles to process in NLP pipeline.")
            return 0
            
        print(f"NLP Pipeline: processing {len(articles)} articles...")
        
        # Cluster unprocessed articles using local model
        clusters = cluster_articles(articles)
        child_to_parent_index = {}
        parent_indices = set()
        for c in clusters:
            parent_idx = c[0]
            parent_indices.add(parent_idx)
            for child_idx in c[1:]:
                child_to_parent_index[child_idx] = parent_idx
        
        print(f"NLP Pipeline: found {len(clusters)} clusters of duplicate/similar stories.")
        
        processed_count = 0
        ollama_calls_made = 0
        max_ollama_calls = 3 # Cap Ollama calls to keep execution fast on virtual CPU
        
        processed_parents = {} # Maps parent_idx -> (parent_id, label, score, tickers)
        
        for idx, art in enumerate(articles):
            art_id, title, content, url, source, country = art
            
            # Print progress update
            if (processed_count + 1) % 10 == 0 or processed_count == 0 or processed_count == len(articles) - 1:
                print(f"NLP: Processing article {processed_count + 1}/{len(articles)} ({source}) - {title[:45]}...")
            
            try:
                # Check if this article is a child of a cluster
                if idx in child_to_parent_index:
                    parent_idx = child_to_parent_index[idx]
                    if parent_idx in processed_parents:
                        parent_id, label, score, tickers = processed_parents[parent_idx]
                        
                        # Save sentiment and link to parent
                        db.execute(
                            text("""
                                UPDATE news_articles 
                                SET sentiment_score = :score, sentiment_label = :label, processed = TRUE, parent_article_id = :parent_id
                                WHERE id = :id
                            """),
                            {"score": score, "label": label, "parent_id": parent_id, "id": art_id}
                        )
                        
                        # Copy mappings
                        for ticker in tickers:
                            db.execute(
                                text("""
                                    INSERT INTO news_company_mappings (article_id, company_ticker)
                                    VALUES (:article_id, :ticker)
                                    ON CONFLICT DO NOTHING
                                """),
                                {"article_id": art_id, "ticker": ticker}
                            )
                        db.commit()
                        processed_count += 1
                        print(f"NLP: Clustered child duplicate '{title[:35]}...' under parent ID {parent_id}.")
                        continue
                
                # 1. Map to companies (NER) for parent or independent article
                tickers = map_article_to_tickers(title, content)
                
                # 2. Run Sentiment Analysis only if it maps to a target company
                if tickers:
                    if load_finbert():
                        label, score = analyze_sentiment(title, content)
                    elif ollama_calls_made < max_ollama_calls:
                        label, score = analyze_sentiment(title, content)
                        ollama_calls_made += 1
                    else:
                        label, score = "neutral", 0.0
                else:
                    label, score = "neutral", 0.0
                
                # 3. Save sentiment back to DB and mark processed
                db.execute(
                    text("""
                        UPDATE news_articles 
                        SET sentiment_score = :score, sentiment_label = :label, processed = TRUE
                        WHERE id = :id
                    """),
                    {"score": score, "label": label, "id": art_id}
                )
                
                # 4. Insert company mappings
                for ticker in tickers:
                    db.execute(
                        text("""
                            INSERT INTO news_company_mappings (article_id, company_ticker)
                            VALUES (:article_id, :ticker)
                            ON CONFLICT DO NOTHING
                        """),
                        {"article_id": art_id, "ticker": ticker}
                    )
                db.commit()
                
                # If this was a parent, store results to copy for children
                if idx in parent_indices:
                    processed_parents[idx] = (art_id, label, score, tickers)
                    
                processed_count += 1
            except Exception as e:
                print(f"Error processing NLP for article ID {art_id}: {e}")
                db.rollback()
                
        print(f"NLP Pipeline finished. Processed {processed_count} articles. Made {ollama_calls_made} Ollama calls.")
        return processed_count
    finally:
        db.close()


if __name__ == "__main__":
    process_unprocessed_news()
