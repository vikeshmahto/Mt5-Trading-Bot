"""
scripts/verify_step4.py
───────────────────────
Step 4 smoke-test: bias detection on real MT5 data + synthetic unit tests.

Tests:
  A. Synthetic data tests (no MT5 needed):
       1. Perfect bullish staircase   → BULLISH
       2. Perfect bearish staircase   → BEARISH
       3. Flat / choppy data          → NEUTRAL
       4. Not enough bars             → NEUTRAL
       5. Mixed structure (3HH + 1LL) → leans BULLISH

  B. Live data from MT5:
       - Compute bias for D1, H4, H1
       - Print swing points + reason
       - Verify output types are correct

Run:
    python scripts/verify_step4.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import Bias, BiasResult
from signals.bias import compute_bias, detect_swings, get_multi_tf_bias
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi

log = get_logger(__name__, level=settings.log_level)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data builders
# ─────────────────────────────────────────────────────────────────────────────

def _make_df(opens, highs, lows, closes) -> pd.DataFrame:
    """Build a minimal OHLC DataFrame from lists."""
    n = len(opens)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes},
        index=idx,
    )


def _build_bullish_staircase(n_cycles: int = 8) -> pd.DataFrame:
    """
    Synthetic HH/HL zigzag uptrend.
    Alternates: swing low (SL) → swing high (SH) → higher SL → higher SH …
    5 flat padding bars are added around each pivot to satisfy n_left/n_right.
    """
    # Anchor prices for each pivot, each cycle 20 pts higher
    # Cycle: (low_price, high_price)
    pivots_raw = [(1000 + c * 15, 1020 + c * 15) for c in range(n_cycles)]

    opens, highs, lows, closes = [], [], [], []
    PAD = 4   # flat bars around each pivot (must be ≥ n_left/n_right used in test)

    prev_mid = pivots_raw[0][0]

    for i, (lo, hi) in enumerate(pivots_raw):
        # ── Swing LOW bar ────────────────────────────────────────────────
        mid = (lo + hi) / 2
        # Pad before SL (bars slightly above the low)
        for _ in range(PAD):
            p = lo + 2
            opens.append(p); highs.append(p + 1); lows.append(p - 0.3); closes.append(p)
        # The swing low itself
        opens.append(lo + 0.5); highs.append(lo + 1.5); lows.append(lo); closes.append(lo + 1)
        # Pad after SL
        for _ in range(PAD):
            p = lo + 2
            opens.append(p); highs.append(p + 1); lows.append(p - 0.3); closes.append(p)

        # ── Swing HIGH bar ───────────────────────────────────────────────
        for _ in range(PAD):
            p = hi - 2
            opens.append(p); highs.append(p + 0.3); lows.append(p - 1); closes.append(p)
        # The swing high itself
        opens.append(hi - 0.5); highs.append(hi); lows.append(hi - 1.5); closes.append(hi - 1)
        # Pad after SH
        for _ in range(PAD):
            p = hi - 2
            opens.append(p); highs.append(p + 0.3); lows.append(p - 1); closes.append(p)

    return _make_df(opens, highs, lows, closes)


def _build_bearish_staircase(n_cycles: int = 8) -> pd.DataFrame:
    """
    Synthetic LH/LL zigzag downtrend.
    Alternates: swing high → swing low → lower swing high → lower swing low …
    """
    pivots_raw = [(2000 - c * 15, 2020 - c * 15) for c in range(n_cycles)]

    opens, highs, lows, closes = [], [], [], []
    PAD = 4

    for i, (lo, hi) in enumerate(pivots_raw):
        # ── Swing HIGH bar ───────────────────────────────────────────────
        for _ in range(PAD):
            p = hi - 2
            opens.append(p); highs.append(p + 0.3); lows.append(p - 1); closes.append(p)
        opens.append(hi - 0.5); highs.append(hi); lows.append(hi - 1.5); closes.append(hi - 1)
        for _ in range(PAD):
            p = hi - 2
            opens.append(p); highs.append(p + 0.3); lows.append(p - 1); closes.append(p)

        # ── Swing LOW bar ────────────────────────────────────────────────
        for _ in range(PAD):
            p = lo + 2
            opens.append(p); highs.append(p + 1); lows.append(p - 0.3); closes.append(p)
        opens.append(lo + 0.5); highs.append(lo + 1.5); lows.append(lo); closes.append(lo + 1)
        for _ in range(PAD):
            p = lo + 2
            opens.append(p); highs.append(p + 1); lows.append(p - 0.3); closes.append(p)

    return _make_df(opens, highs, lows, closes)


def _build_choppy(n_bars: int = 60) -> pd.DataFrame:
    """Flat oscillating price — should produce NEUTRAL."""
    np.random.seed(42)
    prices = 1500 + np.sin(np.linspace(0, 8 * np.pi, n_bars)) * 5
    noise  = np.random.uniform(-0.5, 0.5, n_bars)
    prices = prices + noise
    opens  = prices.copy()
    closes = prices + np.random.uniform(-1, 1, n_bars)
    highs  = np.maximum(opens, closes) + np.random.uniform(0.2, 1.0, n_bars)
    lows   = np.minimum(opens, closes) - np.random.uniform(0.2, 1.0, n_bars)
    return _make_df(list(opens), list(highs), list(lows), list(closes))


# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

def run_synthetic_tests() -> int:
    """Returns number of failures."""
    failures = 0

    cases = [
        ("Perfect bullish staircase", _build_bullish_staircase(),  Bias.BULLISH),
        ("Perfect bearish staircase", _build_bearish_staircase(),  Bias.BEARISH),
        ("Choppy / neutral data",     _build_choppy(),             Bias.NEUTRAL),
        ("Too few bars (4 bars)",     _make_df(
            [1,2,3,4],[1.5,2.5,3.5,4.5],[0.5,1.5,2.5,3.5],[1,2,3,4]
         ),                                                         Bias.NEUTRAL),
    ]

    log.info("── Synthetic unit tests ─────────────────────────────────────")
    for name, df, expected_bias in cases:
        result = compute_bias(df, timeframe="TEST", n_left=3, n_right=2)
        ok = result.bias == expected_bias
        marker = "✓" if ok else "✗"
        log.info(
            f"  {marker} [{name}]  "
            f"got={result.bias.value:8s}  expected={expected_bias.value:8s}"
        )
        log.info(f"      notes: {result.notes}")
        if not ok:
            failures += 1

    return failures


def run_live_tests() -> int:
    """Returns number of failures (type/shape errors)."""
    failures = 0
    SYMBOL = "XAUUSD"
    BIAS_TFS = ["D1", "H4", "H1"]

    log.info("\n── Live MT5 data bias test ──────────────────────────────────")

    with MT5Client():
        bars = fetch_multi(
            symbol=SYMBOL,
            timeframes=BIAS_TFS,
            n_bars_per_tf={"D1": 365, "H4": 500, "H1": 500},
            include_open=False,
        )

    bias_results = get_multi_tf_bias(bars, timeframes=BIAS_TFS)

    log.info(f"\nBias for {SYMBOL}:")
    for tf, result in bias_results.items():
        log.info(f"  {result}")
        log.info(f"    swing highs : {len(result.swing_highs)} detected")
        log.info(f"    swing lows  : {len(result.swing_lows)} detected")
        if result.swing_highs:
            last_sh = result.swing_highs[-1]
            log.info(f"    last SH     : {last_sh.timestamp.date()}  @ {last_sh.price:.2f}")
        if result.swing_lows:
            last_sl = result.swing_lows[-1]
            log.info(f"    last SL     : {last_sl.timestamp.date()}  @ {last_sl.price:.2f}")
        log.info(f"    last HH={result.last_hh}  HL={result.last_hl}  "
                 f"LH={result.last_lh}  LL={result.last_ll}")

        # ── Type checks ──────────────────────────────────────────────────────
        if not isinstance(result, BiasResult):
            log.error(f"  {tf}: result is not BiasResult!")
            failures += 1
        if not isinstance(result.bias, Bias):
            log.error(f"  {tf}: bias is not Bias enum!")
            failures += 1

    # ── Three-TF confluence example ──────────────────────────────────────────
    log.info("\n── 3-TF confluence summary ──────────────────────────────────")
    d1_bias  = bias_results["D1"].bias
    h4_bias  = bias_results["H4"].bias
    h1_bias  = bias_results["H1"].bias

    bullish_count = sum(b == Bias.BULLISH for b in [d1_bias, h4_bias, h1_bias])
    bearish_count = sum(b == Bias.BEARISH for b in [d1_bias, h4_bias, h1_bias])

    log.info(f"  D1={d1_bias.value}  H4={h4_bias.value}  H1={h1_bias.value}")
    if bullish_count >= 2:
        log.info(f"  → {bullish_count}/3 bullish — looking for LONG setups")
    elif bearish_count >= 2:
        log.info(f"  → {bearish_count}/3 bearish — looking for SHORT setups")
    else:
        log.info(f"  → Mixed / no clear bias — staying flat")

    return failures


def main() -> None:
    log.info("=" * 65)
    log.info("STEP 4 — Bias Detection (Synthetic + Live)")
    log.info("=" * 65)

    synth_failures = run_synthetic_tests()
    live_failures  = run_live_tests()
    total = synth_failures + live_failures

    log.info("")
    if total == 0:
        log.info("✅  Step 4 PASSED — bias detection working correctly.")
    else:
        log.error(f"❌  Step 4 FAILED — {total} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
