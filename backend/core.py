"""
backend/core.py
===============
Shared application state: DB engine, WebSocket manager, global risk
variables, TTL caches and notification helpers.

All routers import from here to avoid circular dependencies.
"""
import os
import json
import math
from datetime import datetime, timezone
from typing import List

import requests as _requests
from fastapi import WebSocket
from sqlalchemy import create_engine, text
from cachetools import TTLCache

# ─── Database ────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db"
)
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=20)

# ─── WebSocket Manager ────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# ─── Global Risk State ────────────────────────────────────────────────────────
mt5_clients: dict = {}
manual_overrides: dict = {}
max_drawdown_percent: float = 5.0
emergency_kill_switch: bool = False
last_risk_state: bool = False
last_risk_reason: str = ""

# ─── TTL Caches ──────────────────────────────────────────────────────────────
_cache_market_summary  = TTLCache(maxsize=1,  ttl=30)
_cache_screener        = TTLCache(maxsize=64, ttl=60)
_cache_forex           = TTLCache(maxsize=1,  ttl=30)
_cache_correlation     = TTLCache(maxsize=8,  ttl=300)
_cache_risk_analytics  = TTLCache(maxsize=1,  ttl=120)

# ─── Notification Helpers ─────────────────────────────────────────────────────
def send_telegram_alert(message: str) -> None:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT telegram_bot_token, telegram_chat_id FROM system_settings WHERE id = 1")
            ).fetchone()
        if row and row[0] and row[1]:
            _requests.post(
                f"https://api.telegram.org/bot{row[0]}/sendMessage",
                json={"chat_id": row[1], "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
    except Exception:
        pass


def send_discord_alert(message: str) -> None:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT discord_webhook_url FROM system_settings WHERE id = 1")
            ).fetchone()
        if row and row[0]:
            _requests.post(row[0], json={"content": message}, timeout=10)
    except Exception:
        pass


def send_system_notifications(message: str) -> None:
    send_telegram_alert(message)
    send_discord_alert(message)
