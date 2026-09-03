"""
scoring/evaluator.py
───────────────────
Signal Quality Evaluator & Report Generator.

Analyzes the correlation between SMC Confluence Scores and trade profitability,
evaluates strategy edge, and generates detailed Markdown / CSV exports.

Public API:
  evaluate_scoring_model(trades: list[TradeRecord]) -> dict[str, Any]
  export_trades_csv(trades: list[TradeRecord], output_path: str | Path) -> Path
  generate_markdown_report(report: PerformanceReport, output_path: Optional[str | Path]) -> str
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from backtest.engine import TradeRecord
from backtest.metrics import PerformanceReport, calculate_metrics
from core.logger import get_logger

log = get_logger(__name__)


def evaluate_scoring_model(trades: list[TradeRecord]) -> dict[str, Any]:
    """
    Evaluate if higher confluence scores correlate with higher win rate and PnL.
    
    Returns tier-by-tier metrics and a calibration score.
    """
    closed = [t for t in trades if t.exit_price is not None and t.pnl is not None]
    if not closed:
        return {"total_evaluated": 0, "tiers": {}, "is_calibrated": False}

    # Group into score brackets: [50-59, 60-69, 70-79, 80-89, 90-100]
    brackets = {
        "80-100": [t for t in closed if getattr(t.signal, "confluence_score", 0) >= 80],
        "70-79":  [t for t in closed if 70 <= getattr(t.signal, "confluence_score", 0) < 80],
        "60-69":  [t for t in closed if 60 <= getattr(t.signal, "confluence_score", 0) < 70],
        "<60":    [t for t in closed if getattr(t.signal, "confluence_score", 0) < 60],
    }

    tier_results = {}
    win_rates = []

    for name, b_trades in brackets.items():
        if not b_trades:
            continue
        wins = [t for t in b_trades if (t.pnl or 0) > 0]
        r_vals = [t.pnl_r for t in b_trades if t.pnl_r is not None]
        pnls = [t.pnl for t in b_trades if t.pnl is not None]
        wr = len(wins) / len(b_trades)
        win_rates.append(wr)

        tier_results[name] = {
            "count": len(b_trades),
            "wins": len(wins),
            "win_rate": round(wr, 4),
            "avg_r": round(float(np.mean(r_vals)), 2) if r_vals else 0.0,
            "total_pnl": round(float(np.sum(pnls)), 2) if pnls else 0.0,
        }

    # Calibration: monotonic trend check (higher score tier should generally have >= win rate)
    is_calibrated = True
    if len(win_rates) >= 2:
        # Check if first non-empty tier (highest score) >= last non-empty tier
        is_calibrated = win_rates[0] >= win_rates[-1]

    return {
        "total_evaluated": len(closed),
        "tiers": tier_results,
        "is_calibrated": is_calibrated,
    }


def export_trades_csv(trades: list[TradeRecord], output_path: str | Path) -> Path:
    """Export trade records to a clean CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for idx, t in enumerate(trades, 1):
        rows.append({
            "trade_no": idx,
            "symbol": t.signal.symbol if t.signal else "",
            "direction": t.direction,
            "signal_type": t.signal.signal_type.value if hasattr(t.signal, "signal_type") else "",
            "confluence_score": getattr(t.signal, "confluence_score", 0),
            "entry_time": t.entry_bar_ts,
            "entry_price": t.entry_price,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "lot_size": t.lot_size,
            "exit_time": t.exit_bar_ts,
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason,
            "pnl_usd": t.pnl,
            "pnl_r": t.pnl_r,
            "commission": t.commission,
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    log.info(f"Exported {len(rows)} trades to {path}")
    return path


def generate_markdown_report(
    report: PerformanceReport,
    symbol: str = "XAUUSD",
    output_path: Optional[str | Path] = None,
) -> str:
    """Generate a clean GitHub-Flavored Markdown summary report."""
    md_lines = [
        f"# Performance Report — {symbol}",
        "",
        f"**Generated:** {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Initial Capital:** `${report.initial_balance:,.2f}` | **Final Balance:** `${report.final_balance:,.2f}` | **Net Return:** `{report.return_pct:+.2%}`",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric | Value | Metric | Value |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Total Trades** | `{report.total_trades}` | **Win Rate** | `{report.win_rate:.2%}` |",
        f"| **Wins / Losses** | `{report.wins}W / {report.losses}L` | **Profit Factor** | `{report.profit_factor:.2f}` |",
        f"| **Gross Profit** | `${report.total_pnl:+,.2f}` | **Total Commissions** | `${report.total_commission:,.2f}` |",
        f"| **Net Profit** | `${report.net_pnl:+,.2f}` | **Expectancy (R)** | `{report.expectancy_r:+.2f}R` |",
        f"| **Max Drawdown (%)** | `{report.max_drawdown_pct:.2%}` | **Max Drawdown ($)** | `${report.max_drawdown_dollars:,.2f}` |",
        f"| **Sharpe Ratio** | `{report.sharpe_ratio:.2f}` | **Sortino Ratio** | `{report.sortino_ratio:.2f}` |",
        f"| **Max Win Streak** | `{report.max_consecutive_wins}` | **Max Loss Streak** | `{report.max_consecutive_losses}` |",
        "",
        "## 2. Trade Breakdown by Direction",
        "",
        "| Direction | Trades | Win Rate | Total P&L | Avg R | Profit Factor |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for d_name, s in report.by_direction.items():
        md_lines.append(
            f"| **{d_name.upper()}** | `{s.count}` | `{s.win_rate:.1%}` | `${s.total_pnl:+,.2f}` | `{s.avg_r:+.2f}R` | `{s.profit_factor:.2f}` |"
        )

    if report.by_setup_type:
        md_lines.extend([
            "",
            "## 3. Trade Breakdown by Setup Type",
            "",
            "| Setup Type | Trades | Win Rate | Total P&L | Avg R | Profit Factor |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for s_name, s in report.by_setup_type.items():
            md_lines.append(
                f"| `{s_name}` | `{s.count}` | `{s.win_rate:.1%}` | `${s.total_pnl:+,.2f}` | `{s.avg_r:+.2f}R` | `{s.profit_factor:.2f}` |"
            )

    if report.by_score_tier:
        md_lines.extend([
            "",
            "## 4. Confluence Score Calibration",
            "",
            "| Score Tier | Trades | Win Rate | Total P&L | Avg R |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for tier, s in report.by_score_tier.items():
            md_lines.append(
                f"| `{tier}` | `{s.count}` | `{s.win_rate:.1%}` | `${s.total_pnl:+,.2f}` | `{s.avg_r:+.2f}R` |"
            )

    content = "\n".join(md_lines)

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
        log.info(f"Markdown report written to {out_p}")

    return content
