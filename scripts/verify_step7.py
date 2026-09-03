"""
scripts/verify_step7.py
───────────────────────
Step 7 smoke-test: storage layer (SQLite + optionally Neon PostgreSQL).

Tests:
  1. SQLite: create tables, save signal, save trade, close trade, query stats
  2. Neon Postgres (if DB_URL set): same test suite on Neon

Run:
    python scripts/verify_step7.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import (
    Bias, BiasResult, Direction, OrderBlock, Signal, SignalType
)
from storage.db import close_engine, get_engine, init_db
from storage.models import SignalLog, Trade
from storage.repository import (
    close_trade, get_open_trades, get_trade_stats, get_trades,
    save_signal, save_trade, get_signals,
)

log = get_logger(__name__, level=settings.log_level)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_dummy_signal(direction: str = "bullish") -> Signal:
    """Build a minimal Signal object for DB testing."""
    dummy_ob = OrderBlock(
        direction=Direction.BULLISH if direction == "bullish" else Direction.BEARISH,
        timestamp=pd.Timestamp("2024-01-01 10:00", tz="UTC"),
        high=1910.0, low=1905.0, open=1908.0, close=1906.0,
        impulse_size=12.0, timeframe="M15",
    )
    dummy_bias = BiasResult(
        bias=Bias.BULLISH if direction == "bullish" else Bias.BEARISH,
        timeframe="D1",
        notes="unit test",
    )
    return Signal(
        symbol="XAUUSD",
        direction=Direction.BULLISH if direction == "bullish" else Direction.BEARISH,
        signal_type=SignalType.OB_RETEST,
        timestamp=pd.Timestamp("2024-01-01 10:05", tz="UTC"),
        entry_price=1907.50,
        stop_loss=1903.00,
        take_profit=1914.75,
        risk_reward=1.61,
        confluence_score=75.0,
        d1_bias=dummy_bias,
        h4_bias=dummy_bias,
        h1_bias=dummy_bias,
        trigger_ob=dummy_ob,
        setup_timeframe="M15",
        notes="unit test signal",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Core test suite (DB-agnostic)
# ─────────────────────────────────────────────────────────────────────────────

def run_db_tests(db_url: str, label: str) -> int:
    """Run the full CRUD test suite against `db_url`. Returns failure count."""
    failures = 0
    log.info(f"\n  Testing: {label}")

    # ── Init ──────────────────────────────────────────────────────────────────
    close_engine()   # reset singleton so we can swap URL
    try:
        init_db(db_url)
    except Exception as e:
        log.error(f"  init_db FAILED: {e}")
        return 1

    # ── 1. Save signal ────────────────────────────────────────────────────────
    sig  = _make_dummy_signal("bullish")
    try:
        sig_row = save_signal(sig, environment="backtest")
        ok1 = sig_row.id is not None and sig_row.symbol == "XAUUSD"
        log.info(f"  {'OK' if ok1 else 'FAIL'} [save_signal]  id={sig_row.id}  score={sig_row.confluence_score}")
        if not ok1: failures += 1
    except Exception as e:
        log.error(f"  FAIL [save_signal] {e}")
        return failures + 1

    # ── 2. Save trade ─────────────────────────────────────────────────────────
    try:
        trade = save_trade(
            signal_log=sig_row,
            lot_size=0.10,
            entry_price=1907.60,
            entry_time=datetime(2024, 1, 1, 10, 6, tzinfo=timezone.utc),
            environment="backtest",
            commission=7.0,
            slippage_pts=0.1,
        )
        ok2 = trade.id is not None and trade.direction == "bullish"
        log.info(f"  {'OK' if ok2 else 'FAIL'} [save_trade]  id={trade.id}  entry={trade.entry_price}")
        if not ok2: failures += 1
    except Exception as e:
        log.error(f"  FAIL [save_trade] {e}")
        return failures + 1

    # ── 3. Check signal marked executed ───────────────────────────────────────
    try:
        sigs = get_signals(symbol="XAUUSD", limit=1, executed_only=True)
        ok3  = len(sigs) >= 1 and sigs[0].executed is True
        log.info(f"  {'OK' if ok3 else 'FAIL'} [signal.executed]  executed={sigs[0].executed if sigs else 'N/A'}")
        if not ok3: failures += 1
    except Exception as e:
        log.error(f"  FAIL [signal.executed] {e}")
        failures += 1

    # ── 4. Close trade (TP hit) ───────────────────────────────────────────────
    try:
        closed = close_trade(
            trade_id=trade.id,
            exit_price=1914.75,
            exit_time=datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc),
            exit_reason="tp_hit",
            pnl=72.50,
        )
        ok4 = (closed is not None and
               closed.exit_reason == "tp_hit" and
               closed.pnl == 72.50)
        log.info(f"  {'OK' if ok4 else 'FAIL'} [close_trade]  reason={closed.exit_reason if closed else 'N/A'}  "
                 f"pnl={closed.pnl if closed else 'N/A'}")
        if not ok4: failures += 1
    except Exception as e:
        log.error(f"  FAIL [close_trade] {e}")
        failures += 1

    # ── 5. Open trades = 0 ────────────────────────────────────────────────────
    try:
        open_t = get_open_trades("XAUUSD")
        ok5    = len(open_t) == 0
        log.info(f"  {'OK' if ok5 else 'FAIL'} [open_trades=0]  open_count={len(open_t)}")
        if not ok5: failures += 1
    except Exception as e:
        log.error(f"  FAIL [get_open_trades] {e}")
        failures += 1

    # ── 6. Stats ──────────────────────────────────────────────────────────────
    try:
        stats = get_trade_stats(symbol="XAUUSD", environment="backtest")
        ok6   = (stats["total"] >= 1 and
                 stats["wins"]  >= 1 and
                 stats["total_pnl"] > 0)
        log.info(f"  {'OK' if ok6 else 'FAIL'} [stats]  "
                 f"total={stats['total']}  wins={stats['wins']}  "
                 f"win_rate={stats['win_rate']:.0%}  "
                 f"total_pnl={stats['total_pnl']:.2f}")
        if not ok6: failures += 1
    except Exception as e:
        log.error(f"  FAIL [get_trade_stats] {e}")
        failures += 1

    close_engine()
    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 65)
    log.info("STEP 7 -- Storage Layer (SQLite + Neon Postgres)")
    log.info("=" * 65)

    total_fails = 0

    # ── SQLite test (always runs) ─────────────────────────────────────────────
    sqlite_url = "sqlite:///test_verify_step7.db"
    total_fails += run_db_tests(sqlite_url, "SQLite (local)")

    # ── Neon Postgres test (runs if DB_URL is Postgres) ───────────────────────
    db_url = settings.db_url
    if db_url and ("postgresql" in db_url or "postgres" in db_url):
        log.info("\n  Neon PostgreSQL URL detected in .env — running Postgres test …")
        total_fails += run_db_tests(db_url, f"Neon PostgreSQL")
    else:
        log.info("\n  DB_URL is SQLite — skipping Postgres test.")
        log.info("  To test Neon: set DB_URL=postgresql://... in your .env")

    # ── Cleanup SQLite test DB ────────────────────────────────────────────────
    test_db = Path("test_verify_step7.db")
    if test_db.exists():
        test_db.unlink()
        log.info("\n  Cleaned up test SQLite file.")

    log.info("")
    if total_fails == 0:
        log.info("PASSED -- Step 7: storage layer working on all tested backends.")
    else:
        log.error(f"FAILED -- Step 7: {total_fails} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
