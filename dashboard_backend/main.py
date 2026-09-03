import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
from typing import List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.db import get_engine
from config.settings import settings
from core.logger import get_logger

log = get_logger("dashboard", log_file="logs/dashboard.log")

app = FastAPI(title="SMC Zero-Latency Dashboard Backend")

# Allow CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Connection Manager for WebSockets ─────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except RuntimeError:
                # Connection dropped
                pass

manager = ConnectionManager()

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from client, just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

class EventPayload(BaseModel):
    event_type: str
    data: dict

@app.post("/api/internal/push")
async def internal_push(payload: EventPayload):
    """Webhook for live_runner.py to push events to the dashboard."""
    await manager.broadcast({"type": payload.event_type, "data": payload.data})
    return {"status": "ok"}

@app.get("/api/trades")
async def get_trades(
    page: int = 1,
    limit: int = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    signal_type: Optional[str] = None
):
    engine = get_engine()
    query = "SELECT t.*, s.confluence_score, s.signal_type, s.direction FROM trades t JOIN signal_logs s ON t.signal_id = s.id WHERE t.environment = 'paper'"
    params = {}
    
    if start_date:
        query += " AND t.entry_time >= %(start)s"
        params['start'] = start_date
    if end_date:
        query += " AND t.entry_time <= %(end)s"
        params['end'] = end_date
    if signal_type:
        query += " AND s.signal_type = %(sig_type)s"
        params['sig_type'] = signal_type
        
    query += " ORDER BY t.entry_time DESC LIMIT %(limit)s OFFSET %(offset)s"
    params['limit'] = limit
    params['offset'] = (page - 1) * limit
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
        df['entry_time'] = df['entry_time'].astype(str)
        if 'exit_time' in df.columns:
             df['exit_time'] = df['exit_time'].astype(str)
        return {"data": df.to_dict(orient="records"), "page": page}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/equity-curve")
async def get_equity_curve():
    engine = get_engine()
    query = "SELECT entry_time, pnl FROM trades WHERE environment = 'paper' AND exit_reason IS NOT NULL ORDER BY entry_time ASC"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        if df.empty:
            return {"data": []}
            
        df['entry_time'] = df['entry_time'].astype(str)
        df['cumulative_pnl'] = df['pnl'].cumsum()
        
        # We need a starting balance to plot relative drop. Assuming 10k for now.
        df['equity'] = 10000.0 + df['cumulative_pnl']
        return {"data": df[['entry_time', 'equity', 'pnl', 'cumulative_pnl']].to_dict(orient="records")}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/stats")
async def get_stats():
    engine = get_engine()
    query = "SELECT entry_time, pnl, pnl_r, exit_reason FROM trades WHERE environment = 'paper' AND exit_reason IS NOT NULL"
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        if df.empty:
             return {"all_time": {"trades": 0, "win_rate": 0, "expectancy": 0, "pf": 0}, "week": {"trades": 0, "win_rate": 0, "expectancy": 0, "pf": 0}}
             
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        if df['entry_time'].dt.tz is None:
             df['entry_time'] = df['entry_time'].dt.tz_localize('UTC')
             
        def calc(data: pd.DataFrame):
            if data.empty:
                return {"trades": 0, "win_rate": 0.0, "expectancy": 0.0, "pf": 0.0}
            wins = data[data['pnl_r'] > 0]
            losses = data[data['pnl_r'] <= 0]
            wr = (len(wins) / len(data)) * 100
            exp = data['pnl_r'].mean()
            gross_win = wins['pnl'].sum()
            gross_loss = abs(losses['pnl'].sum())
            pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
            return {"trades": len(data), "win_rate": round(wr, 1), "expectancy": round(exp, 2), "pf": round(pf, 2)}
            
        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)
        week_df = df[df['entry_time'] >= one_week_ago]
        
        return {
            "all_time": calc(df),
            "week": calc(week_df)
        }
    except Exception as e:
         return {"error": str(e)}

@app.get("/api/status")
async def get_status():
    engine = get_engine()
    try:
        with engine.connect() as conn:
            hb_df = pd.read_sql("SELECT * FROM system_status WHERE id = 'live_runner'", conn)
            sig_df = pd.read_sql("SELECT * FROM signal_logs WHERE environment = 'paper' ORDER BY timestamp DESC LIMIT 1", conn)
            trades_df = pd.read_sql("SELECT MIN(entry_time) as min_time FROM trades WHERE environment = 'paper'", conn)
        
        hb = hb_df.iloc[0].to_dict() if not hb_df.empty else None
        last_sig = sig_df.iloc[0].to_dict() if not sig_df.empty else None
        
        # Cleanup JSON
        if hb and hb.get('extra_info'):
            hb['extra_info'] = json.loads(hb['extra_info'])
            hb['timestamp'] = str(hb['timestamp'])
            
        if last_sig:
            last_sig['timestamp'] = str(last_sig['timestamp'])
            
    """Returns basic configuration and status."""
    return {
        "paper_start_date": settings.paper_start_date,
        "environment": "paper" if settings.is_paper else "live",
        "active_symbols": settings.active_symbols
    }

# Mount the static frontend at the root (must be done last to not override API routes)
frontend_dist_path = Path(__file__).resolve().parent.parent / "dashboard_frontend" / "dist"
if frontend_dist_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist_path), html=True), name="frontend")
else:
    log.warning(f"Frontend dist not found at {frontend_dist_path}. Run npm run build.")

if __name__ == "__main__":
    import uvicorn
    # Make sure we use a different port if needed, 8000 is default
    uvicorn.run(app, host="0.0.0.0", port=8000)
