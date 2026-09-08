"""
signals/bias.py
───────────────
SMC market structure bias detection: HH/HL → Bullish, LH/LL → Bearish.

═══════════════════════════════════════════════════════════════════════════════
THEORY
═══════════════════════════════════════════════════════════════════════════════
Smart Money Concepts define bias by the sequence of swing points:

  Bullish:  … HL → HH → HL → HH …   (price is "stair-stepping" up)
  Bearish:  … LH → LL → LH → LL …   (price is "stair-stepping" down)
  Neutral:  Mixed — e.g. HH but LL, or not enough swings yet.

A swing HIGH is a bar whose high is greater than the N bars on each side.
A swing LOW  is a bar whose low  is less    than the N bars on each side.

We also detect:
  - Break of Structure (BOS): price closes beyond the last swing high/low,
    confirming the trend continues.
  - Change of Character (CHoCH): price breaks in the OPPOSITE direction,
    signalling a potential reversal.

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API
═══════════════════════════════════════════════════════════════════════════════

detect_swings(df, n_left, n_right) → (list[SwingPoint], list[SwingPoint])
    Returns (swing_highs, swing_lows) from a DataFrame of OHLCV bars.
    PURE — no side effects.

compute_bias(df, timeframe, n_left, n_right, min_swings) → BiasResult
    Full bias analysis on one timeframe's DataFrame.
    PURE — no side effects.

get_multi_tf_bias(bars_dict, timeframes, n_left, n_right) → dict[str, BiasResult]
    Convenience wrapper: compute bias for multiple timeframes at once.
    PURE — no side effects.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.types import Bias, BiasResult, SwingPoint, SwingType

log = get_logger(__name__)


# ── Constants / defaults ──────────────────────────────────────────────────────

DEFAULT_N_LEFT  = 3   # bars to left of pivot for confirmation
DEFAULT_N_RIGHT = 3   # bars to right of pivot for confirmation
DEFAULT_MIN_SWINGS = 2  # minimum swing highs AND lows needed to assign bias


# ── Swing detection ───────────────────────────────────────────────────────────

def detect_swings(
    df: pd.DataFrame,
    n_left: int = DEFAULT_N_LEFT,
    n_right: int = DEFAULT_N_RIGHT,
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """
    Detect confirmed swing highs and swing lows in a bar DataFrame.

    A bar at index i is a swing HIGH if:
        df['high'][i] > df['high'][i-j]  for j in 1..n_left
        df['high'][i] > df['high'][i+j]  for j in 1..n_right

    A bar at index i is a swing LOW if:
        df['low'][i]  < df['low'][i-j]   for j in 1..n_left
        df['low'][i]  < df['low'][i+j]   for j in 1..n_right

    Args:
        df:      DataFrame with at least 'high' and 'low' columns, UTC index.
        n_left:  Left-side confirmation bars.
        n_right: Right-side confirmation bars.

    Returns:
        (swing_highs, swing_lows) — lists of SwingPoint, chronological order.
    """
    if len(df) < n_left + n_right + 1:
        return [], []

    highs_arr = df["high"].to_numpy(dtype=float)
    lows_arr  = df["low"].to_numpy(dtype=float)
    timestamps = df.index

    swing_highs: list[SwingPoint] = []
    swing_lows:  list[SwingPoint] = []

    # Vectorised approach: build boolean masks for left and right conditions
    n = len(df)

    for i in range(n_left, n - n_right):
        h = highs_arr[i]
        l = lows_arr[i]

        # ── Swing high check ─────────────────────────────────────────────────
        is_sh = True
        for j in range(1, n_left + 1):
            if h <= highs_arr[i - j]:
                is_sh = False
                break
        if is_sh:
            for j in range(1, n_right + 1):
                if h <= highs_arr[i + j]:
                    is_sh = False
                    break

        if is_sh:
            swing_highs.append(SwingPoint(
                timestamp=timestamps[i],
                price=float(h),
                kind=SwingType.HIGH,
                bar_index=i,
            ))

        # ── Swing low check ──────────────────────────────────────────────────
        is_sl = True
        for j in range(1, n_left + 1):
            if l >= lows_arr[i - j]:
                is_sl = False
                break
        if is_sl:
            for j in range(1, n_right + 1):
                if l >= lows_arr[i + j]:
                    is_sl = False
                    break

        if is_sl:
            swing_lows.append(SwingPoint(
                timestamp=timestamps[i],
                price=float(l),
                kind=SwingType.LOW,
                bar_index=i,
            ))

    return swing_highs, swing_lows


# ── Bias computation ──────────────────────────────────────────────────────────

def compute_bias(
    df: pd.DataFrame,
    timeframe: str = "?",
    n_left: int = DEFAULT_N_LEFT,
    n_right: int = DEFAULT_N_RIGHT,
    min_swings: int = DEFAULT_MIN_SWINGS,
) -> BiasResult:
    """
    Analyse market structure and return a BiasResult for one timeframe.

    Logic:
      1. Detect all swing highs and swing lows.
      2. Look at the LAST 3 swing highs and LAST 3 swing lows.
      3. Score: +1 for HH, -1 for LH (across consecutive high pairs).
               +1 for HL, -1 for LL (across consecutive low pairs).
      4. Net positive score → BULLISH; negative → BEARISH; zero → NEUTRAL.

    Using the last 3 swings (2 comparisons each) gives a robust
    majority-vote rather than a single pair flip.

    Args:
        df:         DataFrame with 'open','high','low','close' columns.
        timeframe:  Label for logging, e.g. "H1".
        n_left:     Swing detection left bars.
        n_right:    Swing detection right bars.
        min_swings: Require at least this many swing highs AND lows.

    Returns:
        BiasResult (pure, no side-effects).
    """
    # ── Guard: enough bars? ──────────────────────────────────────────────────
    required = n_left + n_right + 1
    if len(df) < required:
        return BiasResult(
            bias=Bias.NEUTRAL,
            timeframe=timeframe,
            notes=f"Not enough bars ({len(df)} < {required})",
        )

    swing_highs, swing_lows = detect_swings(df, n_left, n_right)

    # ── Guard: enough swings? ────────────────────────────────────────────────
    if len(swing_highs) < min_swings or len(swing_lows) < min_swings:
        return BiasResult(
            bias=Bias.NEUTRAL,
            timeframe=timeframe,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            notes=(
                f"Insufficient swings: "
                f"SH={len(swing_highs)} SL={len(swing_lows)} "
                f"(need ≥{min_swings} each)"
            ),
        )

    # ── Score the last N swing pairs ─────────────────────────────────────────
    # We look at last 3 swings → 2 consecutive comparisons each
    LOOKBACK = 3
    recent_highs = swing_highs[-LOOKBACK:]
    recent_lows  = swing_lows[-LOOKBACK:]

    high_score = _score_swing_sequence([sp.price for sp in recent_highs])
    low_score  = _score_swing_sequence([sp.price for sp in recent_lows])

    net = high_score + low_score   # range: -4 to +4 with LOOKBACK=3

    # ── Determine bias ───────────────────────────────────────────────────────
    # Require net ≥ +1 or ≤ -1 to avoid flip on a single noisy pair
    if net > 0:
        bias = Bias.BULLISH
    elif net < 0:
        bias = Bias.BEARISH
    else:
        bias = Bias.NEUTRAL

    # ── Extract last HH/HL/LH/LL prices for downstream use ──────────────────
    last_hh = last_lh = last_hl = last_ll = None

    if len(recent_highs) >= 2:
        if recent_highs[-1].price > recent_highs[-2].price:
            last_hh = recent_highs[-1].price
        else:
            last_lh = recent_highs[-1].price

    if len(recent_lows) >= 2:
        if recent_lows[-1].price > recent_lows[-2].price:
            last_hl = recent_lows[-1].price
        else:
            last_ll = recent_lows[-1].price

    # ── Human-readable explanation ───────────────────────────────────────────
    high_tags = _label_sequence([sp.price for sp in recent_highs], "HH", "LH")
    low_tags  = _label_sequence([sp.price for sp in recent_lows],  "HL", "LL")
    notes = (
        f"Highs: {high_tags} (score={high_score:+d})  |  "
        f"Lows: {low_tags}  (score={low_score:+d})  |  "
        f"net={net:+d}"
    )

    return BiasResult(
        bias=bias,
        timeframe=timeframe,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        last_hh=last_hh,
        last_hl=last_hl,
        last_lh=last_lh,
        last_ll=last_ll,
        notes=notes,
    )


_BIAS_CACHE: dict[tuple, BiasResult] = {}

def get_multi_tf_bias(
    bars_dict: dict[str, pd.DataFrame],
    timeframes: Optional[list[str]] = None,
    n_left: int = DEFAULT_N_LEFT,
    n_right: int = DEFAULT_N_RIGHT,
    min_swings: int = DEFAULT_MIN_SWINGS,
) -> dict[str, BiasResult]:
    """
    Compute bias for each timeframe in bars_dict (cached by timeframe & last bar timestamp).
    """
    tfs = timeframes or list(bars_dict.keys())
    results: dict[str, BiasResult] = {}

    for tf in tfs:
        df = bars_dict.get(tf, pd.DataFrame())
        if df.empty:
            results[tf] = BiasResult(
                bias=Bias.NEUTRAL,
                timeframe=tf,
                notes="Empty DataFrame",
            )
            continue
        
        last_ts = df.index[-1]
        cache_key = (tf, last_ts, len(df), n_left, n_right)
        if cache_key in _BIAS_CACHE:
            results[tf] = _BIAS_CACHE[cache_key]
        else:
            res = compute_bias(df, timeframe=tf, n_left=n_left, n_right=n_right, min_swings=min_swings)
            if len(_BIAS_CACHE) > 5000:
                _BIAS_CACHE.clear()
            _BIAS_CACHE[cache_key] = res
            results[tf] = res

    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _score_swing_sequence(prices: list[float]) -> int:
    """
    Score a sequence of swing prices.
    Each consecutive pair: +1 if rising (HH or HL), -1 if falling (LH or LL).
    Returns net score across all pairs.
    """
    score = 0
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            score += 1
        elif prices[i] < prices[i - 1]:
            score -= 1
        # equal → 0
    return score


def _label_sequence(prices: list[float], up_tag: str, down_tag: str) -> str:
    """Build a human-readable string like 'HL → HL' from a price sequence."""
    if len(prices) < 2:
        return "(insufficient)"
    tags = []
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            tags.append(up_tag)
        elif prices[i] < prices[i - 1]:
            tags.append(down_tag)
        else:
            tags.append("=")
    return " → ".join(tags)
