"""
backend/routers/mt5.py
======================
All /api/mt5/* endpoints.
Imports shared state from core.py — no circular dependency.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from core import engine, manager, manual_overrides, send_system_notifications
from models.schemas import (
    OverridePayload, PositionsPayload, ExecutionLogPayload,
    RiskSettingsPayload, AccountRiskPayload, KillSwitchPayload,
    MT5PositionsPayload, MT5ExecutionLog,
)
from auth import get_current_user, require_admin, write_audit_log

# Import mutable globals — we modify them via global keyword inside functions
import core

router = APIRouter(prefix="/api/mt5", tags=["MT5"])


@router.get("/overrides")
def get_overrides():
    return core.manual_overrides


@router.post("/overrides")
async def set_override(payload: OverridePayload, current_user: dict = Depends(get_current_user)):
    ticker = payload.ticker
    action = payload.action
    if action == "CLEAR":
        core.manual_overrides.pop(ticker, None)
        send_system_notifications(
            f"ℹ️ <b>EuroQuant Manual Override</b>\n"
            f"Override for <code>{ticker}</code> cleared by user <b>{current_user['username']}</b>."
        )
    else:
        core.manual_overrides[ticker] = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        send_system_notifications(
            f"⚠️ <b>EuroQuant Manual Override FORCE</b>\n"
            f"Override for <code>{ticker}</code> set to <b>{action}</b> by user <b>{current_user['username']}</b>."
        )
    await core.manager.broadcast({"type": "overrides_update"})
    return {"status": "success", "overrides": core.manual_overrides}


@router.get("/accounts")
def get_broker_accounts():
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT account_id, broker, balance, equity, margin, margin_free, margin_level, profit, last_seen
                FROM broker_accounts ORDER BY last_seen DESC
            """)).fetchall()
            return [
                {
                    "account_id": r[0], "broker": r[1],
                    "balance": float(r[2]) if r[2] is not None else 0.0,
                    "equity": float(r[3]) if r[3] is not None else 0.0,
                    "margin": float(r[4]) if r[4] is not None else 0.0,
                    "margin_free": float(r[5]) if r[5] is not None else 0.0,
                    "margin_level": float(r[6]) if r[6] is not None else 0.0,
                    "profit": float(r[7]) if r[7] is not None else 0.0,
                    "last_seen": r[8].isoformat() if r[8] else None,
                }
                for r in rows
            ]
    except Exception as e:
        print(f"Error fetching broker accounts: {e}")
        return []


@router.post("/positions")
async def sync_mt5_positions(payload: PositionsPayload):
    try:
        with engine.connect() as conn:
            for pos in payload.positions:
                conn.execute(text("""
                    INSERT INTO live_positions (ticker, quantity, avg_price, current_price, unrealized_pnl, updated_at)
                    VALUES (:ticker, :qty, :avg_price, :current_price, :pnl, NOW())
                    ON CONFLICT (ticker) DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        avg_price = EXCLUDED.avg_price,
                        current_price = EXCLUDED.current_price,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        updated_at = NOW();
                """), {
                    "ticker": pos.ticker, "qty": pos.quantity,
                    "avg_price": pos.avg_price, "current_price": pos.current_price,
                    "pnl": pos.unrealized_pnl,
                })
            conn.commit()
            await core.manager.broadcast({"type": "positions_update"})
            return {"status": "ok"}
    except Exception as e:
        print(f"Error syncing positions: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/execution-log")
async def sync_execution_log(payload: ExecutionLogPayload):
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO execution_logs (ticker, action, quantity, fill_price, slippage, broker, timestamp)
                VALUES (:ticker, :action, :qty, :fill_price, :slippage, :broker, NOW())
            """), {
                "ticker": payload.ticker, "action": payload.action,
                "qty": payload.quantity, "fill_price": payload.fill_price,
                "slippage": payload.slippage, "broker": payload.broker,
            })
            conn.commit()
            await core.manager.broadcast({"type": "execution_logs_update"})
            return {"status": "ok"}
    except Exception as e:
        print(f"Error saving execution log: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/risk")
def get_risk_settings():
    with engine.connect() as conn:
        acc_stats = conn.execute(text("SELECT SUM(balance), SUM(equity) FROM broker_accounts")).fetchone()
        current_drawdown_pct = 0.0
        if acc_stats and acc_stats[0] and float(acc_stats[0]) > 0:
            total_bal, total_eq = float(acc_stats[0]), float(acc_stats[1])
            if total_bal > total_eq:
                current_drawdown_pct = ((total_bal - total_eq) / total_bal) * 100.0
        accounts_rows = conn.execute(text(
            "SELECT account_id, broker, balance, equity, profit, max_drawdown_percent FROM broker_accounts"
        )).fetchall()
        accounts_data = []
        for r in accounts_rows:
            acc_id, broker, bal, eq, prof, max_dd = r
            bal_val = float(bal) if bal else 0.0
            eq_val = float(eq) if eq else 0.0
            dd = ((bal_val - eq_val) / bal_val * 100.0) if bal_val > eq_val and bal_val > 0 else 0.0
            accounts_data.append({
                "account_id": acc_id, "broker": broker or "Unknown",
                "balance": bal_val, "equity": eq_val,
                "profit": float(prof) if prof else 0.0,
                "max_drawdown_percent": float(max_dd) if max_dd is not None else 5.0,
                "current_drawdown_percent": round(dd, 2),
            })
    return {
        "max_drawdown_percent": core.max_drawdown_percent,
        "emergency_kill_switch": core.emergency_kill_switch,
        "current_drawdown_percent": round(current_drawdown_pct, 2),
        "accounts": accounts_data,
    }


@router.post("/risk")
async def update_risk_settings(payload: RiskSettingsPayload, current_user: dict = Depends(require_admin)):
    core.max_drawdown_percent = payload.max_drawdown_percent
    send_system_notifications(
        f"🛡️ <b>EuroQuant Risk System</b>\n"
        f"Max drawdown limit updated to {core.max_drawdown_percent}% by admin <b>{current_user['username']}</b>."
    )
    await core.manager.broadcast({"type": "risk_update"})
    return {"status": "success", "max_drawdown_percent": core.max_drawdown_percent}


@router.post("/risk/kill-switch")
async def toggle_kill_switch(payload: KillSwitchPayload, current_user: dict = Depends(require_admin)):
    core.emergency_kill_switch = payload.active
    status_text = "ATTIVATO" if core.emergency_kill_switch else "DISATTIVATO"
    send_system_notifications(
        f"⚠️ <b>EuroQuant EMERGENCY ALERT</b>\n"
        f"Kill switch <b>{status_text}</b> by admin <b>{current_user['username']}</b>!"
    )
    await core.manager.broadcast({"type": "risk_update"})
    return {"status": "success", "emergency_kill_switch": core.emergency_kill_switch}


@router.post("/accounts/{account_id}/risk")
async def update_account_risk_settings(account_id: str, payload: AccountRiskPayload, current_user: dict = Depends(require_admin)):
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE broker_accounts SET max_drawdown_percent = :max_dd WHERE account_id = :account_id"),
            {"max_dd": payload.max_drawdown_percent, "account_id": account_id}
        )
        conn.commit()
    send_system_notifications(
        f"🛡️ <b>EuroQuant Risk System</b>\n"
        f"Account <code>{account_id}</code> drawdown limit updated to {payload.max_drawdown_percent}% by admin <b>{current_user['username']}</b>."
    )
    await core.manager.broadcast({"type": "risk_update"})
    return {"status": "success", "account_id": account_id, "max_drawdown_percent": payload.max_drawdown_percent}


@router.get("/clients")
def get_mt5_clients():
    return list(core.mt5_clients.values())
