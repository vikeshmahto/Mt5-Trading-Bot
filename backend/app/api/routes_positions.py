from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
import MetaTrader5 as mt5
from app.schemas.position import Position
from app.journal.trade_logger import close_trade
from app.logging_setup import log_system_event
from app.config import settings

router = APIRouter()

@router.get("/positions", response_model=List[Position])
def get_positions():
    """Returns all currently open positions from MT5 (or empty if not connected)."""
    positions = []
    
    try:
        mt5_positions = mt5.positions_get()
        if mt5_positions is None:
            return []

        for pos in mt5_positions:
            direction = "long" if pos.type == mt5.POSITION_TYPE_BUY else "short"
            floating_pnl = pos.profit

            positions.append(Position(
                id=str(pos.ticket),
                symbol=pos.symbol,
                direction=direction,
                entryPrice=pos.price_open,
                currentPrice=pos.price_current,
                sl=pos.sl,
                tp=pos.tp,
                floatingPnl=floating_pnl,
                openedAt=datetime.utcfromtimestamp(pos.time)
            ))
    except Exception as e:
        log_system_event('warning', f"Could not fetch live positions: {e}")
        
    return positions

@router.post("/positions/{position_id}/close")
def close_position(position_id: str):
    """Closes a specific position (respects DRY_RUN) and logs the trade."""
    if settings.DRY_RUN:
        # Simulate close
        log_system_event('info', f"[DRY RUN] Would close position {position_id}")
        success = close_trade(position_id, exit_price=0.0)  # Price 0.0 as placeholder in dry run
        if not success:
            raise HTTPException(status_code=404, detail="Trade not found in DB")
        return {"status": "closed", "dryRun": True}
    else:
        # Real close via MT5
        position = mt5.positions_get(ticket=int(position_id))
        if not position:
            raise HTTPException(status_code=404, detail="Position not found in MT5")
            
        pos = position[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pos.symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "SMC Bot: Manual close",
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise HTTPException(status_code=500, detail=f"MT5 close failed: {result.retcode}")
            
        close_trade(position_id, exit_price=result.price)
        return {"status": "closed", "dryRun": False}
