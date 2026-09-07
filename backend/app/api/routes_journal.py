from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.db.session import get_db
from app.db.models import TradeModel
from app.schemas.trade import Trade

router = APIRouter()

@router.get("/trades", response_model=List[Trade])
def get_trades(
    db: Session = Depends(get_db),
    setup_type: Optional[str] = Query(None, alias="setupType"),
    session: Optional[str] = None,
    outcome: Optional[str] = None,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, le=500)
):
    """Returns filtered trades from the journal DB."""
    query = db.query(TradeModel)
    
    if setup_type:
        query = query.filter(TradeModel.setup_type == setup_type)
    if session:
        query = query.filter(TradeModel.session == session)
    if outcome:
        query = query.filter(TradeModel.outcome == outcome)
    if from_date:
        query = query.filter(TradeModel.opened_at >= from_date)
    if to_date:
        query = query.filter(TradeModel.opened_at <= to_date)
        
    trades = query.order_by(TradeModel.opened_at.desc()).limit(limit).all()
    
    result = []
    for t in trades:
        result.append(Trade(
            id=t.id,
            symbol=t.symbol,
            direction=t.direction,
            entryPrice=t.entry_price,
            exitPrice=t.exit_price,
            sl=t.sl,
            tp=t.tp,
            rMultiple=t.r_multiple,
            outcome=t.outcome,
            setupType=t.setup_type,
            session=t.session,
            openedAt=t.opened_at,
            closedAt=t.closed_at
        ))
    return result
