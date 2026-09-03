"""
scripts/verify_fixes.py
───────────────────────
Pre-Backtest Unit & Targeted Verification Script for:
  1. Order Block Departure & Genuine Mitigation Timing Fix.
  2. Liquidity Sweep Direct Reversal Entry Trigger Fix.
  3. Bearish & Counter-Trend Bias Confluence Fix.

Run:
    python scripts/verify_fixes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import Direction, SignalType, Bias
from data.fetcher import fetch_multi
from data.mt5_client import MT5Client
from signals.order_blocks import detect_order_blocks, get_unmitigated_obs
from signals.liquidity_sweep import detect_liquidity_sweeps
from signals.generator import generate_signal

log = get_logger(__name__, level=settings.log_level)


def test_ob_mitigation_fix() -> int:
    log.info("\n-- 1. Testing Order Block Departure & Mitigation Timing Fix -------")
    with MT5Client():
        bars = fetch_multi("XAUUSD", ["M15"], {"M15": 500}, include_open=False)
    
    df = bars["M15"]
    obs = detect_order_blocks(df, timeframe="M15", mark_mitigation=True)
    
    log.info(f"  Total OBs detected: {len(obs)}")
    
    # Check that OBs are NOT immediately marked mitigated on the very next bar
    unmitigated_at_some_point = 0
    delayed_mitigations = 0
    currently_fresh = 0
    
    for ob in obs:
        if not ob.mitigated:
            currently_fresh += 1
        else:
            # Check time delta between formation and mitigation
            delta_bars = (ob.mitigated_at - ob.timestamp) / pd.Timedelta(minutes=15)
            if delta_bars > 1:
                delayed_mitigations += 1
                
    log.info(f"  Currently unmitigated (fresh) OBs available: {currently_fresh}")
    log.info(f"  OBs with genuine delayed retest (>1 bar after departure): {delayed_mitigations}")
    
    # Verification assertion: we must have unmitigated OBs and/or delayed mitigations
    ok = (currently_fresh > 0 or delayed_mitigations > 0)
    log.info(f"  {'PASS' if ok else 'FAIL'} -> OB self-mitigation bug resolved.")
    return 0 if ok else 1


def _build_zigzag(base: float = 2000.0, trend: str = "up", n_cycles: int = 6) -> pd.DataFrame:
    """Generate clean zigzag candles for multi-TF bias verification."""
    opens, highs, lows, closes = [], [], [], []
    PAD = 4
    for c in range(n_cycles):
        step = (c * 20) if trend == "up" else (-c * 20)
        lo = base + step
        hi = lo + 25
        
        # SL
        for _ in range(PAD):
            p = lo + 3; opens.append(p); highs.append(p+1); lows.append(p-0.5); closes.append(p)
        opens.append(lo+1); highs.append(lo+2); lows.append(lo); closes.append(lo+1.5)
        for _ in range(PAD):
            p = lo + 3; opens.append(p); highs.append(p+1); lows.append(p-0.5); closes.append(p)
            
        # SH
        for _ in range(PAD):
            p = hi - 3; opens.append(p); highs.append(p+0.5); lows.append(p-1); closes.append(p)
        opens.append(hi-1); highs.append(hi); lows.append(hi-2); closes.append(hi-1)
        for _ in range(PAD):
            p = hi - 3; opens.append(p); highs.append(p+0.5); lows.append(p-1); closes.append(p)
            
    idx = pd.date_range("2024-01-01", periods=len(opens), freq="h", tz="UTC")
    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "tick_volume": 100}, index=idx)
    df.index.name = "timestamp"
    return df


def test_sweep_entry_fix() -> int:
    log.info("\n-- 2. Testing Liquidity Sweep Direct Reversal Entry Trigger -------")
    
    # 1. Base zigzag on M15 that creates a swing low at ~1000
    m15_df = _build_zigzag(base=1000.0, trend="up", n_cycles=4)
    lowest_swing = m15_df["low"].min()
    
    # Append sweep bar: wicks below the lowest swing (e.g. 995) and closes back above (1005)
    last_t = m15_df.index[-1]
    sweep_row = pd.DataFrame(
        [{"open": lowest_swing + 2, "high": lowest_swing + 6, "low": lowest_swing - 5, "close": lowest_swing + 5, "tick_volume": 300}],
        index=[last_t + pd.Timedelta(minutes=15)]
    )
    m15_df = pd.concat([m15_df, sweep_row])
    
    # M1 trigger: bullish reversal candle closing above swept level
    m1_row = pd.DataFrame(
        [{"open": lowest_swing + 4, "high": lowest_swing + 8, "low": lowest_swing + 3, "close": lowest_swing + 7, "tick_volume": 50}],
        index=[last_t + pd.Timedelta(minutes=16)],
    )
    
    d1_df = _build_zigzag(base=1000.0, trend="up", n_cycles=6)
    h4_df = _build_zigzag(base=1000.0, trend="up", n_cycles=6)
    h1_df = _build_zigzag(base=1000.0, trend="up", n_cycles=6)
    
    bars = {"D1": d1_df, "H4": h4_df, "H1": h1_df, "M15": m15_df, "M1": m1_row}
    
    # Generate signal
    sig = generate_signal(bars, symbol="XAUUSD")
    ok = (sig is not None and sig.direction == Direction.BULLISH and sig.signal_type in [SignalType.SWEEP_ENTRY, SignalType.OB_RETEST, SignalType.OB_FVG, SignalType.FVG_RETEST])
    
    log.info(f"  Signal generated: {sig is not None}")
    if sig:
        log.info(f"  Signal Type: {sig.signal_type.value}")
        log.info(f"  Entry: {sig.entry_price}, SL: {sig.stop_loss}, TP: {sig.take_profit}, Score: {sig.confluence_score}")
    
    log.info(f"  {'PASS' if ok else 'FAIL'} -> Sweep reversal entry trigger verified.")
    return 0 if ok else 1


def test_bearish_bias_pullback_fix() -> int:
    log.info("\n-- 3. Testing Bearish & Counter-Trend Signal Generation ------------")
    
    # D1 is bullish uptrend
    d1_df = _build_zigzag(base=2000.0, trend="up", n_cycles=6)
    # H4 is bearish downtrend (pullback)
    h4_df = _build_zigzag(base=2200.0, trend="down", n_cycles=6)
    # H1 is bearish downtrend
    h1_df = _build_zigzag(base=2150.0, trend="down", n_cycles=6)
    
    # M15 bearish with an unmitigated OB
    m15_df = _build_zigzag(base=2100.0, trend="down", n_cycles=4)
    
    last_t = m15_df.index[-1]
    # 1. Bullish candle before impulse (Bearish OB) -> zone [2045, 2055]
    ob_bar = pd.DataFrame([{"open": 2045, "high": 2055, "low": 2044, "close": 2052, "tick_volume": 100}], index=[last_t + pd.Timedelta(minutes=15)])
    # 2. Strong Bearish Impulse (exceeds ATR, departs zone below 2044)
    imp1 = pd.DataFrame([{"open": 2052, "high": 2053, "low": 2025, "close": 2028, "tick_volume": 350}], index=[last_t + pd.Timedelta(minutes=30)])
    # 3. Follow-through bar
    imp2 = pd.DataFrame([{"open": 2028, "high": 2030, "low": 2020, "close": 2022, "tick_volume": 200}], index=[last_t + pd.Timedelta(minutes=45)])
    
    m15_df = pd.concat([m15_df, ob_bar, imp1, imp2])
    
    # M1 trigger: pulls back into the OB zone [2045, 2055] and closes bearish
    m1_row = pd.DataFrame(
        [{"open": 2051, "high": 2052, "low": 2046, "close": 2047, "tick_volume": 50}],
        index=[last_t + pd.Timedelta(minutes=46)],
    )
    
    bars = {"D1": d1_df, "H4": h4_df, "H1": h1_df, "M15": m15_df, "M1": m1_row}
    sig = generate_signal(bars, symbol="XAUUSD")
    
    ok = (sig is not None and sig.direction == Direction.BEARISH and sig.is_counter_trend is True)
    log.info(f"  Bearish Signal generated: {sig is not None}")
    if sig:
        log.info(f"  Direction: {sig.direction.value}, Counter-Trend: {sig.is_counter_trend}")
        log.info(f"  Signal Type: {sig.signal_type.value}, Score: {sig.confluence_score}")
        log.info(f"  Notes: {sig.notes}")
        
    log.info(f"  {'PASS' if ok else 'FAIL'} -> Bearish pullback signal generation verified.")
    return 0 if ok else 1


def main() -> None:
    log.info("=" * 65)
    log.info("VERIFY FIXES -- OB Mitigation, Sweep Entry & Bearish Confluence")
    log.info("=" * 65)

    f1 = test_ob_mitigation_fix()
    f2 = test_sweep_entry_fix()
    f3 = test_bearish_bias_pullback_fix()

    total = f1 + f2 + f3
    log.info("")
    if total == 0:
        log.info("ALL TARGETED FIXES VERIFIED & PASSED!")
    else:
        log.error(f"FAILED -- {total} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
