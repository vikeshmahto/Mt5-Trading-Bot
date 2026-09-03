"""
signals/liquidity_sweep.py
──────────────────────────
Detect liquidity sweep events in a bar DataFrame.

═══════════════════════════════════════════════════════════════════════════════
SMC THEORY
═══════════════════════════════════════════════════════════════════════════════
Liquidity pools sit above swing highs (buy stops) and below swing lows
(sell stops).  Smart money engineers a "sweep" to grab this liquidity before
reversing:

  Bullish sweep (sell-side liquidity grab):
    • Bar's LOW wicks BELOW a recent swing low.
    • Bar CLOSES back ABOVE that swing low.
    • Interpretation: sell stops triggered → smart money absorbed supply →
      price likely to move higher.

  Bearish sweep (buy-side liquidity grab):
    • Bar's HIGH wicks ABOVE a recent swing high.
    • Bar CLOSES back BELOW that swing high.
    • Interpretation: buy stops triggered → smart money distributed →
      price likely to move lower.

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API  (all PURE — no I/O, no state)
═══════════════════════════════════════════════════════════════════════════════

detect_liquidity_sweeps(df, timeframe, swing_lookback, level_lookback)
    → list[LiquiditySweep]

    Full pipeline: detect swings internally, then scan every bar for sweeps.

is_sweep_bar(bar, swing_levels, direction)
    → Optional[LiquiditySweep]

    Check a single bar against a list of price levels (low-level helper).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.types import Direction, LiquiditySweep, SwingType
from signals.bias import detect_swings, DEFAULT_N_LEFT, DEFAULT_N_RIGHT

log = get_logger(__name__)


def detect_liquidity_sweeps(
    df: pd.DataFrame,
    timeframe: str = "",
    swing_n_left: int = DEFAULT_N_LEFT,
    swing_n_right: int = DEFAULT_N_RIGHT,
    level_lookback: int = 30,
    min_wick_ratio: float = 0.1,
) -> list[LiquiditySweep]:
    """
    Scan a bar DataFrame for liquidity sweep events.

    Args:
        df:              OHLCV DataFrame with UTC DatetimeIndex.
        timeframe:       Label for the LiquiditySweep objects, e.g. "M15".
        swing_n_left:    Left bars for swing detection.
        swing_n_right:   Right bars for swing detection.
        level_lookback:  Max number of past SWING POINTS to consider as
                         active liquidity levels. Older swings are dropped.
        min_wick_ratio:  Min (wick beyond level / ATR) ratio required.
                         Filters out micro-wicks that aren't real sweeps.

    Returns:
        List of LiquiditySweep events, chronological order.
    """
    if len(df) < swing_n_left + swing_n_right + 2:
        return []

    swing_highs, swing_lows = detect_swings(df, swing_n_left, swing_n_right)

    highs_arr  = df["high"].to_numpy(dtype=float)
    lows_arr   = df["low"].to_numpy(dtype=float)
    closes_arr = df["close"].to_numpy(dtype=float)
    opens_arr  = df["open"].to_numpy(dtype=float)
    timestamps = df.index

    # Rolling ATR (14-period) for wick-ratio filter
    atr = _rolling_atr(df, period=14)

    sweeps: list[LiquiditySweep] = []

    for i in range(swing_n_left + swing_n_right + 1, len(df)):
        current_ts = timestamps[i]
        bar_atr    = atr[i] if atr[i] > 0 else 1.0

        # ── Collect active swing levels up to bar i ─────────────────────────
        # Only use swings confirmed BEFORE bar i (their bar_index < i)
        active_lows  = [sp for sp in swing_lows  if sp.bar_index < i][-level_lookback:]
        active_highs = [sp for sp in swing_highs if sp.bar_index < i][-level_lookback:]

        h  = highs_arr[i]
        l  = lows_arr[i]
        c  = closes_arr[i]
        o  = opens_arr[i]
        body = abs(c - o)

        # ── Bullish sweep: wick below swing low, close back above ────────────
        for sp in reversed(active_lows):   # newest first — take the closest one
            level = sp.price
            if l < level and c > level:
                wick_size = level - l
                if wick_size / bar_atr >= min_wick_ratio:
                    disp = body / bar_atr
                    sweeps.append(LiquiditySweep(
                        direction=Direction.BULLISH,
                        timestamp=current_ts,
                        swept_level=level,
                        sweep_low=float(l),
                        sweep_high=float(h),
                        close=float(c),
                        displacement=round(disp, 3),
                        timeframe=timeframe,
                    ))
                    break   # one sweep per bar (most significant level)

        # ── Bearish sweep: wick above swing high, close back below ───────────
        for sp in reversed(active_highs):
            level = sp.price
            if h > level and c < level:
                wick_size = h - level
                if wick_size / bar_atr >= min_wick_ratio:
                    disp = body / bar_atr
                    sweeps.append(LiquiditySweep(
                        direction=Direction.BEARISH,
                        timestamp=current_ts,
                        swept_level=level,
                        sweep_low=float(l),
                        sweep_high=float(h),
                        close=float(c),
                        displacement=round(disp, 3),
                        timeframe=timeframe,
                    ))
                    break

    return sweeps


def get_recent_sweeps(
    sweeps: list[LiquiditySweep],
    n: int = 5,
    direction: Optional[Direction] = None,
) -> list[LiquiditySweep]:
    """Return the most recent N sweeps, optionally filtered by direction."""
    filtered = [s for s in sweeps if direction is None or s.direction == direction]
    return filtered[-n:]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _rolling_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Compute a simple rolling ATR (True Range mean) array."""
    high  = df["high"].to_numpy(dtype=float)
    low   = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n     = len(df)
    atr   = np.zeros(n)

    prev_close = close[0]
    for i in range(1, n):
        tr = max(
            high[i] - low[i],
            abs(high[i] - prev_close),
            abs(low[i]  - prev_close),
        )
        start = max(0, i - period)
        # Approximate: mean of last `period` TR values is expensive to keep
        # Use exponential approximation instead
        if i < period:
            atr[i] = tr
        else:
            atr[i] = atr[i - 1] * (period - 1) / period + tr / period
        prev_close = close[i]

    return atr
