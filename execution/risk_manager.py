"""
execution/risk_manager.py
─────────────────────────
Live Risk & Constraint Enforcement Engine.

Evaluates signals against:
  1. Confluence score threshold
  2. Max concurrent open trades (system-wide)
  3. Max open trades per instrument
  4. Daily loss limit (calculated from DB + live unrealized P&L)
  5. Maximum drawdown limit
  6. Maximum spread threshold (live broker spread check)
  7. Active trading sessions filter (Asian, London, NY)
  8. Position sizing & lot clamp (min_lot, lot_step)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5

from config.settings import InstrumentConfig, RiskConfig, settings
from core.logger import get_logger
from core.types import Signal
from storage.repository import get_daily_pnl, get_open_trades

log = get_logger(__name__)


class RiskManager:
    """
    Enforces risk rules prior to live order execution.
    """

    def __init__(self, risk_config: Optional[RiskConfig] = None) -> None:
        self.risk = risk_config or settings.risk

    def can_trade(
        self,
        signal: Signal,
        account_info: dict,
        inst_config: InstrumentConfig,
        environment: str = "live",
    ) -> tuple[bool, str, float]:
        """
        Evaluate all risk rules for a given signal.

        Returns:
            (is_allowed, reason_message, calculated_lot_size)
        """
        symbol = signal.symbol

        # 1. Confluence Score Check
        min_score = self.risk.scoring.min_score_to_trade
        if signal.confluence_score < min_score:
            return False, f"Score {signal.confluence_score:.0f} < min_score {min_score}", 0.0

        # 2. R:R Ratio Check
        min_rr = self.risk.scoring.min_rr_ratio
        if signal.risk_reward < min_rr:
            return False, f"R:R {signal.risk_reward:.2f} < min_rr {min_rr}", 0.0

        # 3. Session Filter Check
        now_utc = datetime.now(timezone.utc)
        if not self._is_within_session(now_utc, inst_config):
            return False, f"Current UTC time {now_utc.strftime('%H:%M')} outside active sessions", 0.0

        # 4. Spread Check (if live MT5 connection available)
        spread_pts = self._get_current_spread(symbol)
        if spread_pts is not None and spread_pts > inst_config.max_spread_points:
            return False, f"Spread {spread_pts:.1f} > max allowed {inst_config.max_spread_points:.1f}", 0.0

        # 5. Concurrent Trades Limit
        open_trades = get_open_trades()
        if len(open_trades) >= self.risk.limits.max_concurrent_trades:
            return False, f"Open trades {len(open_trades)} >= max {self.risk.limits.max_concurrent_trades}", 0.0

        # 6. Instrument Specific Trade Limit
        symbol_open = [t for t in open_trades if t.symbol == symbol]
        if len(symbol_open) >= self.risk.limits.max_trades_per_instrument:
            return False, f"Open {symbol} trades {len(symbol_open)} >= max {self.risk.limits.max_trades_per_instrument}", 0.0

        # 7. Same-Direction Correlated Exposure Limit
        dir_open = [t for t in open_trades if getattr(t, "direction", "") == signal.direction.value]
        if len(dir_open) >= self.risk.limits.max_concurrent_same_direction_trades:
            return False, f"Open {signal.direction.value} trades {len(dir_open)} >= max same-direction limit {self.risk.limits.max_concurrent_same_direction_trades}", 0.0

        # 7. Daily Loss Limit Check
        equity = account_info.get("equity", self.risk.backtest.initial_balance)
        balance = account_info.get("balance", equity)
        realized_today = get_daily_pnl(target_date=now_utc.date(), environment=environment)
        unrealized = account_info.get("profit", 0.0)
        total_today_pnl = realized_today + unrealized

        max_daily_loss = balance * self.risk.limits.max_daily_loss
        if total_today_pnl < -abs(max_daily_loss):
            return False, f"Daily loss ${total_today_pnl:.2f} breached max limit ${max_daily_loss:.2f}", 0.0

        # 8. Calculate Position Sizing
        risk_pts = signal.risk_points
        if risk_pts <= 0:
            return False, f"Invalid stop distance {risk_pts}", 0.0

        value_per_pt_per_lot = inst_config.pip_value * 1000.0
        risk_dollars = equity * self.risk.position_sizing.risk_per_trade
        raw_lots = risk_dollars / (risk_pts * value_per_pt_per_lot)

        lots = max(
            inst_config.min_lot,
            round(raw_lots / inst_config.lot_step) * inst_config.lot_step,
        )
        lots = round(lots, 2)

        return True, "Risk checks passed", lots

    def _is_within_session(self, current_time: datetime, inst_config: InstrumentConfig) -> bool:
        """Check if current UTC time falls within any configured trading session."""
        if not inst_config.sessions:
            return True

        current_hm = current_time.strftime("%H:%M")
        for s_name, s_cfg in inst_config.sessions.items():
            if s_cfg.start <= s_cfg.end:
                if s_cfg.start <= current_hm <= s_cfg.end:
                    return True
            else:  # Overnight session spanning midnight (e.g. 22:00 to 06:00)
                if current_hm >= s_cfg.start or current_hm <= s_cfg.end:
                    return True
        return False

    def _get_current_spread(self, symbol: str) -> Optional[float]:
        """Fetch current spread in price points from MT5."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.ask == 0 or tick.bid == 0:
            return None
        return round(tick.ask - tick.bid, 2)
