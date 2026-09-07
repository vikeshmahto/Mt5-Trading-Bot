from app.db.session import SessionLocal
from app.db.models import TradeModel
import pandas as pd
from datetime import datetime

def get_analytics_summary() -> dict:
    """
    Returns win rate, total trades, avg R-multiple, current equity.
    """
    db = SessionLocal()
    try:
        trades = db.query(TradeModel).filter(TradeModel.closed_at.isnot(None)).all()
        total_trades = len(trades)
        
        if total_trades == 0:
            return {
                "winRate": 0,
                "totalTrades": 0,
                "avgRMultiple": 0.0,
                "totalEquity": 10000.0 # Starting equity mockup
            }
            
        wins = sum(1 for t in trades if t.outcome == 'win')
        win_rate = (wins / total_trades) * 100
        
        # Calculate R-multiples skipping Nones
        r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
        
        # Simple mockup of equity curve starting at 10000 assuming $100 per 1R
        total_equity = 10000.0 + (sum(r_multiples) * 100)
        
        return {
            "winRate": round(win_rate, 2),
            "totalTrades": total_trades,
            "avgRMultiple": round(avg_r, 2),
            "totalEquity": round(total_equity, 2)
        }
    finally:
        db.close()

def get_equity_curve() -> list:
    """
    Computes cumulative P&L series from the trades table.
    """
    db = SessionLocal()
    try:
        trades = db.query(TradeModel).filter(TradeModel.closed_at.isnot(None)).order_by(TradeModel.closed_at.asc()).all()
        
        curve = []
        equity = 10000.0
        for t in trades:
            if t.r_multiple is not None:
                equity += (t.r_multiple * 100) # Assuming $100 risk per 1R
            curve.append({
                "date": t.closed_at.strftime("%b %d"),
                "value": round(equity, 2)
            })
            
        return curve
    finally:
        db.close()

def get_win_rate_breakdown() -> list:
    """
    Win rate grouped by setupType.
    """
    db = SessionLocal()
    try:
        # We group by setup type manually for simplicity
        trades = db.query(TradeModel).filter(TradeModel.closed_at.isnot(None)).all()
        
        df = pd.DataFrame([{
            'setup_type': t.setup_type,
            'outcome': t.outcome
        } for t in trades])
        
        if df.empty:
            return []
            
        breakdown = []
        for setup in df['setup_type'].unique():
            setup_trades = df[df['setup_type'] == setup]
            wins = len(setup_trades[setup_trades['outcome'] == 'win'])
            wr = (wins / len(setup_trades)) * 100
            
            breakdown.append({
                "name": setup,
                "winRate": round(wr, 2)
            })
            
        return breakdown
    finally:
        db.close()
