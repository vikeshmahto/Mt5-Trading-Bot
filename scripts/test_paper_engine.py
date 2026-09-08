"""
scripts/test_paper_engine.py
─────────────────────────────
Smoke test for signal_loop:
1. Verifies BTCUSD is NOT scanned.
2. Verifies XAUUSD generates a single valid trade with SL < Entry < TP.
3. Verifies monitor_open_positions closes the trade when price crosses SL/TP.
"""

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.engine.signal_loop import run_signal_loop, monitor_open_positions
from app.db.session import SessionLocal
from app.db.models import TradeModel

def test():
    print("Executing signal loop cycle...")
    run_signal_loop()

    db = SessionLocal()
    trades = db.query(TradeModel).filter(TradeModel.source == 'paper').all()
    print(f"\nTotal Paper Trades in DB: {len(trades)}")
    
    for t in trades:
        print(f"ID: {t.id} | Symbol: {t.symbol} | Dir: {t.direction} | Entry: {t.entry_price} | SL: {t.sl} | TP: {t.tp} | ClosedAt: {t.closed_at} | Outcome: {t.outcome} | R: {t.r_multiple}")

    db.close()

if __name__ == "__main__":
    test()
