#!/usr/bin/env python3
"""
FastAPI dashboard for the Crypto Trading tool.

Provides a minimal REST + WebSocket API for monitoring bot status, configuration
summaries, and recent logs. Designed to run alongside the trading bot via the
bootstrap/deploy automation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# The trading modules live under src/, so ensure PYTHONPATH includes src
ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"
LOG_PATH = ROOT / "crypto_trading.log"

try:
    from crypto_trading.utils.config import Config, load_config
except ModuleNotFoundError as exc:  # pragma: no cover - happens only if PYTHONPATH misconfigured
    raise RuntimeError(
        "Unable to import crypto_trading modules. Make sure PYTHONPATH includes 'src'."
    ) from exc


def utc_now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def sanitize_config(cfg: Config) -> Dict[str, Any]:
    """Return a safe version of the config without secrets."""
    exchanges = {
        name: {
            "sandbox": exchange.sandbox,
            "rate_limit": exchange.rate_limit,
            "enable_rate_limit": exchange.enable_rate_limit,
            "has_passphrase": bool(exchange.passphrase),
        }
        for name, exchange in cfg.exchanges.items()
    }

    trading = {
        "symbols": cfg.trading.symbols,
        "strategies": cfg.trading.strategies,
        "max_positions": cfg.trading.max_positions,
        "risk_management": cfg.trading.risk_management.dict(),
    }

    monitoring = {
        "enable_alerts": cfg.monitoring.enable_alerts,
        "alert_channels": cfg.monitoring.alert_channels,
        "metrics_retention_hours": cfg.monitoring.metrics_retention_hours,
    }

    return {
        "exchanges": exchanges,
        "trading": trading,
        "monitoring": monitoring,
        "enable_live_trading": cfg.enable_live_trading,
        "log_level": cfg.log_level,
    }


def get_recent_logs(limit: int = 200) -> List[str]:
    if not LOG_PATH.exists():
        return []

    try:
        with LOG_PATH.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except Exception:
        return []

    trimmed = [line.rstrip() for line in lines[-limit:]]
    return trimmed


def build_status() -> Dict[str, Any]:
    """Assemble a snapshot of the tool status."""
    summary: Dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "config_present": CONFIG_PATH.exists(),
        "log_present": LOG_PATH.exists(),
        "exchanges": [],
        "symbols": [],
        "strategies": [],
        "enable_live_trading": False,
    }

    if CONFIG_PATH.exists():
        try:
            cfg = load_config(str(CONFIG_PATH))
            summary["exchanges"] = list(cfg.exchanges.keys())
            summary["symbols"] = cfg.trading.symbols
            summary["strategies"] = cfg.trading.strategies
            summary["enable_live_trading"] = cfg.enable_live_trading
        except Exception as exc:  # pragma: no cover - defensive
            summary["config_error"] = str(exc)

    if LOG_PATH.exists():
        summary["latest_logs"] = get_recent_logs(limit=5)

    return summary


class DashboardState:
    """Caches status snapshots to avoid re-reading config multiple times per second."""

    def __init__(self, ttl_seconds: int = 5):
        self._ttl_seconds = ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._last_refresh: float = 0.0
        self._lock = asyncio.Lock()

    async def snapshot(self) -> Dict[str, Any]:
        now = asyncio.get_running_loop().time()
        if now - self._last_refresh < self._ttl_seconds and self._cache:
            return self._cache

        async with self._lock:
            now = asyncio.get_running_loop().time()
            if now - self._last_refresh < self._ttl_seconds and self._cache:
                return self._cache

            self._cache = build_status()
            self._last_refresh = now
            return self._cache


app = FastAPI(title="FamilyGuard Dashboard", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
state = DashboardState()


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "timestamp": utc_now_iso()}


@app.get("/api/status")
async def api_status() -> Dict[str, Any]:
    return await state.snapshot()


@app.get("/api/config")
async def api_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"error": "config file not found", "config_path": str(CONFIG_PATH)}

    try:
        cfg = load_config(str(CONFIG_PATH))
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": str(exc)}

    return {"generated_at": utc_now_iso(), "config": sanitize_config(cfg)}


@app.get("/api/logs")
async def api_logs(limit: int = 200) -> Dict[str, Any]:
    lines = get_recent_logs(limit=limit)
    return {"count": len(lines), "entries": lines}


@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await state.snapshot()
            await websocket.send_json(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
    except Exception:  # pragma: no cover - defensive
        await websocket.close()

