from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import engine
from app.db import models
from app.db.models import ConfigModel
from app.db.session import SessionLocal
from app.config import settings
from app.logging_setup import log_system_event
from app.mt5_client.connection import initialize_mt5, shutdown_mt5, check_connection
from app.engine.signal_loop import run_signal_loop

from app.api import routes_status, routes_positions, routes_journal, routes_analytics, routes_config, routes_zones, routes_ws, routes_chart

# ── Scheduler ──────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    models.Base.metadata.create_all(bind=engine)
    
    # Ensure config row exists
    db = SessionLocal()
    try:
        if not db.query(ConfigModel).first():
            db.add(ConfigModel())
            db.commit()
    finally:
        db.close()
    
    # Connect MT5
    initialize_mt5()
    
    # Schedule signal loop at every :00, :15, :30, :45 minutes
    scheduler.add_job(
        run_signal_loop,
        CronTrigger(minute=f"*/{settings.SCHEDULER_INTERVAL_MINUTES}"),
        id="signal_loop",
        replace_existing=True
    )
    scheduler.start()
    log_system_event('info', f"Scheduler started. Signal loop runs every {settings.SCHEDULER_INTERVAL_MINUTES}min.")
    
    yield
    
    # Shutdown
    scheduler.shutdown(wait=False)
    shutdown_mt5()

# ── App ─────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SMC Algo Trading Dashboard API",
    description="Python/FastAPI backend for the XAUUSD/BTCUSD SMC trading bot",
    version="1.0.0",
    lifespan=lifespan
)

# Allow the Vite frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────────
app.include_router(routes_status.router, prefix="/api", tags=["Status"])
app.include_router(routes_positions.router, prefix="/api", tags=["Positions"])
app.include_router(routes_journal.router, prefix="/api", tags=["Journal"])
app.include_router(routes_analytics.router, prefix="/api", tags=["Analytics"])
app.include_router(routes_config.router, prefix="/api", tags=["Config"])
app.include_router(routes_zones.router, prefix="/api", tags=["Zones"])
app.include_router(routes_chart.router, prefix="/api", tags=["Chart"])
app.include_router(routes_ws.router, tags=["WebSocket"])

@app.get("/")
def root():
    return {
        "service": "SMC Algo Trading Dashboard API",
        "docs": "/docs",
        "status": "/api/status"
    }
