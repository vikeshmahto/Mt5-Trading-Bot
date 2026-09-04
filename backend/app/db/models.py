from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.session import Base
from datetime import datetime

class TradeModel(Base):
    __tablename__ = "trades"
    
    id = Column(String, primary_key=True, index=True)
    symbol = Column(String, index=True)
    direction = Column(String) # 'long' | 'short'
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    sl = Column(Float)
    tp = Column(Float)
    r_multiple = Column(Float, nullable=True)
    outcome = Column(String, nullable=True) # 'win' | 'loss' | 'breakeven'
    setup_type = Column(String, index=True)
    session = Column(String) # 'asian' | 'london' | 'ny'
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

class LogEntryModel(Base):
    __tablename__ = "logs"
    
    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String) # 'info' | 'warning' | 'error' | 'success'
    message = Column(String)

class ConfigModel(Base):
    __tablename__ = "config"
    
    id = Column(Integer, primary_key=True, index=True, default=1)
    risk_per_trade = Column(Float, default=1.0)
    daily_circuit_breaker = Column(Boolean, default=False)
    max_daily_loss = Column(Float, default=3.0)
    
    # Active Setups
    setup_ob_fvg = Column(Boolean, default=True)
    setup_liquidity_sweep = Column(Boolean, default=True)
    setup_bos_breakout = Column(Boolean, default=False)
    setup_trendline_bounce = Column(Boolean, default=False)
