"""
storage/repository.py
─────────────────────
High-level CRUD operations for signals and trades.
All DB access in the system goes through this module — nothing else
should import SQLAlchemy directly.

Public API:
    save_signal(signal, environment)      → SignalLog
    mark_signal_executed(signal_id)       → None
    save_trade(trade_row)                 → Trade
    close_trade(trade_id, exit_price, exit_time, exit_reason, pnl) → Trade
    get_open_trades(symbol)               → list[Trade]
    get_trades(symbol, limit, environment)→ list[Trade]
    get_signals(symbol, limit)            → list[SignalLog]
    get_daily_pnl(date)                   → float
    get_trade_stats(symbol, environment)  → dict
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from core.logger import get_logger
from core.types import Signal
from storage.db import get_session
from storage.models import SignalLog, Trade

log = get_logger(__name__)


# ── Signal operations ─────────────────────────────────────────────────────────

def save_signal(
    signal: Signal,
    environment: str = "backtest",
) -> SignalLog:
    """
    Persist a Signal to the signal_logs table.

    Args:
        signal:      core.types.Signal instance from generate_signal().
        environment: "backtest" | "paper" | "live"

    Returns:
        The saved SignalLog ORM instance (with id populated).
    """
    row = SignalLog.from_signal(signal, environment=environment)
    with get_session() as session:
        session.add(row)
        session.flush()   # populate row.id before commit
        session.expunge(row)  # detach so it's usable after session closes
    log.debug(f"Signal saved: {row.id} | {row.symbol} {row.direction}")
    return row


def mark_signal_executed(signal_id: uuid.UUID) -> None:
    """Set executed=True on a signal after a trade is placed."""
    with get_session() as session:
        stmt = select(SignalLog).where(SignalLog.id == signal_id)
        row  = session.execute(stmt).scalar_one_or_none()
        if row:
            row.executed = True


def get_signals(
    symbol: Optional[str] = None,
    limit: int = 100,
    environment: Optional[str] = None,
    executed_only: bool = False,
) -> list[SignalLog]:
    """Retrieve recent signal logs, newest first."""
    with get_session() as session:
        stmt = select(SignalLog).order_by(SignalLog.timestamp.desc()).limit(limit)
        if symbol:
            stmt = stmt.where(SignalLog.symbol == symbol)
        if environment:
            stmt = stmt.where(SignalLog.environment == environment)
        if executed_only:
            stmt = stmt.where(SignalLog.executed.is_(True))
        rows = session.execute(stmt).scalars().all()
        session.expunge_all()
    return list(rows)


# ── Trade operations ──────────────────────────────────────────────────────────

def save_trade(
    signal_log: SignalLog,
    lot_size: float,
    entry_price: float,
    entry_time: datetime,
    environment: str = "backtest",
    mt5_ticket: Optional[int] = None,
    commission: float = 0.0,
    slippage_pts: float = 0.0,
    notes: str = "",
) -> Trade:
    """
    Create and persist a new Trade row linked to a SignalLog.

    Marks the parent signal as executed automatically.

    Args:
        signal_log:    The SignalLog this trade stems from.
        lot_size:      Size of the position in lots.
        entry_price:   Actual fill price (may differ from signal.entry_price).
        entry_time:    Actual fill timestamp (UTC).
        environment:   "backtest" | "paper" | "live"
        mt5_ticket:    MT5 order ticket ID (None for backtest).
        commission:    Round-trip commission in account currency.
        slippage_pts:  Entry slippage in price points.
        notes:         Optional annotation.

    Returns:
        The saved Trade ORM instance.
    """
    trade = Trade(
        signal_id=signal_log.id,
        symbol=signal_log.symbol,
        direction=signal_log.direction,
        entry_time=entry_time,
        entry_price=entry_price,
        stop_loss=signal_log.stop_loss,
        take_profit=signal_log.take_profit,
        lot_size=lot_size,
        mt5_ticket=mt5_ticket,
        commission=commission,
        slippage_pts=slippage_pts,
        environment=environment,
        setup_score=signal_log.confluence_score,
        notes=notes,
    )

    with get_session() as session:
        session.add(trade)
        # Mark the signal as executed
        stmt = select(SignalLog).where(SignalLog.id == signal_log.id)
        sig  = session.execute(stmt).scalar_one_or_none()
        if sig:
            sig.executed = True
        session.flush()
        session.expunge(trade)

    log.info(
        f"Trade opened: {trade.symbol} {trade.direction} "
        f"entry={entry_price} lot={lot_size} [{environment}]"
    )
    return trade


def close_trade(
    trade_id: uuid.UUID,
    exit_price: float,
    exit_time: datetime,
    exit_reason: str,
    pnl: float,
) -> Optional[Trade]:
    """
    Record the closing of a trade.

    Args:
        trade_id:    UUID of the Trade to close.
        exit_price:  Actual exit price.
        exit_time:   UTC close timestamp.
        exit_reason: 'tp_hit' | 'sl_hit' | 'manual' | 'timeout' | 'end_of_data'
        pnl:         Realised P&L in account currency (after commission).

    Returns:
        Updated Trade instance, or None if not found.
    """
    with get_session() as session:
        stmt  = select(Trade).where(Trade.id == trade_id)
        trade = session.execute(stmt).scalar_one_or_none()
        if trade is None:
            log.warning(f"close_trade: trade {trade_id} not found")
            return None

        trade.exit_price  = exit_price
        trade.exit_time   = exit_time
        trade.exit_reason = exit_reason
        trade.pnl         = pnl

        # Compute R-multiple
        if trade.entry_price and trade.stop_loss:
            risk_pts = abs(trade.entry_price - trade.stop_loss)
            if risk_pts > 0 and trade.lot_size:
                trade.pnl_r = pnl / (risk_pts * trade.lot_size) if trade.lot_size else None
            else:
                trade.pnl_r = None

        session.flush()
        session.expunge(trade)

    log.info(
        f"Trade closed: {trade.symbol} {trade.direction} "
        f"exit={exit_price} pnl={pnl:+.2f} reason={exit_reason}"
    )
    return trade


def get_open_trades(symbol: Optional[str] = None) -> list[Trade]:
    """Return all trades with no exit_time (still open)."""
    with get_session() as session:
        stmt = select(Trade).where(Trade.exit_time.is_(None))
        if symbol:
            stmt = stmt.where(Trade.symbol == symbol)
        rows = session.execute(stmt).scalars().all()
        session.expunge_all()
    return list(rows)


def get_trades(
    symbol: Optional[str] = None,
    limit: int = 200,
    environment: Optional[str] = None,
) -> list[Trade]:
    """Retrieve closed trades, newest first."""
    with get_session() as session:
        stmt = (
            select(Trade)
            .where(Trade.exit_time.isnot(None))
            .order_by(Trade.exit_time.desc())
            .limit(limit)
        )
        if symbol:
            stmt = stmt.where(Trade.symbol == symbol)
        if environment:
            stmt = stmt.where(Trade.environment == environment)
        rows = session.execute(stmt).scalars().all()
        session.expunge_all()
    return list(rows)


def get_daily_pnl(
    target_date: Optional[date] = None,
    environment: str = "backtest",
) -> float:
    """
    Sum of P&L for all closed trades on target_date (UTC).
    Defaults to today.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         tzinfo=timezone.utc)
    day_end   = datetime(target_date.year, target_date.month, target_date.day,
                         23, 59, 59, tzinfo=timezone.utc)

    with get_session() as session:
        stmt = select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
            Trade.exit_time.between(day_start, day_end),
            Trade.environment == environment,
            Trade.pnl.isnot(None),
        )
        total = session.execute(stmt).scalar()
    return float(total or 0.0)


def get_trade_stats(
    symbol: Optional[str] = None,
    environment: str = "backtest",
) -> dict:
    """
    Return a summary dict with key statistics from closed trades.

    Returns:
        {
            "total": int,
            "wins": int, "losses": int,
            "win_rate": float,          # 0–1
            "avg_pnl": float,
            "avg_r": float,
            "total_pnl": float,
            "best_trade": float,
            "worst_trade": float,
        }
    """
    trades = get_trades(symbol=symbol, limit=10_000, environment=environment)
    closed = [t for t in trades if t.pnl is not None]

    if not closed:
        return {k: 0 for k in
                ["total","wins","losses","win_rate","avg_pnl","avg_r",
                 "total_pnl","best_trade","worst_trade"]}

    pnls  = [t.pnl  for t in closed]
    r_muls = [t.pnl_r for t in closed if t.pnl_r is not None]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    return {
        "total":       len(closed),
        "wins":        len(wins),
        "losses":      len(losses),
        "win_rate":    len(wins) / len(closed),
        "avg_pnl":     sum(pnls) / len(pnls),
        "avg_r":       sum(r_muls) / len(r_muls) if r_muls else 0.0,
        "total_pnl":   sum(pnls),
        "best_trade":  max(pnls),
        "worst_trade": min(pnls),
    }
# ── System Status (Heartbeat) ──────────────────────────────────────────────────

def update_heartbeat(component: str, status: str, extra_info: dict | None = None) -> None:
    """Upsert the system status for a given component."""
    from storage.models import SystemStatus
    import json
    with get_session() as session:
        row = session.execute(
            select(SystemStatus).where(SystemStatus.id == component)
        ).scalar_one_or_none()
        
        if not row:
            row = SystemStatus(id=component)
            session.add(row)
            
        row.timestamp = datetime.now(timezone.utc)
        row.status = status
        if extra_info is not None:
            row.extra_info = json.dumps(extra_info)
        session.commit()
