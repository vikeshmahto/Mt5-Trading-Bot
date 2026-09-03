"""
scripts/verify_step6.py
───────────────────────
Step 6 smoke-test: generate_signal() — guard conditions + live data.

Tests:
  1. Signal dataclass construction and property correctness
  2. Conflicting bias (1 bull / 1 bear) returns None
  3. Empty M1 DataFrame returns None
  4. No zones on M15 returns None
  5. Live MT5 run — prints current market analysis

Run:
    python scripts/verify_step6.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import Direction, Signal, SignalType, OrderBlock, FairValueGap
from signals.generator import generate_signal
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi

log = get_logger(__name__, level=settings.log_level)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_bars(n, base, trend="up", freq="h", start="2024-01-01") -> pd.DataFrame:
    np.random.seed(42)
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    p = base
    opens, closes, highs, lows = [], [], [], []
    for _ in range(n):
        if trend == "up":   p += np.random.uniform(0.5, 2.0)
        elif trend == "down": p -= np.random.uniform(0.5, 2.0)
        else: p += np.random.uniform(-1.0, 1.0)
        o = p
        c = o + (np.random.uniform(0.2,1.5) if trend=="up"
                 else -np.random.uniform(0.2,1.5) if trend=="down"
                 else np.random.uniform(-1,1))
        opens.append(o); closes.append(c)
        highs.append(max(o,c)+np.random.uniform(0.1,1)); lows.append(min(o,c)-np.random.uniform(0.1,1))
    df = pd.DataFrame({"open":opens,"high":highs,"low":lows,"close":closes,"tick_volume":100}, index=idx)
    df.index.name = "timestamp"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic tests
# ─────────────────────────────────────────────────────────────────────────────

def run_synthetic_tests() -> int:
    failures = 0

    # ── Test 1: Signal dataclass + property correctness ───────────────────────
    dummy_ob = OrderBlock(
        direction=Direction.BULLISH,
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        high=1010.0, low=1005.0, open=1008.0, close=1006.0,
        impulse_size=15.0, timeframe="M15",
    )
    s = Signal(
        symbol="XAUUSD", direction=Direction.BULLISH,
        signal_type=SignalType.OB_RETEST,
        timestamp=pd.Timestamp("2024-01-02", tz="UTC"),
        entry_price=1007.0, stop_loss=1003.0, take_profit=1013.0,
        risk_reward=1.5, confluence_score=75.0,
        trigger_ob=dummy_ob, setup_timeframe="M15", notes="unit test",
    )
    ok1 = (s.risk_points == 4.0 and
           s.reward_points == 6.0 and
           str(s).startswith("[XAUUSD] LONG"))
    log.info(f"  {'OK' if ok1 else 'FAIL'} [Test 1 - Signal properties]  "
             f"risk={s.risk_points}  reward={s.reward_points}  str_ok={str(s).startswith('[XAUUSD]')}")
    if not ok1: failures += 1

    # ── Test 2: Conflicting bias (1 bull D1 / 1 bear H4 / 1 bull H1) → None ──
    bars2 = {
        "D1":  _make_bars(200, 1000, trend="up",   freq="D"),
        "H4":  _make_bars(300, 1000, trend="down", freq="4h"),
        "H1":  _make_bars(300, 1000, trend="up",   freq="h"),
        "M15": _make_bars(100, 1000, trend="flat",  freq="15min"),
        "M1":  _make_bars(50,  1000, trend="flat",  freq="min"),
    }
    sig2 = generate_signal(bars2, symbol="XAUUSD")
    ok2  = sig2 is None
    log.info(f"  {'OK' if ok2 else 'FAIL'} [Test 2 - Conflicting bias -> None]  "
             f"got={'None' if sig2 is None else sig2.direction.value}")
    if not ok2: failures += 1

    # ── Test 3: Empty M1 → None ───────────────────────────────────────────────
    bars3 = {
        "D1":  _make_bars(200, 1000, trend="up", freq="D"),
        "H4":  _make_bars(300, 1000, trend="up", freq="4h"),
        "H1":  _make_bars(300, 1000, trend="up", freq="h"),
        "M15": _make_bars(100, 1000, trend="up", freq="15min"),
        "M1":  pd.DataFrame(),
    }
    sig3 = generate_signal(bars3, symbol="XAUUSD")
    ok3  = sig3 is None
    log.info(f"  {'OK' if ok3 else 'FAIL'} [Test 3 - Empty M1 -> None]  "
             f"got={'None' if sig3 is None else 'Signal'}")
    if not ok3: failures += 1

    # ── Test 4: No M15 zone (pure flat data) → None ───────────────────────────
    bars4 = {
        "D1":  _make_bars(200, 1000, trend="up",   freq="D"),
        "H4":  _make_bars(300, 1000, trend="up",   freq="4h"),
        "H1":  _make_bars(300, 1000, trend="up",   freq="h"),
        "M15": _make_bars(100, 1000, trend="flat",  freq="15min"),
        "M1":  _make_bars(50,  1000, trend="flat",  freq="min"),
    }
    sig4 = generate_signal(bars4, symbol="XAUUSD")
    ok4  = sig4 is None
    log.info(f"  {'OK' if ok4 else 'FAIL'} [Test 4 - No zones -> None]  "
             f"got={'None' if sig4 is None else 'Signal'}")
    if not ok4: failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Live MT5 test
# ─────────────────────────────────────────────────────────────────────────────

def run_live_test() -> None:
    log.info("\n-- Live MT5 test ------------------------------------------------")
    SYMBOL = "XAUUSD"
    TFS    = ["D1", "H4", "H1", "M15", "M1"]
    N      = {"D1": 365, "H4": 500, "H1": 500, "M15": 500, "M1": 500}

    with MT5Client():
        bars = fetch_multi(SYMBOL, TFS, N, include_open=False)

    sig = generate_signal(bars, symbol=SYMBOL)

    if sig is None:
        log.info(f"  [{SYMBOL}] generate_signal -> None")
        log.info("  (No qualifying setup right now — correct behaviour.)")
        log.info("  Current bias snapshot:")
        from signals.bias import get_multi_tf_bias
        bias_tfs = {k: bars[k] for k in ["D1","H4","H1"] if not bars[k].empty}
        br = get_multi_tf_bias(bias_tfs)
        for tf, r in br.items():
            log.info(f"    {r}")

        # Show what zones ARE present even without a signal
        from signals.order_blocks import detect_order_blocks, get_unmitigated_obs
        from signals.fvg import detect_fvgs, get_fresh_fvgs
        from core.types import Direction as Dir
        for tf in ["H1", "M15"]:
            df = bars.get(tf, pd.DataFrame())
            if df.empty: continue
            obs = detect_order_blocks(df, timeframe=tf)
            fvgs = detect_fvgs(df, timeframe=tf)
            fresh_bull_ob  = get_unmitigated_obs(obs, Dir.BULLISH, 2)
            fresh_bear_ob  = get_unmitigated_obs(obs, Dir.BEARISH, 2)
            fresh_bull_fvg = get_fresh_fvgs(fvgs, Dir.BULLISH, 2)
            fresh_bear_fvg = get_fresh_fvgs(fvgs, Dir.BEARISH, 2)
            log.info(f"  {tf}: {len(fresh_bull_ob)} fresh bull OBs | "
                     f"{len(fresh_bear_ob)} fresh bear OBs | "
                     f"{len(fresh_bull_fvg)} fresh bull FVGs | "
                     f"{len(fresh_bear_fvg)} fresh bear FVGs")
    else:
        log.info(f"\n  SIGNAL FOUND:")
        log.info(f"  {sig}")
        log.info(f"  Type       : {sig.signal_type.value}")
        log.info(f"  Setup TF   : {sig.setup_timeframe}")
        log.info(f"  Entry      : {sig.entry_price:.2f}")
        log.info(f"  Stop Loss  : {sig.stop_loss:.2f}  (risk={sig.risk_points:.2f} pts)")
        log.info(f"  Take Profit: {sig.take_profit:.2f}  (reward={sig.reward_points:.2f} pts)")
        log.info(f"  R:R        : {sig.risk_reward:.2f}")
        log.info(f"  Score      : {sig.confluence_score:.0f}/100")
        log.info(f"  Notes      : {sig.notes}")
        if sig.trigger_ob:
            log.info(f"  OB zone    : [{sig.trigger_ob.low:.2f}-{sig.trigger_ob.high:.2f}]")
        if sig.trigger_fvg:
            log.info(f"  FVG zone   : [{sig.trigger_fvg.bottom:.2f}-{sig.trigger_fvg.top:.2f}]")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 65)
    log.info("STEP 6 -- generate_signal() (Synthetic + Live)")
    log.info("=" * 65)

    log.info("\n-- Synthetic tests ----------------------------------------------")
    synth_fails = run_synthetic_tests()

    run_live_test()

    log.info("")
    if synth_fails == 0:
        log.info("PASSED -- Step 6: generate_signal() pure function working.")
    else:
        log.error(f"FAILED -- Step 6: {synth_fails} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
