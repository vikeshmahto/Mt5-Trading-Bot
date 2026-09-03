"""
scripts/verify_step5.py
───────────────────────
Step 5 smoke-test: sweeps, order blocks, FVGs — synthetic + live data.

Synthetic tests:
  Sweep:  craft a bar that wicks through a known swing low/high and closes back
  OB:     craft a sequence with an impulse candle preceded by an opposing candle
  FVG:    craft 3 candles with a known gap, verify detection and retest

Live tests:
  Run all three detectors on M15 XAUUSD data and print summaries.

Run:
    python scripts/verify_step5.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import Direction
from signals.liquidity_sweep import detect_liquidity_sweeps
from signals.order_blocks import detect_order_blocks, get_unmitigated_obs
from signals.fvg import detect_fvgs, get_fresh_fvgs
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi

log = get_logger(__name__, level=settings.log_level)


# ─────────────────────────────────────────────────────────────────────────────
# Tiny helper
# ─────────────────────────────────────────────────────────────────────────────

def _df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of dicts."""
    idx = pd.date_range("2024-01-01 00:00", periods=len(rows), freq="h", tz="UTC")
    df  = pd.DataFrame(rows, index=idx)
    df.index.name = "timestamp"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic tests
# ─────────────────────────────────────────────────────────────────────────────

def test_sweep_detection() -> int:
    """
    Build a sequence that has:
      - A clear swing low at bar 5 (price = 100).
      - Bar 15 wicks below 100 but closes back above → bullish sweep.
      - A swing high at bar 20 (price = 120).
      - Bar 25 wicks above 120 but closes back below → bearish sweep.
    """
    rows = []
    # Bars 0-4: setup
    for i in range(5):
        rows.append({"open":105, "high":108, "low":103, "close":106, "tick_volume":100})
    # Bar 5: swing low at 100
    rows.append({"open":105, "high":106, "low":100, "close":104, "tick_volume":100})
    # Bars 6-14: recovery up
    for i in range(9):
        rows.append({"open":104+i, "high":106+i, "low":103+i, "close":105+i, "tick_volume":100})
    # Bar 15: bullish sweep — wicks to 98, closes at 106 (above 100 swing low)
    rows.append({"open":103, "high":107, "low":98, "close":106, "tick_volume":200})
    # Bars 16-19: push up
    for i in range(4):
        rows.append({"open":106+i, "high":122+i, "low":105+i, "close":120+i, "tick_volume":100})
    # Bar 20: swing high at 130
    rows.append({"open":121, "high":130, "low":119, "close":122, "tick_volume":100})
    # Bars 21-24: pullback
    for i in range(4):
        rows.append({"open":122-i, "high":124-i, "low":120-i, "close":121-i, "tick_volume":100})
    # Bar 25: bearish sweep — wicks to 133, closes at 119 (below 130 swing high)
    rows.append({"open":122, "high":133, "low":117, "close":119, "tick_volume":200})
    # Bars 26-30: tail
    for i in range(5):
        rows.append({"open":119, "high":121, "low":118, "close":120, "tick_volume":100})

    df = _df(rows)
    sweeps = detect_liquidity_sweeps(df, timeframe="TEST", swing_n_left=3, swing_n_right=2)

    bull_sweeps = [s for s in sweeps if s.direction == Direction.BULLISH]
    bear_sweeps = [s for s in sweeps if s.direction == Direction.BEARISH]

    ok = len(bull_sweeps) >= 1 and len(bear_sweeps) >= 1
    marker = "✓" if ok else "✗"
    log.info(f"  {marker} [Sweep] bull={len(bull_sweeps)} bear={len(bear_sweeps)}"
             f" (expected ≥1 each)")
    if bull_sweeps:
        log.info(f"      BullSweep: swept_level={bull_sweeps[-1].swept_level:.1f}"
                 f"  close={bull_sweeps[-1].close:.1f}")
    if bear_sweeps:
        log.info(f"      BearSweep: swept_level={bear_sweeps[-1].swept_level:.1f}"
                 f"  close={bear_sweeps[-1].close:.1f}")
    return 0 if ok else 1


def test_ob_detection() -> int:
    """
    Construct a sequence:
      - 3 flat bars
      - 1 bearish candle (future bullish OB)
      - 3 strong bullish impulse bars (body > ATR threshold)
      - Result: bullish OB should be detected at the bearish candle's position
    """
    rows = []
    # Flat context (needed for ATR to stabilise)
    for _ in range(20):
        rows.append({"open":100, "high":101, "low":99, "close":100, "tick_volume":50})
    # Last bearish candle before the impulse
    rows.append({"open":101, "high":102, "low":98, "close":99, "tick_volume":80})
    # Strong bullish impulse (body ~10 pts >> ATR ~2 pts)
    rows.append({"open":99, "high":112, "low":98, "close":110, "tick_volume":300})
    rows.append({"open":110, "high":115, "low":109, "close":114, "tick_volume":200})
    # Tail
    for _ in range(5):
        rows.append({"open":114, "high":115, "low":113, "close":114, "tick_volume":50})

    df  = _df(rows)
    obs = detect_order_blocks(df, timeframe="TEST", impulse_atr_mult=1.5)

    bull_obs = [o for o in obs if o.direction == Direction.BULLISH]
    ok = len(bull_obs) >= 1
    marker = "✓" if ok else "✗"
    log.info(f"  {marker} [OB]    bull_obs={len(bull_obs)} (expected ≥1)")
    if bull_obs:
        ob = bull_obs[-1]
        log.info(f"      BullOB: zone=[{ob.low:.1f}–{ob.high:.1f}]"
                 f"  impulse={ob.impulse_size:.1f}"
                 f"  mitigated={ob.mitigated}")
    return 0 if ok else 1


def test_fvg_detection() -> int:
    """
    Craft an explicit bullish FVG:
      bar[i].high=100, bar[i+2].low=105  → gap 100–105
    And a bearish FVG:
      bar[i].low=200,  bar[i+2].high=195 → gap 195–200
    Also test retest detection.
    """
    # ── Bullish FVG ──────────────────────────────────────────────────────────
    rows = []
    for _ in range(5):
        rows.append({"open":95, "high":100, "low":94, "close":97, "tick_volume":50})
    # Bar i  : high=100
    rows.append({"open":97, "high":100, "low":96, "close":98, "tick_volume":60})
    # Bar i+1 (middle)
    rows.append({"open":102, "high":104, "low":101, "close":103, "tick_volume":80})
    # Bar i+2: low=105 → gap is [100, 105]
    rows.append({"open":105, "high":108, "low":105, "close":107, "tick_volume":70})
    # Some bars after (no retest yet)
    for _ in range(3):
        rows.append({"open":107, "high":109, "low":106, "close":108, "tick_volume":50})
    # Retest bar: enters the 100–105 zone from above
    rows.append({"open":106, "high":107, "low":102, "close":104, "tick_volume":90})
    # Recovery
    for _ in range(3):
        rows.append({"open":104, "high":108, "low":103, "close":107, "tick_volume":50})

    df   = _df(rows)
    fvgs = detect_fvgs(df, timeframe="TEST", min_size_atr_mult=0.0)  # no min filter

    bull_fvgs = [f for f in fvgs if f.direction == Direction.BULLISH]
    ok_detect = len(bull_fvgs) >= 1
    ok_retest = any(f.retested for f in bull_fvgs)

    ok = ok_detect and ok_retest
    marker = "✓" if ok else "✗"
    log.info(f"  {marker} [FVG]   bull_fvgs={len(bull_fvgs)}"
             f"  retested={sum(1 for f in bull_fvgs if f.retested)}"
             f" (expected ≥1 detected, ≥1 retested)")
    if bull_fvgs:
        fvg = [f for f in bull_fvgs if f.bottom >= 99][0] if any(f.bottom >= 99 for f in bull_fvgs) else bull_fvgs[-1]
        log.info(f"      BullFVG: zone=[{fvg.bottom:.1f}–{fvg.top:.1f}]"
                 f"  size={fvg.size:.1f}"
                 f"  retested={fvg.retested}"
                 f"  filled={fvg.filled}")
    return 0 if ok else 1


# ─────────────────────────────────────────────────────────────────────────────
# Live MT5 tests
# ─────────────────────────────────────────────────────────────────────────────

def run_live_tests() -> int:
    failures = 0
    SYMBOL   = "XAUUSD"
    TFS      = ["H1", "M15"]

    log.info("\n── Live MT5 data (XAUUSD) ───────────────────────────────────")

    with MT5Client():
        bars = fetch_multi(SYMBOL, TFS, n_bars_per_tf=500, include_open=False)

    for tf in TFS:
        df = bars[tf]
        if df.empty:
            log.error(f"  {tf}: empty DataFrame!")
            failures += 1
            continue

        # Sweeps
        sweeps = detect_liquidity_sweeps(df, timeframe=tf)
        bull_sw = [s for s in sweeps if s.direction == Direction.BULLISH]
        bear_sw = [s for s in sweeps if s.direction == Direction.BEARISH]

        # OBs
        obs      = detect_order_blocks(df, timeframe=tf)
        fresh_bull_obs = get_unmitigated_obs(obs, Direction.BULLISH, n_recent=3)
        fresh_bear_obs = get_unmitigated_obs(obs, Direction.BEARISH, n_recent=3)

        # FVGs
        fvgs          = detect_fvgs(df, timeframe=tf)
        fresh_bull_fvg = get_fresh_fvgs(fvgs, Direction.BULLISH, n_recent=3)
        fresh_bear_fvg = get_fresh_fvgs(fvgs, Direction.BEARISH, n_recent=3)

        log.info(f"\n[{tf}] ({len(df)} bars)")
        log.info(f"  Sweeps  : {len(bull_sw)} bull / {len(bear_sw)} bear")
        if sweeps:
            last = sweeps[-1]
            log.info(f"    Latest: {last}")

        log.info(f"  OBs     : {len(obs)} total | "
                 f"{len(fresh_bull_obs)} fresh-bull / {len(fresh_bear_obs)} fresh-bear")
        for ob in fresh_bull_obs[-2:]:
            log.info(f"    {ob}")
        for ob in fresh_bear_obs[-2:]:
            log.info(f"    {ob}")

        log.info(f"  FVGs    : {len(fvgs)} total | "
                 f"filled={sum(1 for f in fvgs if f.filled)} | "
                 f"retested={sum(1 for f in fvgs if f.retested)}")
        log.info(f"    Fresh bull FVGs: {len(fresh_bull_fvg)}")
        for fvg in fresh_bull_fvg[-2:]:
            log.info(f"      {fvg}")
        log.info(f"    Fresh bear FVGs: {len(fresh_bear_fvg)}")
        for fvg in fresh_bear_fvg[-2:]:
            log.info(f"      {fvg}")

        if len(sweeps) == 0 and len(obs) == 0 and len(fvgs) == 0:
            log.warning(f"  {tf}: zero detections on all three — check thresholds")
            failures += 1

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 65)
    log.info("STEP 5 — Sweeps / Order Blocks / FVGs (Synthetic + Live)")
    log.info("=" * 65)

    log.info("\n── Synthetic unit tests ─────────────────────────────────────")
    f1 = test_sweep_detection()
    f2 = test_ob_detection()
    f3 = test_fvg_detection()
    synth_fails = f1 + f2 + f3

    live_fails = run_live_tests()
    total = synth_fails + live_fails

    log.info("")
    if total == 0:
        log.info("✅  Step 5 PASSED — all three detectors working.")
    else:
        log.error(f"❌  Step 5 FAILED — {total} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
