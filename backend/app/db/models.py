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
    source = Column(String, default="paper", index=True) # 'paper' | 'backtest' | 'live' | 'manual_note'

    # 1. Context / Bias
    htf_bias = Column(String, nullable=True) # 'bullish' | 'bearish' | 'range'
    htf_reason = Column(String, nullable=True) # structure, key levels
    bias_correct = Column(String, nullable=True) # 'yes' | 'no' | 'partial'

    # 2. Setup
    setup_timeframe = Column(String, nullable=True, default="M15") # 'M15' | 'H1' | 'H4'
    confluence = Column(String, nullable=True) # 'single' | 'double' | 'triple_stack'
    screenshot_url = Column(String, nullable=True)

    # 3. Execution
    entry_timeframe = Column(String, nullable=True, default="M1") # 'M1' | 'M5'
    entry_trigger = Column(String, nullable=True) # 'clean_retest' | 'chased' | 'limit_order'
    sl_logic = Column(String, nullable=True) # 'structure' | 'atr' | 'sweep_low'
    planned_rr = Column(Float, nullable=True)
    risk_pct = Column(Float, nullable=True, default=1.0) # risk % of account

    # 4. Outcome & Excursion
    points_captured = Column(Float, nullable=True)
    mae = Column(Float, nullable=True) # max adverse excursion
    mfe = Column(Float, nullable=True) # max favorable excursion

    # 5. Process & Psychology
    rule_adherence = Column(String, nullable=True) # 'followed_rules' | 'early_entry' | 'moved_sl' | 'closed_early' | 'chased'
    emotional_state = Column(String, nullable=True) # 'calm' | 'fomo' | 'revenge' | 'tilted' | 'confident'
    external_factor = Column(String, nullable=True) # 'news_event' | 'low_liquidity' | 'normal'

    # 6. Post-trade review
    textbook_comparison = Column(String, nullable=True)
    mistake_type = Column(String, nullable=True) # 'clean' | 'wrong_bias' | 'bad_entry_timing' | 'ignored_htf' | 'sized_wrong' | 'moved_sl'
    review_notes = Column(String, nullable=True)

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
    
    # Paper Trading Evaluation Config
    paper_trading_start_date = Column(String, default="2026-09-08T17:30:00Z")
    setup_ob_fvg = Column(Boolean, default=True)
    setup_liquidity_sweep = Column(Boolean, default=True)
    setup_bos_breakout = Column(Boolean, default=False)
    setup_trendline_bounce = Column(Boolean, default=False)
