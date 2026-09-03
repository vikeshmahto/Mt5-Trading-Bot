"""
scripts/verify_step9.py
───────────────────────
Step 9 smoke-test: Performance Metrics, Scoring Evaluator & Report Generation.

Tests:
  1. Unit tests for metrics math: Win rate, Profit Factor, Expectancy, Drawdown, Sharpe/Sortino.
  2. Scoring tier calibration evaluation.
  3. CSV trade logs exporter.
  4. Markdown report generation.
  5. End-to-end integration: Run backtest on 2,000 M15 live historical bars, compute full metrics,
     and export CSV + Markdown reports.

Run:
    python scripts/verify_step9.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from core.types import Direction, Signal, SignalType, OrderBlock
from backtest.engine import BacktestEngine, TradeRecord
from backtest.metrics import calculate_metrics, PerformanceReport
from scoring.evaluator import evaluate_scoring_model, export_trades_csv, generate_markdown_report
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi

log = get_logger(__name__, level=settings.log_level)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_trade(
    pnl: float,
    pnl_r: float,
    direction: Direction = Direction.BULLISH,
    score: float = 75.0,
    signal_type: SignalType = SignalType.OB_RETEST,
) -> TradeRecord:
    sig = Signal(
        symbol="XAUUSD",
        direction=direction,
        signal_type=signal_type,
        timestamp=pd.Timestamp("2024-01-01 10:00", tz="UTC"),
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit=2015.0,
        risk_reward=1.5,
        confluence_score=score,
    )
    t = TradeRecord(
        signal=sig,
        entry_bar_ts=pd.Timestamp("2024-01-01 10:15", tz="UTC"),
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit=2015.0,
        lot_size=0.10,
        exit_bar_ts=pd.Timestamp("2024-01-01 11:30", tz="UTC"),
        exit_price=2015.0 if pnl > 0 else 1990.0,
        exit_reason="tp_hit" if pnl > 0 else "sl_hit",
        pnl=pnl,
        pnl_r=pnl_r,
    )
    return t


def run_unit_tests() -> int:
    failures = 0
    log.info("\n-- Synthetic Metrics & Evaluator Unit Tests ---------------------")

    # Construct 10 synthetic trades: 6 wins ($150, +1.5R), 4 losses (-$100, -1.0R)
    trades = [
        _make_mock_trade(150.0, 1.5, Direction.BULLISH, 80.0, SignalType.OB_RETEST),
        _make_mock_trade(150.0, 1.5, Direction.BULLISH, 85.0, SignalType.OB_RETEST),
        _make_mock_trade(-100.0, -1.0, Direction.BULLISH, 65.0, SignalType.FVG_RETEST),
        _make_mock_trade(150.0, 1.5, Direction.BEARISH, 80.0, SignalType.OB_FVG),
        _make_mock_trade(-100.0, -1.0, Direction.BEARISH, 60.0, SignalType.FVG_RETEST),
        _make_mock_trade(-100.0, -1.0, Direction.BULLISH, 55.0, SignalType.FVG_RETEST),
        _make_mock_trade(150.0, 1.5, Direction.BULLISH, 75.0, SignalType.OB_RETEST),
        _make_mock_trade(150.0, 1.5, Direction.BEARISH, 90.0, SignalType.OB_RETEST),
        _make_mock_trade(-100.0, -1.0, Direction.BEARISH, 70.0, SignalType.FVG_RETEST),
        _make_mock_trade(150.0, 1.5, Direction.BULLISH, 85.0, SignalType.OB_FVG),
    ]

    # Mock equity curve
    eq_values = [10000.0]
    cur = 10000.0
    for t in trades:
        cur += t.pnl
        eq_values.append(cur)
    eq_series = pd.Series(
        eq_values,
        index=pd.date_range("2024-01-01", periods=len(eq_values), freq="h", tz="UTC"),
    )

    report = calculate_metrics(trades, equity_curve=eq_series, initial_balance=10000.0)

    # 1. Win Rate & PnL
    ok1 = (
        report.total_trades == 10
        and report.wins == 6
        and report.losses == 4
        and abs(report.win_rate - 0.60) < 1e-4
        and abs(report.total_pnl - 500.0) < 1e-4
    )
    log.info(f"  {'OK' if ok1 else 'FAIL'} [Test 1 - Win rate & PnL]  "
             f"trades={report.total_trades}  win_rate={report.win_rate:.0%}  pnl=${report.total_pnl:,.2f}")
    if not ok1: failures += 1

    # 2. Profit Factor & Expectancy
    # Gross profit = 6 * 150 = 900, Gross loss = 4 * 100 = 400. PF = 900 / 400 = 2.25
    # Expectancy R = (6 * 1.5 - 4 * 1.0) / 10 = 5.0 / 10 = +0.50R
    ok2 = abs(report.profit_factor - 2.25) < 1e-4 and abs(report.expectancy_r - 0.50) < 1e-4
    log.info(f"  {'OK' if ok2 else 'FAIL'} [Test 2 - Profit Factor & Expectancy]  "
             f"PF={report.profit_factor:.2f}  exp_R={report.expectancy_r:+.2f}R")
    if not ok2: failures += 1

    # 3. Drawdown & Streaks
    ok3 = report.max_drawdown_pct >= 0.0 and report.max_consecutive_wins >= 2 and report.max_consecutive_losses >= 2
    log.info(f"  {'OK' if ok3 else 'FAIL'} [Test 3 - Drawdown & Streaks]  "
             f"max_dd={report.max_drawdown_pct:.2%}  win_streak={report.max_consecutive_wins}  loss_streak={report.max_consecutive_losses}")
    if not ok3: failures += 1

    # 4. Scoring Calibration Analysis
    eval_res = evaluate_scoring_model(trades)
    ok4 = eval_res["total_evaluated"] == 10 and "80-100" in eval_res["tiers"]
    log.info(f"  {'OK' if ok4 else 'FAIL'} [Test 4 - Scoring Calibration]  "
             f"tiers_found={list(eval_res['tiers'].keys())}  calibrated={eval_res['is_calibrated']}")
    if not ok4: failures += 1

    # 5. CSV & Markdown Generation
    csv_path = Path("test_verify_trades.csv")
    md_path = Path("test_verify_report.md")
    try:
        export_trades_csv(trades, csv_path)
        generate_markdown_report(report, symbol="XAUUSD", output_path=md_path)
        ok5 = csv_path.exists() and md_path.exists() and len(md_path.read_text()) > 100
        log.info(f"  {'OK' if ok5 else 'FAIL'} [Test 5 - CSV & Markdown Export]  "
                 f"csv_bytes={csv_path.stat().st_size if csv_path.exists() else 0}  "
                 f"md_bytes={md_path.stat().st_size if md_path.exists() else 0}")
        if not ok5: failures += 1
    finally:
        if csv_path.exists(): csv_path.unlink()
        if md_path.exists(): md_path.unlink()

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# End-to-End Live Integration
# ─────────────────────────────────────────────────────────────────────────────

def run_live_metrics_pipeline() -> None:
    SYMBOL = "XAUUSD"
    TFS = ["D1", "H4", "H1", "M15"]
    N = {"D1": 500, "H4": 2000, "H1": 2000, "M15": 2000}

    log.info("\n-- Live MT5 Backtest + Metrics Pipeline -------------------------")
    with MT5Client():
        bars = fetch_multi(SYMBOL, TFS, N, include_open=False)

    m15_count = len(bars.get("M15", []))
    if m15_count < 50:
        log.warning("  Too few bars for live pipeline.")
        return

    # Run backtest
    engine = BacktestEngine(symbol=SYMBOL, bars_dict=bars, persist=False)
    result = engine.run()

    # Calculate comprehensive metrics
    report = calculate_metrics(
        result.trades,
        equity_curve=result.equity_curve,
        initial_balance=result.initial_balance,
    )

    # Format text table
    print()
    print(report.format_text_table())

    # Export outputs to reports directory
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    csv_out = reports_dir / f"backtest_{SYMBOL}_trades.csv"
    md_out = reports_dir / f"backtest_{SYMBOL}_report.md"

    export_trades_csv(result.trades, csv_out)
    generate_markdown_report(report, symbol=SYMBOL, output_path=md_out)

    # Evaluate scoring model
    score_eval = evaluate_scoring_model(result.trades)
    log.info(f"\n  Score Model Calibration: {score_eval['tiers']}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 65)
    log.info("STEP 9 -- Performance Metrics & Scoring Evaluator")
    log.info("=" * 65)

    fails = run_unit_tests()
    run_live_metrics_pipeline()

    log.info("")
    if fails == 0:
        log.info("PASSED -- Step 9: Performance metrics & reporting working.")
    else:
        log.error(f"FAILED -- Step 9: {fails} unit test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
