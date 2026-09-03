"""
scripts/run_walkforward_split.py
────────────────────────────────
Executes Walk-Forward Backtest with 70/30 In-Sample & Out-of-Sample Split.

Dataset: 6,000+ M15 bars spanning multiple market regimes.
Evaluates:
  • Long vs Short trade performance
  • Setup type breakdown (OB vs FVG vs Sweep vs Combo)
  • Confluence Score calibration (>=75 vs <75) on both In-Sample and Out-of-Sample
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from scoring.evaluator import export_trades_csv, generate_markdown_report, evaluate_scoring_model
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi

log = get_logger(__name__, level=settings.log_level)


def run_split_backtest() -> None:
    SYMBOL = "XAUUSD"
    TFS = ["D1", "H4", "H1", "M15"]
    N = {"D1": 1000, "H4": 4000, "H1": 5000, "M15": 6000}

    log.info("=" * 65)
    log.info("WALK-FORWARD TRAIN / TEST SPLIT BACKTEST (XAUUSD)")
    log.info("=" * 65)

    with MT5Client():
        bars = fetch_multi(SYMBOL, TFS, N, include_open=False)

    m15_df = bars.get("M15", pd.DataFrame())
    total_bars = len(m15_df)
    log.info(f"Total M15 bars fetched: {total_bars:,} (Range: {m15_df.index[0].date()} to {m15_df.index[-1].date()})")

    if total_bars < 500:
        log.error("Insufficient bars for train/test split.")
        return

    # 70 / 30 Chronological Split
    split_idx = int(total_bars * 0.70)
    split_timestamp = m15_df.index[split_idx]

    log.info(f"In-Sample Split (70%):  {m15_df.index[0].date()} -> {split_timestamp.date()} ({split_idx:,} bars)")
    log.info(f"Out-of-Sample (30%):    {split_timestamp.date()} -> {m15_df.index[-1].date()} ({total_bars - split_idx:,} bars)")

    # ── 1. IN-SAMPLE BACKTEST (70%) ───────────────────────────────────────────
    log.info("\n=================================================================")
    log.info(">>> RUNNING IN-SAMPLE BACKTEST (TRAIN 70%)")
    log.info("=================================================================")

    in_sample_bars = {
        tf: df[df.index <= split_timestamp].copy()
        for tf, df in bars.items()
    }

    engine_is = BacktestEngine(symbol=SYMBOL, bars_dict=in_sample_bars, persist=False)
    result_is = engine_is.run()
    report_is = calculate_metrics(result_is.trades, result_is.equity_curve, initial_balance=result_is.initial_balance)

    print()
    print("IN-SAMPLE PERFORMANCE REPORT:")
    print(report_is.format_text_table())

    # Export In-Sample reports
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    export_trades_csv(result_is.trades, reports_dir / f"in_sample_{SYMBOL}_trades.csv")
    generate_markdown_report(report_is, symbol=f"{SYMBOL} (In-Sample)", output_path=reports_dir / f"in_sample_{SYMBOL}_report.md")

    # ── 2. OUT-OF-SAMPLE BACKTEST (30%) ───────────────────────────────────────
    log.info("\n=================================================================")
    log.info(">>> RUNNING OUT-OF-SAMPLE BACKTEST (TEST 30% - UNSEEN)")
    log.info("=================================================================")

    # For out-of-sample, we start execution at split_timestamp
    engine_oos = BacktestEngine(
        symbol=SYMBOL,
        bars_dict=bars,
        start_date=split_timestamp,
        persist=False,
    )
    result_oos = engine_oos.run()
    report_oos = calculate_metrics(result_oos.trades, result_oos.equity_curve, initial_balance=result_oos.initial_balance)

    print()
    print("OUT-OF-SAMPLE PERFORMANCE REPORT:")
    print(report_oos.format_text_table())

    # Export Out-of-Sample reports
    export_trades_csv(result_oos.trades, reports_dir / f"out_of_sample_{SYMBOL}_trades.csv")
    generate_markdown_report(report_oos, symbol=f"{SYMBOL} (Out-of-Sample)", output_path=reports_dir / f"out_of_sample_{SYMBOL}_report.md")

    # ── 3. COMPARISON & CALIBRATION SUMMARY ───────────────────────────────────
    log.info("\n" + "=" * 65)
    log.info("STRATEGY SUMMARY & SCORING CALIBRATION COMPARISON")
    log.info("=" * 65)

    eval_is = evaluate_scoring_model(result_is.trades)
    eval_oos = evaluate_scoring_model(result_oos.trades)

    log.info("\n[IN-SAMPLE] Score Tiers:")
    for tier, data in eval_is["tiers"].items():
        log.info(f"  {tier:8s} -> {data['count']:3d} trades | WinRate: {data['win_rate']:.1%} | Avg R: {data['avg_r']:+.2f}R | PnL: ${data['total_pnl']:+8.2f}")

    log.info("\n[OUT-OF-SAMPLE] Score Tiers:")
    for tier, data in eval_oos["tiers"].items():
        log.info(f"  {tier:8s} -> {data['count']:3d} trades | WinRate: {data['win_rate']:.1%} | Avg R: {data['avg_r']:+.2f}R | PnL: ${data['total_pnl']:+8.2f}")


if __name__ == "__main__":
    run_split_backtest()
