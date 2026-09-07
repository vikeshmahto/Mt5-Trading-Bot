import MetaTrader5 as mt5
from app.db.session import SessionLocal
from app.db.models import ConfigModel, TradeModel
from app.logging_setup import log_system_event
from datetime import datetime

def check_daily_circuit_breaker() -> bool:
    """
    Checks if the daily loss exceeds the max_daily_loss limit.
    Returns True if trading should be paused.
    """
    db = SessionLocal()
    try:
        config = db.query(ConfigModel).first()
        if not config or not config.daily_circuit_breaker:
            return False
            
        today = datetime.utcnow().date()
        # Calculate today's PnL (using R-multiple or absolute depending on how it's stored, 
        # for simplicity assuming R-multiple is tracked and -1R per loss)
        today_trades = db.query(TradeModel).filter(
            TradeModel.closed_at >= datetime(today.year, today.month, today.day)
        ).all()
        
        daily_loss_r = sum(t.r_multiple for t in today_trades if t.r_multiple is not None and t.r_multiple < 0)
        
        # If daily_loss_r (e.g. -4) <= -max_daily_loss (e.g. -3)
        if abs(daily_loss_r) >= config.max_daily_loss:
            log_system_event('error', f"Daily circuit breaker hit! Loss: {abs(daily_loss_r)}R >= Limit: {config.max_daily_loss}R")
            return True
            
        return False
    finally:
        db.close()

def calculate_position_size(symbol: str, risk_percent: float, entry_price: float, sl_price: float) -> float:
    """
    Calculates the position size based on account balance and risk percentage.
    """
    account_info = mt5.account_info()
    if not account_info:
        log_system_event('error', "Failed to get account info for position sizing")
        return 0.01 # Fallback minimum lot size
        
    balance = account_info.balance
    risk_amount = balance * (risk_percent / 100.0)
    
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        return 0.01
        
    # Standard forex calculation (Simplified)
    # Risk = Volume * ContractSize * (Entry - SL)
    tick_size = symbol_info.trade_tick_size
    tick_value = symbol_info.trade_tick_value
    
    # Distance in ticks
    distance = abs(entry_price - sl_price) / tick_size
    if distance == 0:
        return 0.01
        
    # Calculate volume
    volume = risk_amount / (distance * tick_value)
    
    # Normalize volume
    volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
    
    if volume < symbol_info.volume_min:
        volume = symbol_info.volume_min
    if volume > symbol_info.volume_max:
        volume = symbol_info.volume_max
        
    return float(volume)
