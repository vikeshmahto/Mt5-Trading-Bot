"""
signals/order_blocks.py
───────────────────────
Detect SMC Order Blocks (OBs) in a bar DataFrame.

═══════════════════════════════════════════════════════════════════════════════
SMC THEORY
═══════════════════════════════════════════════════════════════════════════════
An Order Block is the last opposing candle before a significant displacement
(impulsive move) that breaks a structural level.

  Bullish OB:
    • Find a bearish impulse candle → find the LAST BULLISH candle before it
      that kicks off a series of down-moves … wait, that's wrong direction.

    Actually: A BULLISH OB is the last BEARISH (down) candle immediately
    before a strong BULLISH displacement that takes out a swing high.
    Price will return to this OB zone (mitigation) and potentially bounce.

  Bearish OB:
    • The last BULLISH (up) candle immediately before a strong BEARISH
      displacement that takes out a swing low.

  Mitigation:
    • An OB is "mitigated" (touched) when price re-enters its high–low zone.
    • Once mitigated, it is less likely to act as support/resistance again.

  Impulse threshold:
    • We require the displacement candle to be > impulse_atr_mult × ATR
      to filter out random bars.

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API  (all PURE — no I/O, no state)
═══════════════════════════════════════════════════════════════════════════════

detect_order_blocks(df, timeframe, impulse_atr_mult, lookback) → list[OrderBlock]

mark_mitigated(obs, df) → list[OrderBlock]
    Update .mitigated / .mitigated_at fields by scanning subsequent bars.

get_unmitigated_obs(obs, direction) → list[OrderBlock]
    Filter to only fresh (unmitigated) OBs.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.types import Direction, OrderBlock
from signals.liquidity_sweep import _rolling_atr

log = get_logger(__name__)

# Minimum multiplier of ATR that a displacement candle must exceed
DEFAULT_IMPULSE_ATR_MULT = 1.5
# How many bars back to look for the triggering OB candle
DEFAULT_OB_LOOKBACK = 5


def detect_order_blocks(
    df: pd.DataFrame,
    timeframe: str = "",
    impulse_atr_mult: float = DEFAULT_IMPULSE_ATR_MULT,
    ob_lookback: int = DEFAULT_OB_LOOKBACK,
    mark_mitigation: bool = True,
) -> list[OrderBlock]:
    """
    Scan a bar DataFrame for Order Block formations.

    Args:
        df:               OHLCV DataFrame, UTC DatetimeIndex.
        timeframe:        Label for OrderBlock objects, e.g. "H1".
        impulse_atr_mult: A candle must have body ≥ this × ATR to be impulsive.
        ob_lookback:      Max bars to look back from the impulse to find the OB.
        mark_mitigation:  If True, scan forward bars to flag mitigated OBs.

    Returns:
        List of OrderBlock objects, chronological (by OB timestamp).
    """
    if len(df) < ob_lookback + 3:
        return []

    highs  = df["high"].to_numpy(dtype=float)
    lows   = df["low"].to_numpy(dtype=float)
    opens  = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    ts     = df.index
    atr    = _rolling_atr(df, period=14)

    obs: list[OrderBlock] = []
    seen_ob_timestamps: set = set()   # deduplicate (one OB per candle)

    for i in range(ob_lookback + 1, len(df)):
        body      = abs(closes[i] - opens[i])
        bar_atr   = atr[i] if atr[i] > 0 else 1.0
        is_impulse = body >= impulse_atr_mult * bar_atr

        if not is_impulse:
            continue

        # ── Bullish impulse candle ────────────────────────────────────────────
        if closes[i] > opens[i]:
            # Look back for the last BEARISH candle → that's the Bullish OB
            ob_idx = _find_last_opposing(closes, opens, i, ob_lookback, want_bearish=True)
            if ob_idx is not None and ts[ob_idx] not in seen_ob_timestamps:
                impulse_size = closes[i] - opens[i]
                obs.append(OrderBlock(
                    direction=Direction.BULLISH,
                    timestamp=ts[ob_idx],
                    high=float(highs[ob_idx]),
                    low=float(lows[ob_idx]),
                    open=float(opens[ob_idx]),
                    close=float(closes[ob_idx]),
                    impulse_size=round(float(impulse_size), 5),
                    timeframe=timeframe,
                ))
                seen_ob_timestamps.add(ts[ob_idx])

        # ── Bearish impulse candle ────────────────────────────────────────────
        elif closes[i] < opens[i]:
            # Look back for the last BULLISH candle → that's the Bearish OB
            ob_idx = _find_last_opposing(closes, opens, i, ob_lookback, want_bearish=False)
            if ob_idx is not None and ts[ob_idx] not in seen_ob_timestamps:
                impulse_size = opens[i] - closes[i]
                obs.append(OrderBlock(
                    direction=Direction.BEARISH,
                    timestamp=ts[ob_idx],
                    high=float(highs[ob_idx]),
                    low=float(lows[ob_idx]),
                    open=float(opens[ob_idx]),
                    close=float(closes[ob_idx]),
                    impulse_size=round(float(impulse_size), 5),
                    timeframe=timeframe,
                ))
                seen_ob_timestamps.add(ts[ob_idx])

    # Sort by OB timestamp
    obs.sort(key=lambda ob: ob.timestamp)

    if mark_mitigation:
        obs = _mark_mitigated(obs, df)

    log.debug(
        f"[{timeframe}] OBs detected: {len(obs)} "
        f"({sum(1 for o in obs if o.direction == Direction.BULLISH)} bull / "
        f"{sum(1 for o in obs if o.direction == Direction.BEARISH)} bear)"
    )
    return obs


def get_unmitigated_obs(
    obs: list[OrderBlock],
    direction: Optional[Direction] = None,
    n_recent: int = 10,
) -> list[OrderBlock]:
    """
    Return fresh (unmitigated) OBs, newest first, up to n_recent.

    Args:
        obs:       Full list from detect_order_blocks().
        direction: Filter by BULLISH/BEARISH, or None for both.
        n_recent:  Max results to return.
    """
    filtered = [
        ob for ob in obs
        if not ob.mitigated
        and (direction is None or ob.direction == direction)
    ]
    return filtered[-n_recent:]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _find_last_opposing(
    closes: np.ndarray,
    opens: np.ndarray,
    impulse_idx: int,
    lookback: int,
    want_bearish: bool,
) -> Optional[int]:
    """
    Scan backwards from impulse_idx to find the last opposing candle.

    want_bearish=True  → looking for a bearish candle (close < open)
    want_bearish=False → looking for a bullish candle (close > open)

    Returns the bar index, or None if not found within lookback bars.
    """
    for j in range(impulse_idx - 1, max(0, impulse_idx - lookback - 1), -1):
        if want_bearish and closes[j] < opens[j]:
            return j
        if not want_bearish and closes[j] > opens[j]:
            return j
    return None


def _mark_mitigated(obs: list[OrderBlock], df: pd.DataFrame) -> list[OrderBlock]:
    """
    For each OB, scan bars AFTER its formation to track genuine mitigation.

    In SMC theory:
      1. Departure: Price must first break OUT of the OB zone in the impulse direction.
         (e.g., for Bullish OB, price must trade above ob.high).
      2. Mitigation / Retest: Only AFTER departure, if a subsequent bar pulls back
         into the OB zone [ob.low, ob.high], is it marked as mitigated.
    """
    highs  = df["high"].to_numpy(dtype=float)
    lows   = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    ts     = df.index

    # Build a timestamp→index map for fast lookup
    ts_to_idx = {t: i for i, t in enumerate(ts)}

    for ob in obs:
        ob_idx = ts_to_idx.get(ob.timestamp)
        if ob_idx is None:
            continue

        departed = False

        for i in range(ob_idx + 1, len(df)):
            if ob.direction == Direction.BULLISH:
                # Check departure: impulse has pushed above the OB zone
                if not departed:
                    if closes[i] > ob.high or highs[i] > ob.high + (ob.high - ob.low) * 0.2:
                        departed = True
                    continue

                # Once departed, check if price returns to retest/mitigate the zone
                if lows[i] <= ob.high and highs[i] >= ob.low:
                    ob.mitigated   = True
                    ob.mitigated_at = ts[i]
                    break
                # Invalidation: price closes completely below the OB
                if closes[i] < ob.low:
                    ob.mitigated   = True
                    ob.mitigated_at = ts[i]
                    break

            else:  # BEARISH OB
                # Check departure: impulse has pushed below the OB zone
                if not departed:
                    if closes[i] < ob.low or lows[i] < ob.low - (ob.high - ob.low) * 0.2:
                        departed = True
                    continue

                # Once departed, check if price returns to retest/mitigate the zone
                if highs[i] >= ob.low and lows[i] <= ob.high:
                    ob.mitigated   = True
                    ob.mitigated_at = ts[i]
                    break
                # Invalidation: price closes completely above the OB
                if closes[i] > ob.high:
                    ob.mitigated   = True
                    ob.mitigated_at = ts[i]
                    break

    return obs
