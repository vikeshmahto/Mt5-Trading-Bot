"""
storage/models.py
─────────────────
SQLAlchemy ORM models.  Designed to run on both SQLite (backtest / dev)
and PostgreSQL / Neon (production).

Tables:
  signal_logs  — every signal generated_signal() emits, whether traded or not.
  trades       — every executed (or simulated backtest) trade, linked to a signal.

Design decisions:
  • UUIDs as primary keys → safe for distributed/multi-process use.
  • All timestamps stored as UTC with timezone.
  • Complex fields (bias, zone data) stored as JSON TEXT so they survive both
    SQLite (no native JSON type) and Postgres (JSONB upgrade path ready).
  • No foreign-key enforcement on SQLite (pragma needed) but FK defined so
    Postgres enforces referential integrity automatically.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float,
    ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.types import TypeDecorator, CHAR
import json


# ── UUID cross-dialect helper ─────────────────────────────────────────────────

class UUID(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses PostgreSQL's native UUID type when on Postgres,
    falls back to CHAR(36) on SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value) if not isinstance(value, uuid.UUID) else value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── SignalLog ─────────────────────────────────────────────────────────────────

class SignalLog(Base):
    """
    Every signal returned by generate_signal() is logged here.
    Includes signals that were NOT traded (score too low, no fill, etc.)
    so we can evaluate the signal engine's raw accuracy separately.

    Fields:
        executed:       True if a Trade row was created for this signal.
        confluence_score: 0–100 composite score at time of generation.
        d1_bias, h4_bias, h1_bias: 'bullish' | 'bearish' | 'neutral'
        ob_zone, fvg_zone: JSON strings with zone coordinates.
        notes:          Human-readable explanation from generator.
    """
    __tablename__ = "signal_logs"

    id               = Column(UUID, primary_key=True, default=uuid.uuid4)
    symbol           = Column(String(20),  nullable=False, index=True)
    timestamp        = Column(DateTime(timezone=True), nullable=False, index=True)
    direction        = Column(String(10),  nullable=False)   # bullish | bearish
    signal_type      = Column(String(30),  nullable=False)   # ob_retest | fvg_retest | …
    entry_price      = Column(Float,       nullable=False)
    stop_loss        = Column(Float,       nullable=False)
    take_profit      = Column(Float,       nullable=False)
    risk_reward      = Column(Float,       nullable=False)
    confluence_score = Column(Float,       nullable=False)
    setup_timeframe  = Column(String(5),   nullable=True)    # H1 | M15
    d1_bias          = Column(String(10),  nullable=True)
    h4_bias          = Column(String(10),  nullable=True)
    h1_bias          = Column(String(10),  nullable=True)
    ob_zone          = Column(Text,        nullable=True)    # JSON: {low, high, ts}
    fvg_zone         = Column(Text,        nullable=True)    # JSON: {bottom, top, ts}
    sweep_ts         = Column(DateTime(timezone=True), nullable=True)
    is_counter_trend = Column(Boolean,     default=False, nullable=False)
    notes            = Column(Text,        nullable=True)
    executed         = Column(Boolean,     default=False, nullable=False)
    environment      = Column(String(20),  nullable=False, default="backtest")
    created_at       = Column(DateTime(timezone=True),
                              default=lambda: datetime.now(timezone.utc))

    # Relationship (optional — loads the linked trade if it exists)
    trade = relationship("Trade", back_populates="signal", uselist=False)

    def __repr__(self) -> str:
        return (
            f"<SignalLog {self.symbol} {self.direction} "
            f"score={self.confluence_score} ts={self.timestamp}>"
        )

    @classmethod
    def from_signal(cls, signal, environment: str = "backtest") -> "SignalLog":
        """
        Construct a SignalLog from a core.types.Signal instance.
        This is the canonical way to persist a signal.
        """
        ob_zone = fvg_zone = sweep_ts = None

        if signal.trigger_ob:
            ob_zone = json.dumps({
                "low":  signal.trigger_ob.low,
                "high": signal.trigger_ob.high,
                "ts":   str(signal.trigger_ob.timestamp),
            })

        if signal.trigger_fvg:
            fvg_zone = json.dumps({
                "bottom": signal.trigger_fvg.bottom,
                "top":    signal.trigger_fvg.top,
                "ts":     str(signal.trigger_fvg.timestamp),
            })

        if signal.trigger_sweep:
            sweep_ts = signal.trigger_sweep.timestamp.to_pydatetime()

        return cls(
            symbol=signal.symbol,
            timestamp=signal.timestamp.to_pydatetime(),
            direction=signal.direction.value,
            signal_type=signal.signal_type.value,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            risk_reward=signal.risk_reward,
            confluence_score=signal.confluence_score,
            setup_timeframe=signal.setup_timeframe,
            d1_bias=signal.d1_bias.bias.value if signal.d1_bias else None,
            h4_bias=signal.h4_bias.bias.value if signal.h4_bias else None,
            h1_bias=signal.h1_bias.bias.value if signal.h1_bias else None,
            ob_zone=ob_zone,
            fvg_zone=fvg_zone,
            sweep_ts=sweep_ts,
            is_counter_trend=getattr(signal, "is_counter_trend", False),
            notes=signal.notes,
            executed=False,
            environment=environment,
        )


# ── Trade ─────────────────────────────────────────────────────────────────────

class Trade(Base):
    """
    A trade that was executed (live/paper) or simulated (backtest).
    Linked 1:1 to the SignalLog that generated it.

    exit_reason values:
        'tp_hit'   — take-profit reached
        'sl_hit'   — stop-loss hit
        'manual'   — manually closed
        'timeout'  — max hold-time reached (live runner)
        'end_of_data' — backtest ran out of bars
        'open'     — trade still open (null exit fields)

    pnl_r = pnl expressed in R-multiples (1R = risk_points × lot_size × contract_size)
    """
    __tablename__ = "trades"

    id            = Column(UUID,           primary_key=True, default=uuid.uuid4)
    signal_id     = Column(UUID,           ForeignKey("signal_logs.id"), nullable=True, index=True)
    symbol        = Column(String(20),     nullable=False, index=True)
    direction     = Column(String(10),     nullable=False)
    entry_time    = Column(DateTime(timezone=True), nullable=True)
    entry_price   = Column(Float,          nullable=True)
    stop_loss     = Column(Float,          nullable=True)
    take_profit   = Column(Float,          nullable=True)
    lot_size      = Column(Float,          nullable=True)
    exit_time     = Column(DateTime(timezone=True), nullable=True)
    exit_price    = Column(Float,          nullable=True)
    pnl           = Column(Float,          nullable=True)   # in account currency
    pnl_r         = Column(Float,          nullable=True)   # in R-multiples
    exit_reason   = Column(String(20),     nullable=True)
    mt5_ticket    = Column(BigInteger,     nullable=True)   # MT5 order ticket
    commission    = Column(Float,          nullable=True, default=0.0)
    slippage_pts  = Column(Float,          nullable=True, default=0.0)
    environment   = Column(String(20),     nullable=False, default="backtest")
    setup_score   = Column(Float,          nullable=True)   # confluence_score snapshot
    notes         = Column(Text,           nullable=True)
    created_at    = Column(DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc))

    # Relationship
    signal = relationship("SignalLog", back_populates="trade")

    def __repr__(self) -> str:
        return (
            f"<Trade {self.symbol} {self.direction} "
            f"entry={self.entry_price} pnl={self.pnl} "
            f"reason={self.exit_reason}>"
        )

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    @property
    def risk_points(self) -> float | None:
        if self.entry_price is not None and self.stop_loss is not None:
            return abs(self.entry_price - self.stop_loss)
        return None

    @property
    def reward_points(self) -> float | None:
        if self.entry_price is not None and self.take_profit is not None:
            return abs(self.take_profit - self.entry_price)
        return None

# ── System Status (Heartbeat) ─────────────────────────────────────────────────

class SystemStatus(Base):
    """
    Tracks the heartbeat and liveness of various system components
    (like live_runner) to display on the dashboard.
    """
    __tablename__ = "system_status"

    id           = Column(String(50), primary_key=True)  # e.g., "live_runner"
    timestamp    = Column(DateTime(timezone=True), nullable=False)
    status       = Column(String(50), nullable=False)    # e.g., "active", "stopped"
    extra_info   = Column(Text, nullable=True)           # JSON string for active_symbols, environment, etc.
