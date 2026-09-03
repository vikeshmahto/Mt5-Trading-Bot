"""
core/types.py
─────────────
Shared dataclasses and enums used across the entire system.
Expanded incrementally — new types added as each step is built.

Current types:
  Bias          – market structure direction per timeframe
  BiasResult    – output of signals/bias.py
  Direction     – BULLISH/BEARISH label for zones
  LiquiditySweep, OrderBlock, FairValueGap – Step 5 zone types
  Signal        – Step 6 trade signal (pure output of generator)

Step 7 will add: Setup, Trade (DB models)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import pandas as pd


# ── Bias ─────────────────────────────────────────────────────────────────────

class Bias(Enum):
    """Market structure direction derived from swing HH/HL vs LH/LL analysis."""
    BULLISH = "bullish"     # HH + HL sequence — buyers in control
    BEARISH = "bearish"     # LH + LL sequence — sellers in control
    NEUTRAL = "neutral"     # mixed / insufficient data


# ── Swing points ──────────────────────────────────────────────────────────────

class SwingType(Enum):
    HIGH = "high"
    LOW  = "low"


@dataclass
class SwingPoint:
    """A single confirmed swing high or low."""
    timestamp: pd.Timestamp
    price: float
    kind: SwingType          # HIGH or LOW
    bar_index: int           # position in the source DataFrame


# ── BiasResult ────────────────────────────────────────────────────────────────

@dataclass
class BiasResult:
    """
    Full output from bias detection on a single timeframe's bars.

    Attributes:
        bias:           BULLISH / BEARISH / NEUTRAL
        timeframe:      String label, e.g. "H1"
        swing_highs:    Confirmed swing highs in chronological order
        swing_lows:     Confirmed swing lows in chronological order
        last_hh:        Price of the most recent Higher High (None if not applicable)
        last_hl:        Price of the most recent Higher Low  (None if not applicable)
        last_lh:        Price of the most recent Lower High  (None if not applicable)
        last_ll:        Price of the most recent Lower Low   (None if not applicable)
        notes:          Human-readable explanation of why this bias was assigned
    """
    bias: Bias
    timeframe: str
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows:  list[SwingPoint] = field(default_factory=list)
    last_hh: Optional[float] = None
    last_hl: Optional[float] = None
    last_lh: Optional[float] = None
    last_ll: Optional[float] = None
    notes: str = ""

    def __str__(self) -> str:
        return (
            f"[{self.timeframe}] {self.bias.value.upper():8s} | "
            f"SH={len(self.swing_highs)} SL={len(self.swing_lows)} | "
            f"{self.notes}"
        )


# ── Direction helper (used by sweep / OB / FVG) ───────────────────────────────

class Direction(Enum):
    """Directional label for sweeps, OBs, FVGs."""
    BULLISH = "bullish"   # sweep of sell-side / bullish OB / bullish FVG
    BEARISH = "bearish"   # sweep of buy-side  / bearish OB / bearish FVG


# ── LiquiditySweep ───────────────────────────────────────────────────────────

@dataclass
class LiquiditySweep:
    """
    A liquidity sweep event: price briefly violates a swing level
    (taking out stop-losses) and then closes back inside.

    Attributes:
        direction:      BULLISH = swept sell-side (below swing low) then recovered.
                        BEARISH = swept buy-side  (above swing high) then reversed.
        timestamp:      Open time of the sweeping bar.
        swept_level:    Price of the swing high/low that was violated.
        sweep_low:      Lowest point reached during the sweep bar (for bullish).
        sweep_high:     Highest point reached during the sweep bar (for bearish).
        close:          Close price of the sweeping bar (back inside the level).
        displacement:   Body size / ATR ratio — higher = more aggressive sweep.
        timeframe:      Source timeframe string, e.g. "M15".
    """
    direction:    Direction
    timestamp:    pd.Timestamp
    swept_level:  float
    sweep_low:    float
    sweep_high:   float
    close:        float
    displacement: float
    timeframe:    str = ""

    def __str__(self) -> str:
        tag = "BullSweep" if self.direction == Direction.BULLISH else "BearSweep"
        return (
            f"{tag} @ {self.timestamp} | swept={self.swept_level:.2f} | "
            f"close={self.close:.2f} | [{self.timeframe}]"
        )


# ── OrderBlock ────────────────────────────────────────────────────────────────

@dataclass
class OrderBlock:
    """
    An SMC Order Block: the last opposing candle before an impulsive move
    that breaks structure.

    Attributes:
        direction:  BULLISH = last bearish candle before bullish impulse (buy OB).
                    BEARISH = last bullish candle before bearish impulse (sell OB).
        timestamp:  Open time of the OB candle.
        high:       High of the OB candle.
        low:        Low  of the OB candle.
        open:       Open of the OB candle.
        close:      Close of the OB candle.
        impulse_size:  Size of the triggering impulse move in price points.
        mitigated:  True once price has re-entered the OB zone.
        mitigated_at: Timestamp of first mitigation (None if not yet mitigated).
        timeframe:  Source timeframe string.
    """
    direction:     Direction
    timestamp:     pd.Timestamp
    high:          float
    low:           float
    open:          float
    close:         float
    impulse_size:  float
    mitigated:     bool              = False
    mitigated_at:  Optional[pd.Timestamp] = None
    timeframe:     str               = ""

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2

    def is_price_inside(self, price: float) -> bool:
        """True if price is within the OB zone."""
        return self.low <= price <= self.high

    def __str__(self) -> str:
        tag = "BullOB" if self.direction == Direction.BULLISH else "BearOB"
        mit = " [MIT]" if self.mitigated else ""
        return (
            f"{tag} @ {self.timestamp} | zone=[{self.low:.2f}–{self.high:.2f}]"
            f"{mit} | [{self.timeframe}]"
        )


# ── FairValueGap ─────────────────────────────────────────────────────────────

@dataclass
class FairValueGap:
    """
    A 3-candle Fair Value Gap (imbalance).

    Bullish FVG:  bar[i].high  <  bar[i+2].low   → gap above bar i's high.
    Bearish FVG:  bar[i].low   >  bar[i+2].high  → gap below bar i's low.

    Attributes:
        direction:  BULLISH (price gapped up) or BEARISH (price gapped down).
        timestamp:  Open time of the MIDDLE bar (bar i+1).
        top:        Upper edge of the gap.
        bottom:     Lower edge of the gap.
        filled:     True once price fully closes through the gap.
        partially_filled: True once price has entered but not fully closed it.
        retested:   True once price re-entered the gap (at least partially).
        retested_at: Timestamp of first retest.
        timeframe:  Source timeframe string.
    """
    direction:        Direction
    timestamp:        pd.Timestamp
    top:              float
    bottom:           float
    filled:           bool              = False
    partially_filled: bool              = False
    retested:         bool              = False
    retested_at:      Optional[pd.Timestamp] = None
    timeframe:        str               = ""

    @property
    def size(self) -> float:
        """Gap size in price points."""
        return self.top - self.bottom

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2

    def is_price_inside(self, price: float) -> bool:
        """True if price is within the FVG zone."""
        return self.bottom <= price <= self.top

    def __str__(self) -> str:
        tag = "BullFVG" if self.direction == Direction.BULLISH else "BearFVG"
        status = " [FILLED]" if self.filled else (" [PARTIAL]" if self.partially_filled else "")
        return (
            f"{tag} @ {self.timestamp} | gap=[{self.bottom:.2f}–{self.top:.2f}]"
            f" size={self.size:.2f}{status} | [{self.timeframe}]"
        )


# ── Signal ────────────────────────────────────────────────────────────────────

class SignalType(Enum):
    """What kind of setup triggered the signal."""
    OB_RETEST   = "ob_retest"    # price entered an order block zone
    FVG_RETEST  = "fvg_retest"   # price entered a fair value gap
    OB_FVG      = "ob_fvg"       # OB + FVG confluence (strongest)
    SWEEP_ENTRY = "sweep_entry"  # immediate post-sweep reversal entry


@dataclass
class Signal:
    """
    A fully-formed trade signal — the pure output of signals/generator.py.

    This is the single contract between the signal engine and everything
    downstream (backtest engine, live runner, DB logger, scorer).

    PURE DATA — no methods that perform I/O, DB writes, or order calls.

    Attributes:
        symbol:          MT5 symbol, e.g. "XAUUSD".
        direction:       BULLISH (long) or BEARISH (short).
        signal_type:     Which pattern triggered the entry.
        timestamp:       Timestamp of the M1 trigger bar (UTC).
        entry_price:     Proposed entry price.
        stop_loss:       Stop-loss price.
        take_profit:     Take-profit price.
        risk_reward:     Actual R:R = |tp - entry| / |entry - sl|.
        confluence_score: 0–100 composite score from bias + zones.
        d1_bias:         D1 BiasResult at signal time.
        h4_bias:         H4 BiasResult at signal time.
        h1_bias:         H1 BiasResult at signal time.
        trigger_ob:      The OrderBlock that price entered (if OB signal).
        trigger_fvg:     The FairValueGap being retested (if FVG signal).
        trigger_sweep:   The LiquiditySweep that preceded the signal.
        setup_timeframe: Timeframe where the OB/FVG was detected (H1 or M15).
        notes:           Human-readable explanation for logging/debugging.
    """
    symbol:           str
    direction:        Direction
    signal_type:      SignalType
    timestamp:        pd.Timestamp
    entry_price:      float
    stop_loss:        float
    take_profit:      float
    risk_reward:      float
    confluence_score: float

    # Bias context
    d1_bias: Optional["BiasResult"] = None   # forward ref — same file
    h4_bias: Optional["BiasResult"] = None
    h1_bias: Optional["BiasResult"] = None

    # Zone context
    trigger_ob:    Optional[OrderBlock]      = None
    trigger_fvg:   Optional[FairValueGap]    = None
    trigger_sweep: Optional[LiquiditySweep]  = None
    setup_timeframe: str                     = ""
    is_counter_trend: bool                   = False
    notes:           str                     = ""

    @property
    def risk_points(self) -> float:
        """Distance from entry to SL in price points."""
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward_points(self) -> float:
        """Distance from entry to TP in price points."""
        return abs(self.take_profit - self.entry_price)

    def __str__(self) -> str:
        d = "LONG" if self.direction == Direction.BULLISH else "SHORT"
        return (
            f"[{self.symbol}] {d} {self.signal_type.value} | "
            f"entry={self.entry_price:.2f} SL={self.stop_loss:.2f} "
            f"TP={self.take_profit:.2f} | RR={self.risk_reward:.2f} "
            f"score={self.confluence_score:.0f} | {self.timestamp}"
        )
