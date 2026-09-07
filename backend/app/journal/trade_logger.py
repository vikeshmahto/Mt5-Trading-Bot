import uuid
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models import TradeModel
from app.logging_setup import log_system_event

def close_trade(trade_id: str, exit_price: float) -> bool:
    """
    Closes a trade in the DB, calculates outcome and R-multiple.
    """
    db = SessionLocal()
    try:
        trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
        if not trade:
            log_system_event('error', f"Trade {trade_id} not found for closing.")
            return False

        trade.exit_price = exit_price
        trade.closed_at = datetime.utcnow()

        # Calculate R-multiple
        risk_distance = abs(trade.entry_price - trade.sl)
        if risk_distance > 0:
            if trade.direction == 'long':
                r = (exit_price - trade.entry_price) / risk_distance
            else:
                r = (trade.entry_price - exit_price) / risk_distance
            trade.r_multiple = round(r, 2)
        else:
            trade.r_multiple = 0.0

        # Determine outcome
        if trade.r_multiple > 0.1:
            trade.outcome = 'win'
        elif trade.r_multiple < -0.1:
            trade.outcome = 'loss'
        else:
            trade.outcome = 'breakeven'

        db.commit()
        log_system_event('success', f"Trade {trade_id} closed at {exit_price} | Outcome: {trade.outcome} | R: {trade.r_multiple}")
        return True
    except Exception as e:
        log_system_event('error', f"Failed to close trade {trade_id}: {e}")
        return False
    finally:
        db.close()
