"""
backtest/metrics.py
───────────────────
Comprehensive quantitative performance metrics calculator for trading strategies.

Calculates:
  • Basic: Total Trades, Win Rate, Loss Rate, Gross Profit/Loss, Net PnL
  • Risk-Adjusted: Profit Factor, Sharpe Ratio, Sortino Ratio, Calmar Ratio
  • Expectancy: Average Trade ($ and R), Win/Loss PnL Ratio, Expectancy per trade
  • Drawdown: Max Drawdown ($, %), Max Drawdown Duration, Recovery Factor
  • Streaks: Max Consecutive Wins, Max Consecutive Losses
  • Categorical Breakdowns:
      - By Direction (Long vs Short)
      - By Setup Type (ob_retest, fvg_retest, etc.)
      - By Confluence Score tier (e.g., >=70 vs <70)
      - By Day of Week / Session

PUBLIC API:
  calculate_metrics(trades: list[TradeRecord], equity_curve: pd.Series, initial_balance: float) -> PerformanceReport
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from backtest.engine import TradeRecord


@dataclass
class BreakdownStats:
    """Statistics for a sub-group of trades (e.g. Longs or OB setups)."""
    count: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_r: float = 0.0
    profit_factor: float = 0.0


@dataclass
class PerformanceReport:
    """Comprehensive performance metrics bundle."""
    # Summary
    initial_balance: float = 10000.0
    final_balance: float = 10000.0
    total_pnl: float = 0.0
    return_pct: float = 0.0

    # Trade counts
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0

    # PnL metrics
    total_commission: float = 0.0
    net_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_win_pnl: float = 0.0
    avg_loss_pnl: float = 0.0
    win_loss_ratio: float = 0.0
    expectancy_dollars: float = 0.0
    expectancy_r: float = 0.0

    # Risk-adjusted & Drawdown
    max_drawdown_dollars: float = 0.0
    max_drawdown_pct: float = 0.0
    recovery_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Streaks
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Breakdowns
    by_direction: dict[str, BreakdownStats] = field(default_factory=dict)
    by_setup_type: dict[str, BreakdownStats] = field(default_factory=dict)
    by_score_tier: dict[str, BreakdownStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to standard serializable dictionary."""
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "total_pnl": self.total_pnl,
            "total_commission": self.total_commission,
            "net_pnl": self.net_pnl,
            "return_pct": self.return_pct,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "expectancy_r": self.expectancy_r,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
        }

    def format_text_table(self) -> str:
        """Format a human-readable performance summary table."""
        lines = [
            "=" * 68,
            "               PERFORMANCE METRICS REPORT",
            "=" * 68,
            f"  Capital Overview:",
            f"    Initial Balance      : ${self.initial_balance:,.2f}",
            f"    Final Balance        : ${self.final_balance:,.2f}",
            f"    Gross Profit / Loss  : ${self.total_pnl:+,.2f}",
            f"    Total Commissions    : ${self.total_commission:,.2f}",
            f"    Net Profit / Loss    : ${self.net_pnl:+,.2f} ({self.return_pct:+.2%})",
            "",
            f"  Trade Statistics:",
            f"    Total Trades Closed  : {self.total_trades}",
            f"    Win / Loss Count     : {self.wins} Wins / {self.losses} Losses",
            f"    Win Rate             : {self.win_rate:.2%}",
            f"    Gross Profit         : ${self.gross_profit:,.2f}",
            f"    Gross Loss           : ${self.gross_loss:,.2f}",
            f"    Profit Factor        : {self.profit_factor:.2f}",
            f"    Avg Trade PnL        : ${self.avg_trade_pnl:+.2f}",
            f"    Avg Win / Avg Loss   : ${self.avg_win_pnl:.2f} / ${self.avg_loss_pnl:.2f}",
            f"    Win/Loss PnL Ratio   : {self.win_loss_ratio:.2f}",
            f"    Expectancy per Trade : {self.expectancy_r:+.2f}R (${self.expectancy_dollars:+.2f})",
            "",
            f"  Risk & Drawdown:",
            f"    Max Drawdown         : ${self.max_drawdown_dollars:,.2f} ({self.max_drawdown_pct:.2%})",
            f"    Recovery Factor      : {self.recovery_factor:.2f}",
            f"    Sharpe Ratio (ann.)  : {self.sharpe_ratio:.2f}",
            f"    Sortino Ratio (ann.) : {self.sortino_ratio:.2f}",
            f"    Max Win Streak       : {self.max_consecutive_wins}",
            f"    Max Loss Streak      : {self.max_consecutive_losses}",
            "=" * 68,
        ]

        for d_name, stats in self.by_direction.items():
            lines.append(
                f"    {d_name.upper():8s} : {stats.count:3d} trades | WinRate: {stats.win_rate:.1%} | "
                f"PnL: ${stats.total_pnl:+8.2f} | Avg R: {stats.avg_r:+.2f}R | PF: {stats.profit_factor:.2f}"
            )

        if self.by_setup_type:
            lines.append("")
            lines.append("  Breakdown by Setup Type:")
            for s_name, stats in self.by_setup_type.items():
                lines.append(
                    f"    {s_name:12s} : {stats.count:3d} trades | WinRate: {stats.win_rate:.1%} | "
                    f"PnL: ${stats.total_pnl:+8.2f} | Avg R: {stats.avg_r:+.2f}R | PF: {stats.profit_factor:.2f}"
                )

        if self.by_score_tier:
            lines.append("")
            lines.append("  Breakdown by Confluence Score Tier:")
            for tier, stats in self.by_score_tier.items():
                lines.append(
                    f"    {tier:12s} : {stats.count:3d} trades | WinRate: {stats.win_rate:.1%} | "
                    f"PnL: ${stats.total_pnl:+8.2f} | Avg R: {stats.avg_r:+.2f}R"
                )

        lines.append("=" * 68)
        return "\n".join(lines)


# ── Core Calculation ──────────────────────────────────────────────────────────

def calculate_metrics(
    trades: list[TradeRecord],
    equity_curve: Optional[pd.Series] = None,
    initial_balance: float = 10000.0,
    annualization_factor: float = 252 * 24 * 4,  # M15 bars per trading year approx
) -> PerformanceReport:
    """
    Compute full quantitative metrics from a list of TradeRecords.

    Args:
        trades: List of closed (or open) TradeRecords from backtest or live logs.
        equity_curve: Timestamp-indexed Series of account equity values.
        initial_balance: Starting account equity in dollars.
        annualization_factor: Factor for Sharpe/Sortino annualization.
    """
    closed = [t for t in trades if t.exit_price is not None and t.pnl is not None]

    report = PerformanceReport(
        initial_balance=initial_balance,
        final_balance=initial_balance,
        total_trades=len(closed),
    )

    if not closed:
        return report

    pnls = [float(t.pnl) for t in closed]
    commissions = [float(t.commission) for t in closed]
    r_multiples = [float(t.pnl_r) if t.pnl_r is not None else 0.0 for t in closed]

    report.total_pnl = float(np.sum(pnls))
    report.total_commission = float(np.sum(commissions))
    report.net_pnl = report.total_pnl - report.total_commission
    report.final_balance = initial_balance + report.net_pnl
    report.return_pct = report.net_pnl / initial_balance if initial_balance > 0 else 0.0

    wins = [p for p in pnls if p > 0]
    losses = [abs(p) for p in pnls if p < 0]

    report.wins = len(wins)
    report.losses = len(losses)
    report.win_rate = len(wins) / len(closed) if closed else 0.0
    report.loss_rate = len(losses) / len(closed) if closed else 0.0

    report.gross_profit = float(np.sum(wins))
    report.gross_loss = float(np.sum(losses))
    report.profit_factor = (
        report.gross_profit / report.gross_loss if report.gross_loss > 0 else (float("inf") if report.gross_profit > 0 else 0.0)
    )

    report.avg_trade_pnl = float(np.mean(pnls)) if pnls else 0.0
    report.avg_win_pnl = float(np.mean(wins)) if wins else 0.0
    report.avg_loss_pnl = float(np.mean(losses)) if losses else 0.0
    report.win_loss_ratio = report.avg_win_pnl / report.avg_loss_pnl if report.avg_loss_pnl > 0 else 0.0

    # Expectancy = (WinRate * AvgWin) - (LossRate * AvgLoss)
    report.expectancy_dollars = (report.win_rate * report.avg_win_pnl) - (report.loss_rate * report.avg_loss_pnl)
    report.expectancy_r = float(np.mean(r_multiples)) if r_multiples else 0.0

    # Streaks
    report.max_consecutive_wins, report.max_consecutive_losses = _calculate_streaks(pnls)

    # Drawdown & ratios from equity curve
    if equity_curve is not None and len(equity_curve) > 1:
        eq = equity_curve.to_numpy(dtype=float)
        peaks = np.maximum.accumulate(eq)
        dd_dollars = peaks - eq
        dd_pct = dd_dollars / peaks

        report.max_drawdown_dollars = float(np.max(dd_dollars)) if len(dd_dollars) else 0.0
        report.max_drawdown_pct = float(np.max(dd_pct)) if len(dd_pct) else 0.0

        if report.max_drawdown_dollars > 0:
            report.recovery_factor = report.net_pnl / report.max_drawdown_dollars

        # Returns on equity curve for Sharpe & Sortino (daily resampled for institutional stability)
        if isinstance(equity_curve.index, pd.DatetimeIndex) and len(equity_curve.index.normalize().unique()) > 2:
            eq_daily = equity_curve.resample("1D").last().ffill().dropna()
            rets = eq_daily.pct_change().dropna().to_numpy()
            ann_factor = 252.0
        else:
            rets = np.diff(eq) / eq[:-1]
            ann_factor = annualization_factor

        mean_ret = np.mean(rets) if len(rets) else 0.0
        std_ret = np.std(rets) if len(rets) else 0.0

        if std_ret > 0:
            report.sharpe_ratio = float((mean_ret / std_ret) * np.sqrt(ann_factor))

        downside_rets = rets[rets < 0]
        downside_std = np.std(downside_rets) if len(downside_rets) else 0.0
        if downside_std > 0:
            report.sortino_ratio = float((mean_ret / downside_std) * np.sqrt(ann_factor))

    # Sub-group Breakdowns
    report.by_direction = _compute_group_breakdown(closed, key_func=lambda t: t.direction)
    report.by_setup_type = _compute_group_breakdown(
        closed, key_func=lambda t: t.signal.signal_type.value if hasattr(t.signal, "signal_type") else "unknown"
    )
    report.by_score_tier = _compute_group_breakdown(
        closed,
        key_func=lambda t: (
            "Score >= 75" if getattr(t.signal, "confluence_score", 0) >= 75
            else ("Score 60-74" if getattr(t.signal, "confluence_score", 0) >= 60 else "Score < 60")
        ),
    )

    return report


# ── Internal Calculation Helpers ──────────────────────────────────────────────

def _calculate_streaks(pnls: list[float]) -> tuple[int, int]:
    """Calculate maximum consecutive wins and losses."""
    max_wins = max_losses = 0
    cur_wins = cur_losses = 0

    for p in pnls:
        if p > 0:
            cur_wins += 1
            cur_losses = 0
            if cur_wins > max_wins:
                max_wins = cur_wins
        elif p < 0:
            cur_losses += 1
            cur_wins = 0
            if cur_losses > max_losses:
                max_losses = cur_losses
        else:
            cur_wins = 0
            cur_losses = 0

    return max_wins, max_losses


def _compute_group_breakdown(trades: list[TradeRecord], key_func) -> dict[str, BreakdownStats]:
    """Group trades by key and compute breakdown summary stats."""
    groups: dict[str, list[TradeRecord]] = {}
    for t in trades:
        k = str(key_func(t))
        groups.setdefault(k, []).append(t)

    breakdown: dict[str, BreakdownStats] = {}
    for k, group_trades in sorted(groups.items()):
        pnls = [float(t.pnl) for t in group_trades if t.pnl is not None]
        r_muls = [float(t.pnl_r) for t in group_trades if t.pnl_r is not None]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]

        gross_profit = sum(wins)
        gross_loss = sum(losses)
        pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

        breakdown[k] = BreakdownStats(
            count=len(group_trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=len(wins) / len(group_trades) if group_trades else 0.0,
            total_pnl=sum(pnls),
            avg_pnl=np.mean(pnls) if pnls else 0.0,
            avg_r=np.mean(r_muls) if r_muls else 0.0,
            profit_factor=pf,
        )

    return breakdown
