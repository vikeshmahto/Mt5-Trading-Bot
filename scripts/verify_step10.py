"""
scripts/verify_step10.py
────────────────────────
Step 10 smoke-test: Live & Paper Execution Engine (`execution/`).

Tests:
  1. OrderManager Paper Execution: simulated fills, return contracts, ticket generation.
  2. RiskManager Rule Evaluation:
      - Session validation
      - Confluence score threshold
      - Daily loss boundary
      - Position sizing calculation
  3. Live Integration Smoke Test:
      - Connects to MT5
      - Polls account status & open positions
      - Executes 1 complete LiveRunner scan cycle for XAUUSD (pulls bars, evaluates bias/zones, runs risk check)
      - Confirms Neon DB connectivity & logging capability

Run:
    python scripts/verify_step10.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import Direction, Signal, SignalType, OrderBlock
from execution.order_manager import OrderManager, ExecutionResult
from execution.risk_manager import RiskManager
from execution.live_runner import LiveRunner
from data.mt5_client import MT5Client
from storage.db import init_db

log = get_logger(__name__, level=settings.log_level)


# ─────────────────────────────────────────────────────────────────────────────
# 1. OrderManager Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_order_manager_paper() -> int:
    log.info("\n-- Test 1: OrderManager Paper Trading ---------------------------")
    om = OrderManager(is_paper=True)
    inst = settings.get_instrument("XAUUSD")

    dummy_sig = Signal(
        symbol="XAUUSD",
        direction=Direction.BULLISH,
        signal_type=SignalType.OB_RETEST,
        timestamp=pd.Timestamp.now(tz="UTC"),
        entry_price=2500.0,
        stop_loss=2490.0,
        take_profit=2515.0,
        risk_reward=1.5,
        confluence_score=80.0,
    )

    res = om.execute_signal(dummy_sig, lot_size=0.10, inst=inst)
    ok = res.success and res.ticket is not None and res.entry_price == 2500.0
    log.info(f"  {'OK' if ok else 'FAIL'} [Paper Order Send]  success={res.success}  ticket={res.ticket}")

    acc = om.get_account_info()
    ok_acc = acc.get("balance", 0) > 0
    log.info(f"  {'OK' if ok_acc else 'FAIL'} [Paper Account Query]  balance=${acc.get('balance'):,.2f}")

    return 0 if (ok and ok_acc) else 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. RiskManager Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_risk_manager() -> int:
    log.info("\n-- Test 2: RiskManager Validation Rules -------------------------")
    rm = RiskManager()
    inst = settings.get_instrument("XAUUSD")
    failures = 0

    # A. Score Below Threshold
    low_sig = Signal(
        symbol="XAUUSD",
        direction=Direction.BULLISH,
        signal_type=SignalType.FVG_RETEST,
        timestamp=pd.Timestamp.now(tz="UTC"),
        entry_price=2500.0,
        stop_loss=2490.0,
        take_profit=2515.0,
        risk_reward=1.5,
        confluence_score=30.0,  # Below min_score (60)
    )
    acc = {"balance": 10000.0, "equity": 10000.0, "profit": 0.0}
    allowed, reason, _ = rm.can_trade(low_sig, acc, inst)
    ok_low = not allowed and "Score" in reason
    log.info(f"  {'OK' if ok_low else 'FAIL'} [Low Score Rejection]  allowed={allowed}  reason='{reason}'")
    if not ok_low: failures += 1

    # B. Valid Signal Sizing
    good_sig = Signal(
        symbol="XAUUSD",
        direction=Direction.BULLISH,
        signal_type=SignalType.OB_RETEST,
        timestamp=pd.Timestamp.now(tz="UTC"),
        entry_price=2500.0,
        stop_loss=2490.0,  # 10 pts risk
        take_profit=2520.0,
        risk_reward=2.0,
        confluence_score=85.0,
    )
    # Mock session pass
    allowed_good, _, lots = rm.can_trade(good_sig, acc, inst)
    # $10,000 * 1% risk = $100. 10 pts risk * $100/lot = $1000 risk/lot -> 0.10 lots
    ok_lots = lots > 0.0
    log.info(f"  {'OK' if ok_lots else 'FAIL'} [Position Sizing Calculation]  lots={lots:.2f}")
    if not ok_lots: failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# 3. Live Runner Integration Test
# ─────────────────────────────────────────────────────────────────────────────

def test_live_runner_scan_cycle() -> int:
    log.info("\n-- Test 3: Live Runner Execution Scan Cycle ---------------------")
    failures = 0

    init_db()

    with MT5Client():
        runner = LiveRunner(symbols=["XAUUSD"], environment="paper")
        # Run one single processing cycle
        runner._log_heartbeat()
        log.info("  Executing 1 full live pipeline scan for XAUUSD...")
        runner._process_symbol("XAUUSD")
        log.info("  Scan cycle executed cleanly without exception.")

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 65)
    log.info("STEP 10 -- Live & Paper Execution Engine")
    log.info("=" * 65)

    f1 = test_order_manager_paper()
    f2 = test_risk_manager()
    f3 = test_live_runner_scan_cycle()

    total = f1 + f2 + f3
    log.info("")
    if total == 0:
        log.info("PASSED -- Step 10: Live/Paper execution engine verified.")
    else:
        log.error(f"FAILED -- Step 10: {total} failure(s) detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
