from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid
from app.db.session import get_db
from app.db.models import TradeModel
from app.schemas.trade import Trade, TradeCreate, TradeUpdate
from app.logging_setup import log_system_event

router = APIRouter()

def _to_trade_schema(t: TradeModel) -> Trade:
    d = (t.direction or "").lower()
    norm_dir = "long" if "bull" in d or "long" in d else "short"

    return Trade(
        id=t.id,
        symbol=t.symbol,
        direction=norm_dir,
        entryPrice=t.entry_price,
        exitPrice=t.exit_price,
        sl=t.sl,
        tp=t.tp,
        rMultiple=t.r_multiple,
        outcome=t.outcome,
        setupType=t.setup_type,
        session=t.session,
        openedAt=t.opened_at,
        closedAt=t.closed_at,
        source=getattr(t, "source", None) or "paper",
        htfBias=t.htf_bias,
        htfReason=t.htf_reason,
        biasCorrect=t.bias_correct,
        setupTimeframe=t.setup_timeframe,
        confluence=t.confluence,
        screenshotUrl=t.screenshot_url,
        entryTimeframe=t.entry_timeframe,
        entryTrigger=t.entry_trigger,
        slLogic=t.sl_logic,
        plannedRr=t.planned_rr,
        riskPct=t.risk_pct,
        pointsCaptured=t.points_captured,
        mae=t.mae,
        mfe=t.mfe,
        ruleAdherence=t.rule_adherence,
        emotionalState=t.emotional_state,
        externalFactor=t.external_factor,
        textbookComparison=t.textbook_comparison,
        mistakeType=t.mistake_type,
        reviewNotes=t.review_notes,
    )

@router.get("/trades", response_model=List[Trade])
def get_trades(
    db: Session = Depends(get_db),
    symbol: Optional[str] = None,
    setup_type: Optional[str] = Query(None, alias="setupType"),
    session: Optional[str] = None,
    outcome: Optional[str] = None,
    source: Optional[str] = Query(None),
    htf_bias: Optional[str] = Query(None, alias="htfBias"),
    mistake_type: Optional[str] = Query(None, alias="mistakeType"),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(500, le=1000)
):
    """Returns filtered trades from the journal DB with SMC diagnostic metadata."""
    query = db.query(TradeModel)
    
    if symbol:
        query = query.filter(TradeModel.symbol == symbol)
    if setup_type:
        query = query.filter(TradeModel.setup_type == setup_type)
    if session:
        query = query.filter(TradeModel.session == session)
    if outcome:
        query = query.filter(TradeModel.outcome == outcome)
    if source and source != "all":
        query = query.filter(TradeModel.source == source)
    if htf_bias:
        query = query.filter(TradeModel.htf_bias == htf_bias)
    if mistake_type:
        query = query.filter(TradeModel.mistake_type == mistake_type)
    if from_date:
        query = query.filter(TradeModel.opened_at >= from_date)
    if to_date:
        query = query.filter(TradeModel.opened_at <= to_date)
        
    trades = query.order_by(TradeModel.opened_at.desc()).limit(limit).all()
    return [_to_trade_schema(t) for t in trades]

@router.post("/trades", response_model=Trade)
def create_trade(payload: TradeCreate, db: Session = Depends(get_db)):
    """Logs a new trade with complete SMC context, execution, and diagnostic tags."""
    trade_id = payload.id or f"manual-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
    
    # Infer trade source
    if payload.source and payload.source != "paper":
        trade_source = payload.source
    elif trade_id.startswith("manual-"):
        trade_source = "manual_note"
    elif trade_id.startswith("bt-"):
        trade_source = "backtest"
    else:
        trade_source = payload.source or "paper"

    # Auto calculate points captured if exit price provided
    points = payload.points_captured
    if points is None and payload.exit_price is not None:
        if payload.direction == "long":
            points = round(payload.exit_price - payload.entry_price, 2)
        else:
            points = round(payload.entry_price - payload.exit_price, 2)

    # Auto calculate R-multiple if outcome and SL provided
    r_mult = payload.r_multiple
    if r_mult is None and payload.exit_price is not None and payload.sl is not None:
        risk = abs(payload.entry_price - payload.sl)
        if risk > 0:
            if payload.direction == "long":
                r_mult = round((payload.exit_price - payload.entry_price) / risk, 2)
            else:
                r_mult = round((payload.entry_price - payload.exit_price) / risk, 2)

    db_trade = TradeModel(
        id=trade_id,
        symbol=payload.symbol.upper(),
        direction=payload.direction,
        entry_price=payload.entry_price,
        exit_price=payload.exit_price,
        sl=payload.sl,
        tp=payload.tp,
        r_multiple=r_mult,
        outcome=payload.outcome,
        setup_type=payload.setup_type,
        session=payload.session,
        opened_at=payload.opened_at or datetime.utcnow(),
        closed_at=payload.closed_at,
        source=trade_source,
        htf_bias=payload.htf_bias,
        htf_reason=payload.htf_reason,
        bias_correct=payload.bias_correct,
        setup_timeframe=payload.setup_timeframe or "M15",
        confluence=payload.confluence,
        screenshot_url=payload.screenshot_url,
        entry_timeframe=payload.entry_timeframe or "M1",
        entry_trigger=payload.entry_trigger,
        sl_logic=payload.sl_logic,
        planned_rr=payload.planned_rr,
        risk_pct=payload.risk_pct or 1.0,
        points_captured=points,
        mae=payload.mae,
        mfe=payload.mfe,
        rule_adherence=payload.rule_adherence,
        emotional_state=payload.emotional_state,
        external_factor=payload.external_factor,
        textbook_comparison=payload.textbook_comparison,
        mistake_type=payload.mistake_type,
        review_notes=payload.review_notes,
    )
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    
    log_system_event('info', f"Logged journal trade {trade_id} on {db_trade.symbol} ({db_trade.setup_type}) [{trade_source}]")
    return _to_trade_schema(db_trade)

@router.put("/trades/{trade_id}", response_model=Trade)
def update_trade(trade_id: str, payload: TradeUpdate, db: Session = Depends(get_db)):
    """Updates an existing trade with post-trade review, mistakes, and diagnosis."""
    trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
        
    update_data = payload.model_dump(exclude_unset=True)
    
    # Map camelCase to snake_case attributes
    mapping = {
        "entry_price": "entry_price",
        "exit_price": "exit_price",
        "r_multiple": "r_multiple",
        "setup_type": "setup_type",
        "opened_at": "opened_at",
        "closed_at": "closed_at",
        "source": "source",
        "htf_bias": "htf_bias",
        "htf_reason": "htf_reason",
        "bias_correct": "bias_correct",
        "setup_timeframe": "setup_timeframe",
        "confluence": "confluence",
        "screenshot_url": "screenshot_url",
        "entry_timeframe": "entry_timeframe",
        "entry_trigger": "entry_trigger",
        "sl_logic": "sl_logic",
        "planned_rr": "planned_rr",
        "risk_pct": "risk_pct",
        "points_captured": "points_captured",
        "mae": "mae",
        "mfe": "mfe",
        "rule_adherence": "rule_adherence",
        "emotional_state": "emotional_state",
        "external_factor": "external_factor",
        "textbook_comparison": "textbook_comparison",
        "mistake_type": "mistake_type",
        "review_notes": "review_notes",
    }
    
    for key, val in update_data.items():
        attr = mapping.get(key, key)
        if hasattr(trade, attr):
            setattr(trade, attr, val)
            
    db.commit()
    db.refresh(trade)
    return _to_trade_schema(trade)

@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: str, db: Session = Depends(get_db)):
    """Deletes a trade entry from the journal."""
    trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()
    return {"status": "deleted", "id": trade_id}

