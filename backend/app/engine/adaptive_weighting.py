from app.db.session import SessionLocal
from app.db.models import TradeModel, ConfigModel
from app.config import settings
from app.logging_setup import log_system_event

def check_setup_winrate(setup_type: str):
    """
    Checks the rolling win rate for a specific setup type.
    If it falls below the minimum threshold, disables the setup in config.
    """
    db = SessionLocal()
    try:
        # Get the last N closed trades for this setup type
        recent_trades = db.query(TradeModel).filter(
            TradeModel.setup_type == setup_type,
            TradeModel.outcome.isnot(None)
        ).order_by(TradeModel.closed_at.desc()).limit(settings.ROLLING_WINRATE_TRADES).all()
        
        if len(recent_trades) < settings.ROLLING_WINRATE_TRADES:
            return # Not enough data
            
        wins = sum(1 for t in recent_trades if t.outcome == 'win')
        winrate = wins / len(recent_trades)
        
        if winrate < settings.MIN_WINRATE_THRESHOLD:
            config = db.query(ConfigModel).first()
            if config:
                # Disable the specific setup
                if setup_type == "ob_fvg" and config.setup_ob_fvg:
                    config.setup_ob_fvg = False
                elif setup_type == "liquidity_sweep" and config.setup_liquidity_sweep:
                    config.setup_liquidity_sweep = False
                elif setup_type == "bos_breakout" and config.setup_bos_breakout:
                    config.setup_bos_breakout = False
                elif setup_type == "trendline_bounce" and config.setup_trendline_bounce:
                    config.setup_trendline_bounce = False
                    
                db.commit()
                log_system_event('warning', f"Disabled {setup_type} setup due to low win rate: {winrate*100:.1f}%")
                
    finally:
        db.close()

def evaluate_all_setups():
    setups = ["ob_fvg", "liquidity_sweep", "bos_breakout", "trendline_bounce"]
    for setup in setups:
        check_setup_winrate(setup)
