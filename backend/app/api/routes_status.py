from fastapi import APIRouter
from datetime import datetime
from app.schemas.system_status import SystemStatus
from app.schemas.log_entry import LogEntry
from app.mt5_client.connection import check_connection
from app.regime.detector import detect_regime
from app.mt5_client.data_feed import fetch_ohlc
from app.config import settings

router = APIRouter()

# In-memory bot state (shared via module-level variable)
bot_state = {"status": "running"}

@router.get("/status", response_model=SystemStatus)
def get_status():
    connected = check_connection()
    regime = "ranging"
    
    if connected:
        df = fetch_ohlc(settings.symbol_list[0], settings.TIMEFRAME, 100)
        if not df.empty:
            regime = detect_regime(df)
            
    return SystemStatus(
        botStatus=bot_state["status"],
        mt5Connected=connected,
        regime=regime,
        lastTickAt=datetime.utcnow()
    )

from app.engine.signal_loop import run_signal_loop

@router.post("/status/pause")
def pause_bot():
    bot_state["status"] = "paused"
    return {"botStatus": "paused"}

@router.post("/status/resume")
def resume_bot():
    bot_state["status"] = "running"
    return {"botStatus": "running"}

@router.post("/status/force-signal")
def force_signal():
    run_signal_loop()
    return {"status": "Signal loop executed"}

@router.get("/logs", response_model=list[LogEntry])
def get_logs(limit: int = 50):
    from app.db.session import SessionLocal
    from app.db.models import LogEntryModel
    db = SessionLocal()
    try:
        entries = db.query(LogEntryModel).order_by(LogEntryModel.timestamp.desc()).limit(limit).all()
        return [
            LogEntry(
                id=e.id,
                timestamp=e.timestamp,
                level=e.level,
                message=e.message
            )
            for e in entries
        ]
    finally:
        db.close()

