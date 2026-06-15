"""
backend/routers/tickers.py
==========================
/api/tickers/* endpoints — manage monitored assets.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from datetime import datetime, timezone

from core import engine, manager
import core
from models.schemas import TickerTogglePayload, TickerAddPayload
from auth import get_current_user

router = APIRouter(prefix="/api/tickers", tags=["Tickers"])


@router.get("")
def get_tickers():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT ticker, name, country, sector, industry, is_active FROM companies ORDER BY ticker"
            )).fetchall()
            return [
                {
                    "ticker": r[0], "name": r[1], "country": r[2],
                    "sector": r[3], "industry": r[4], "is_active": r[5],
                }
                for r in rows
            ]
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []


@router.post("/toggle")
async def toggle_ticker(payload: TickerTogglePayload, current_user: dict = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE companies SET is_active = :active WHERE ticker = :ticker"),
                {"active": payload.is_active, "ticker": payload.ticker},
            )
            conn.commit()
        await core.manager.broadcast({"type": "tickers_update"})
        return {"status": "ok"}
    except Exception as e:
        print(f"Error toggling ticker: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/add")
async def add_ticker(payload: TickerAddPayload, current_user: dict = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO companies (ticker, name, country, sector, industry, is_active, trust_score)
                VALUES (:ticker, :name, :country, :sector, :industry, TRUE, 0.75)
                ON CONFLICT (ticker) DO UPDATE SET
                    name     = EXCLUDED.name,
                    country  = EXCLUDED.country,
                    sector   = EXCLUDED.sector,
                    industry = EXCLUDED.industry,
                    is_active = TRUE
            """), {
                "ticker": payload.ticker, "name": payload.name,
                "country": payload.country, "sector": payload.sector,
                "industry": payload.industry,
            })
            conn.commit()
        await core.manager.broadcast({"type": "tickers_update"})
        return {"status": "ok", "ticker": payload.ticker}
    except Exception as e:
        print(f"Error adding ticker: {e}")
        raise HTTPException(status_code=500, detail="Database error")
