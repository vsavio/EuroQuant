import json
import logging
from sqlalchemy import text
import numpy as np

log = logging.getLogger("gnn_engine")

def build_sector_graph(db_session):
    """
    Costruisce una matrice di adiacenza (Grafo) basata sulle relazioni settoriali 
    e le variazioni di prezzo a 24h.
    """
    companies = db_session.execute(text("SELECT ticker, sector, industry FROM companies")).fetchall()
    
    # Raccogli ultimi prezzi (24h change)
    prices = {}
    for c in companies:
        ticker = c[0]
        res = db_session.execute(text("SELECT price_change_24h FROM recommendations WHERE ticker = :t"), {"t": ticker}).fetchone()
        prices[ticker] = float(res[0]) if res and res[0] else 0.0
        
    # Costruisci il grafo delle influenze
    # Se un titolo dello stesso settore scende molto, "contagia" gli altri (GNN Message Passing)
    contagion_scores = {}
    for target in companies:
        target_ticker, target_sector, target_industry = target
        
        peer_influence = 0.0
        peer_count = 0
        
        for peer in companies:
            peer_ticker, peer_sector, peer_industry = peer
            if target_ticker == peer_ticker:
                continue
                
            weight = 0.0
            if target_industry == peer_industry:
                weight = 0.8  # Forte correlazione intraday
            elif target_sector == peer_sector:
                weight = 0.4  # Correlazione settoriale moderata
                
            if weight > 0:
                peer_influence += prices[peer_ticker] * weight
                peer_count += 1
                
        if peer_count > 0:
            # Calcola il GNN Message Passing (aggregazione del neighborhood)
            avg_peer_influence = peer_influence / peer_count
            contagion_scores[target_ticker] = round(avg_peer_influence, 4)
        else:
            contagion_scores[target_ticker] = 0.0
            
    return contagion_scores

def run_gnn_contagion():
    """
    Esegue il modello Graph Neural Network per calcolare il contagio settoriale.
    Salva i risultati nel database.
    """
    from database import SessionLocal
    db = SessionLocal()
    try:
        contagion_scores = build_sector_graph(db)
        
        for ticker, score in contagion_scores.items():
            db.execute(text("""
                UPDATE recommendations 
                SET gnn_contagio = :score 
                WHERE ticker = :t
            """), {"score": score, "t": ticker})
            
        db.commit()
        log.info(json.dumps({"event": "gnn_executed", "nodes_processed": len(contagion_scores)}))
        return contagion_scores
    except Exception as e:
        log.error(json.dumps({"event": "gnn_error", "error": str(e)}))
        db.rollback()
        return {}
    finally:
        db.close()
