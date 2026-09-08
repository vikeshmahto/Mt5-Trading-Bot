from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.db.models import ConfigModel
from app.logging_setup import log_system_event

router = APIRouter()

class ConfigUpdate(BaseModel):
    riskPerTrade: Optional[float] = None
    dailyCircuitBreaker: Optional[bool] = None
    maxDailyLoss: Optional[float] = None
    paperTradingStartDate: Optional[str] = None
    setupObFvg: Optional[bool] = None
    setupLiquiditySweep: Optional[bool] = None
    setupBosBreakout: Optional[bool] = None
    setupTrendlineBounce: Optional[bool] = None
    activeSetups: Optional[dict[str, bool]] = None

def _get_or_create_config(db: Session) -> ConfigModel:
    config = db.query(ConfigModel).first()
    if not config:
        config = ConfigModel()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = _get_or_create_config(db)
    return {
        "riskPerTrade": config.risk_per_trade,
        "dailyCircuitBreaker": config.daily_circuit_breaker,
        "maxDailyLoss": config.max_daily_loss,
        "paperTradingStartDate": getattr(config, "paper_trading_start_date", "2026-09-08T17:30:00Z"),
        "activeSetups": {
            "OB+FVG confluence": config.setup_ob_fvg,
            "Liquidity Sweep": config.setup_liquidity_sweep,
            "BOS Breakout": config.setup_bos_breakout,
            "Trendline Bounce": config.setup_trendline_bounce,
        }
    }

@router.post("/config")
def update_config(payload: ConfigUpdate, db: Session = Depends(get_db)):
    config = _get_or_create_config(db)
    
    if payload.riskPerTrade is not None:
        config.risk_per_trade = payload.riskPerTrade
    if payload.dailyCircuitBreaker is not None:
        config.daily_circuit_breaker = payload.dailyCircuitBreaker
    if payload.maxDailyLoss is not None:
        config.max_daily_loss = payload.maxDailyLoss
    if payload.setupObFvg is not None:
        config.setup_ob_fvg = payload.setupObFvg
    if payload.setupLiquiditySweep is not None:
        config.setup_liquidity_sweep = payload.setupLiquiditySweep
    if payload.setupBosBreakout is not None:
        config.setup_bos_breakout = payload.setupBosBreakout
    if payload.setupTrendlineBounce is not None:
        config.setup_trendline_bounce = payload.setupTrendlineBounce
    if payload.activeSetups:
        if "OB+FVG confluence" in payload.activeSetups:
            config.setup_ob_fvg = payload.activeSetups["OB+FVG confluence"]
        if "Liquidity Sweep" in payload.activeSetups:
            config.setup_liquidity_sweep = payload.activeSetups["Liquidity Sweep"]
        if "BOS Breakout" in payload.activeSetups:
            config.setup_bos_breakout = payload.activeSetups["BOS Breakout"]
        if "Trendline Bounce" in payload.activeSetups:
            config.setup_trendline_bounce = payload.activeSetups["Trendline Bounce"]
        
    db.commit()
    log_system_event('info', "Configuration updated via API")
    return {"status": "saved"}
