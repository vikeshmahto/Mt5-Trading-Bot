"""
signals/fvg.py
──────────────
Detect Fair Value Gaps (FVGs / Imbalances) in a bar DataFrame.

═══════════════════════════════════════════════════════════════════════════════
SMC THEORY
═══════════════════════════════════════════════════════════════════════════════
A Fair Value Gap is a 3-candle pattern where price moves so fast that a gap
(imbalance) forms between bar 1 and bar 3, meaning bar 2 didn't trade through
that price range at all.

  Bullish FVG (demand imbalance — gap above):
    bar[i].high   <   bar[i+2].low
    The zone: bottom = bar[i].high, top = bar[i+2].low

  Bearish FVG (supply imbalance — gap below):
    bar[i].low    >   bar[i+2].high
    The zone: bottom = bar[i+2].high, top = bar[i].low

  Retest:
    Price re-enters the gap zone → potential bounce/rejection.
    • Partial fill: price enters the zone but doesn't close through.
    • Full fill:    price closes completely through the gap → FVG invalidated.

  Minimum size filter:
    We skip tiny FVGs (< min_size_atr_mult × ATR) that are just spread noise.

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API  (all PURE — no I/O, no state)
═══════════════════════════════════════════════════════════════════════════════

detect_fvgs(df, timeframe, min_size_atr_mult) → list[FairValueGap]

check_fvg_retests(fvgs, df) → list[FairValueGap]
    Scan subsequent bars and update .retested / .filled fields in-place.

get_fresh_fvgs(fvgs, direction, n_recent) → list[FairValueGap]
    Return unfilled FVGs newest-first.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.types import Direction, FairValueGap
from signals.liquidity_sweep import _rolling_atr

log = get_logger(__name__)

DEFAULT_MIN_SIZE_ATR_MULT = 0.1   # FVG must be ≥ 10% of ATR to be meaningful


def detect_fvgs(
    df: pd.DataFrame,
    timeframe: str = "",
    min_size_atr_mult: float = DEFAULT_MIN_SIZE_ATR_MULT,
    check_retests: bool = True,
) -> list[FairValueGap]:
    """
    Scan a bar DataFrame for Fair Value Gaps.

    Args:
        df:                 OHLCV DataFrame, UTC DatetimeIndex.
        timeframe:          Label for FairValueGap objects.
        min_size_atr_mult:  Minimum gap size as a multiple of ATR.
                            Filters out noise from tiny imbalances.
        check_retests:      If True, scan bars after each FVG to update
                            .retested / .filled / .partially_filled flags.

    Returns:
        List of FairValueGap objects in chronological order (by middle bar ts).
    """
    if len(df) < 3:
        return []

    highs  = df["high"].to_numpy(dtype=float)
    lows   = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    ts     = df.index
    atr    = _rolling_atr(df, period=14)

    fvgs: list[FairValueGap] = []

    # We need at least 3 bars: i, i+1, i+2
    for i in range(len(df) - 2):
        bar_atr   = atr[i + 1] if atr[i + 1] > 0 else 1.0
        min_size  = min_size_atr_mult * bar_atr

        # ── Bullish FVG ───────────────────────────────────────────────────────
        # Gap between bar[i] top and bar[i+2] bottom
        gap_bottom = highs[i]
        gap_top    = lows[i + 2]
        if gap_top > gap_bottom and (gap_top - gap_bottom) >= min_size:
            fvgs.append(FairValueGap(
                direction=Direction.BULLISH,
                timestamp=ts[i + 1],       # middle bar
                top=float(gap_top),
                bottom=float(gap_bottom),
                timeframe=timeframe,
            ))

        # ── Bearish FVG ───────────────────────────────────────────────────────
        # Gap between bar[i+2] top and bar[i] bottom
        gap_bottom = highs[i + 2]
        gap_top    = lows[i]
        if gap_top > gap_bottom and (gap_top - gap_bottom) >= min_size:
            fvgs.append(FairValueGap(
                direction=Direction.BEARISH,
                timestamp=ts[i + 1],
                top=float(gap_top),
                bottom=float(gap_bottom),
                timeframe=timeframe,
            ))

    if check_retests:
        fvgs = _check_fvg_retests(fvgs, df)

    log.debug(
        f"[{timeframe}] FVGs detected: {len(fvgs)} "
        f"({sum(1 for f in fvgs if f.direction == Direction.BULLISH)} bull / "
        f"{sum(1 for f in fvgs if f.direction == Direction.BEARISH)} bear) | "
        f"filled={sum(1 for f in fvgs if f.filled)} "
        f"retested={sum(1 for f in fvgs if f.retested)}"
    )
    return fvgs


def get_fresh_fvgs(
    fvgs: list[FairValueGap],
    direction: Optional[Direction] = None,
    n_recent: int = 10,
    exclude_filled: bool = True,
) -> list[FairValueGap]:
    """
    Return recent, unfilled FVGs (newest first), optionally by direction.

    Args:
        fvgs:           Full list from detect_fvgs().
        direction:      Filter by BULLISH/BEARISH, or None for both.
        n_recent:       Maximum results.
        exclude_filled: If True (default), skip fully-filled FVGs.
    """
    filtered = [
        fvg for fvg in fvgs
        if (not exclude_filled or not fvg.filled)
        and (direction is None or fvg.direction == direction)
    ]
    return filtered[-n_recent:]


def is_price_in_fvg(fvg: FairValueGap, price: float) -> bool:
    """Quick helper: True if price is inside the FVG zone."""
    return fvg.bottom <= price <= fvg.top


# ── Internal helpers ──────────────────────────────────────────────────────────

def _check_fvg_retests(
    fvgs: list[FairValueGap],
    df: pd.DataFrame,
) -> list[FairValueGap]:
    """
    For each FVG, scan the bars AFTER its formation to detect:
      - First retest (price enters the zone)
      - Partial fill (price enters but doesn't close through)
      - Full fill    (price closes beyond the far edge of the gap)
    """
    highs  = df["high"].to_numpy(dtype=float)
    lows   = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    ts     = df.index

    ts_to_idx = {t: i for i, t in enumerate(ts)}

    for fvg in fvgs:
        mid_idx = ts_to_idx.get(fvg.timestamp)
        if mid_idx is None:
            continue
        # Scan starts from bar AFTER the middle bar (i+2 in the 3-bar pattern)
        scan_start = mid_idx + 2

        for i in range(scan_start, len(df)):
            h = highs[i]
            l = lows[i]
            c = closes[i]

            if fvg.direction == Direction.BULLISH:
                # Price enters from below (retesting the bullish FVG)
                if l <= fvg.top and h >= fvg.bottom:
                    if not fvg.retested:
                        fvg.retested    = True
                        fvg.retested_at = ts[i]
                    fvg.partially_filled = True
                    # Full fill: close below the bottom of the FVG
                    if c < fvg.bottom:
                        fvg.filled = True
                        break

            else:  # BEARISH FVG
                # Price enters from above (retesting the bearish FVG)
                if h >= fvg.bottom and l <= fvg.top:
                    if not fvg.retested:
                        fvg.retested    = True
                        fvg.retested_at = ts[i]
                    fvg.partially_filled = True
                    # Full fill: close above the top of the FVG
                    if c > fvg.top:
                        fvg.filled = True
                        break

    return fvgs
