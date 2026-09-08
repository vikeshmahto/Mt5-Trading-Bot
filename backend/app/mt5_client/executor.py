import MetaTrader5 as mt5
import uuid
from datetime import datetime
from app.config import settings
from app.logging_setup import log_system_event
from app.schemas.trade import Trade
from app.schemas.position import Position
from app.db.session import SessionLocal
from app.db.models import TradeModel

def place_order(symbol: str, direction: str, volume: float, entry_price: float, sl: float, tp: float, setup_type: str, session: str) -> bool:
    """
    Places an order or simulates it depending on DRY_RUN.
    """
    if settings.DRY_RUN:
        log_system_event('info', f"[DRY RUN] Would execute {direction} on {symbol} | Volume: {volume} | SL: {sl} | TP: {tp}")
        
        # Simulate successful trade logging
        trade_id = f"sim_{uuid.uuid4().hex[:8]}"
        
        db = SessionLocal()
        try:
            trade = TradeModel(
                id=trade_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                setup_type=setup_type,
                session=session,
                opened_at=datetime.utcnow(),
                source="paper"
            )
            db.add(trade)
            db.commit()
            log_system_event('success', f"[DRY RUN] Simulated order {trade_id} logged to DB as paper trade.")
        except Exception as e:
            log_system_event('error', f"Failed to log dry-run trade: {e}")
        finally:
            db.close()
            
        return True
        
    else:
        # REAL TRADING LOGIC
        log_system_event('warning', f"EXECUTING LIVE TRADE ON {symbol}!")
        
        order_type = mt5.ORDER_TYPE_BUY if direction == 'long' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": entry_price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,
            "comment": f"SMC Bot: {setup_type}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log_system_event('error', f"Order send failed, retcode={result.retcode}")
            return False
            
        log_system_event('success', f"Live order executed: Ticket #{result.order}")
        
        # Log to DB
        db = SessionLocal()
        try:
            trade = TradeModel(
                id=str(result.order),
                symbol=symbol,
                direction=direction,
                entry_price=result.price,
                sl=sl,
                tp=tp,
                setup_type=setup_type,
                session=session,
                opened_at=datetime.utcnow(),
                source="live"
            )
            db.add(trade)
            db.commit()
        except Exception as e:
            log_system_event('error', f"Failed to log live trade {result.order}: {e}")
        finally:
            db.close()
            
        return True
