"""
scripts/run_pristine_holdout_tests.py
─────────────────────────────────────
Executes backtests on 100% PRISTINE, UNTOUCHED holdout datasets across:
  1. XAUUSD Pristine Holdout (Spring 2026: March 2, 2026 → May 29, 2026: ~5,800 M15 bars)
  2. BTCUSD Pristine Holdout (Summer 2026: July 2, 2026 → Sept 2, 2026: ~6,000 M15 bars)
  3. EURUSD Pristine Holdout (Summer 2026: June 8, 2026 → Sept 2, 2026: ~6,000 M15 bars)

All automated invariant assertions are active.
Daily resampled Sharpe/Sortino and net commission accounting are reported.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.settings import settings
from core.logger import get_logger
from data.fetcher import fetch_bars
from data.mt5_client import MT5Client
from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from scoring.evaluator import export_trades_csv, generate_markdown_report, evaluate_scoring_model

log = get_logger(__name__)


def log_performance_summary(report, label: str):
    log.info("\n" + "=" * 68)
    log.info(f"PERFORMANCE REPORT: {label}")
    log.info("=" * 68)
    log.info("  Capital Overview:")
    log.info(f"    Initial Balance      : ${report.initial_balance:,.2f}")
    log.info(f"    Final Balance        : ${report.final_balance:,.2f}")
    log.info(f"    Gross Profit / Loss  : ${report.total_pnl:+,.2f}")
    log.info(f"    Total Commissions    : ${report.total_commission:,.2f}")
    log.info(f"    Net Profit / Loss    : ${report.net_pnl:+,.2f} ({report.return_pct:+.2%})")
    log.info("\n  Trade Statistics:")
    log.info(f"    Total Trades Closed  : {report.total_trades}")
    log.info(f"    Win / Loss Count     : {report.wins} Wins / {report.losses} Losses")
    log.info(f"    Win Rate             : {report.win_rate:.2%}")
    log.info(f"    Gross Profit         : ${report.gross_profit:,.2f}")
    log.info(f"    Gross Loss           : ${report.gross_loss:,.2f}")
    log.info(f"    Profit Factor        : {report.profit_factor:.2f}")
    log.info(f"    Avg Trade PnL        : ${report.avg_trade_pnl:+,.2f}")
    log.info(f"    Avg Win / Avg Loss   : ${report.avg_win_pnl:,.2f} / ${report.avg_loss_pnl:,.2f}")
    log.info(f"    Win/Loss PnL Ratio   : {report.win_loss_ratio:.2f}")
    log.info(f"    Expectancy per Trade : {report.expectancy_r:+.2f}R (${report.expectancy_dollars:+,.2f})")
    log.info("\n  Risk & Drawdown:")
    log.info(f"    Max Drawdown         : ${report.max_drawdown_dollars:,.2f} ({report.max_drawdown_pct:.2%})")
    log.info(f"    Recovery Factor      : {report.recovery_factor:.2f}")
    log.info(f"    Daily Sharpe (ann.)  : {report.sharpe_ratio:.2f}")
    log.info(f"    Daily Sortino (ann.) : {report.sortino_ratio:.2f}")
    log.info(f"    Max Win Streak       : {report.max_consecutive_wins}")
    log.info(f"    Max Loss Streak      : {report.max_consecutive_losses}")
    log.info("=" * 68)

    if report.by_direction:
        for d, s in report.by_direction.items():
            log.info(
                f"    {d.upper():8s} : {s.count:3d} trades | "
                f"WinRate: {s.win_rate*100:.1f}% | "
                f"PnL: $ {s.total_pnl:+8.2f} | "
                f"Avg R: {s.avg_r:+.2f}R | "
                f"PF: {s.profit_factor:.2f}"
            )

    if report.by_setup_type:
        log.info("\n  Breakdown by Setup Type:")
        for st, s in report.by_setup_type.items():
            log.info(
                f"    {st:12s} : {s.count:3d} trades | "
                f"WinRate: {s.win_rate*100:.1f}% | "
                f"PnL: $ {s.total_pnl:+8.2f} | "
                f"Avg R: {s.avg_r:+.2f}R | "
                f"PF: {s.profit_factor:.2f}"
            )


def run_holdout_test(
    symbol: str,
    start_date: str,
    end_date: str,
    label: str,
    report_prefix: str,
    n_bars: int = 15000,
):
    inst_config = settings.get_instrument(symbol)
    risk_config = settings.risk

    log.info("=" * 68)
    log.info(f">>> FETCHING DATA FOR {symbol} [{label}] ({start_date} to {end_date})")
    log.info("=" * 68)

    all_tfs = ["D1", "H4", "H1", "M15"]
    os.makedirs("data/cache", exist_ok=True)

    bars_dict: dict[str, pd.DataFrame] = {}
    missing_tfs = []
    for tf in all_tfs:
        cache_file = f"data/cache/{symbol}_{tf}.parquet"
        if os.path.exists(cache_file):
            bars_dict[tf] = pd.read_parquet(cache_file)
        else:
            missing_tfs.append(tf)

    if missing_tfs:
        with MT5Client():
            for tf in missing_tfs:
                df = fetch_bars(symbol, tf, n_bars, include_open=False)
                if not df.empty:
                    df.to_parquet(f"data/cache/{symbol}_{tf}.parquet")
                    bars_dict[tf] = df
                else:
                    log.warning(f"Could not fetch {tf} bars for {symbol}")

    # Slice execution timeframe (M15) to exact target holdout range
    m15_full = bars_dict["M15"]
    m15_sliced = m15_full.loc[start_date:end_date]
    if m15_sliced.empty:
        raise ValueError(f"No M15 bars in range {start_date} to {end_date}")

    log.info(
        f"[{symbol}] {label} slice: {len(m15_sliced)} bars | "
        f"{m15_sliced.index[0]} → {m15_sliced.index[-1]}"
    )

    engine = BacktestEngine(
        symbol=symbol,
        bars_dict=bars_dict,
        instrument_config=inst_config,
        risk_config=risk_config,
        start_date=start_date,
        end_date=end_date,
    )

    result = engine.run()
    metrics = calculate_metrics(
        trades=result.trades,
        equity_curve=result.equity_curve,
        initial_balance=risk_config.backtest.initial_balance,
    )
    log_performance_summary(metrics, label)

    # Scoring telemetry evaluation
    scoring_eval = evaluate_scoring_model(result.trades)
    log.info(f"\n[{label}] Confluence Score Tiers Breakdown:")
    for tier, data in scoring_eval.get("tiers", {}).items():
        log.info(
            f"  {tier:8s} -> {data['count']:3d} trades | "
            f"WinRate: {data['win_rate']*100:.1f}% | "
            f"Avg R: {data['avg_r']:+.2f}R | "
            f"PnL: $ {data['total_pnl']:+8.2f}"
        )

    # Export artifacts
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = reports_dir / f"{report_prefix}_{symbol}_trades.csv"
    md_path = reports_dir / f"{report_prefix}_{symbol}_report.md"

    export_trades_csv(result.trades, csv_path)
    generate_markdown_report(metrics, md_path)

    return result, metrics, scoring_eval


def main():
    results = {}

    # 1. XAUUSD Pristine Holdout (Spring 2026: March 2 → May 29, 2026)
    results["XAUUSD_pristine"] = run_holdout_test(
        symbol="XAUUSD",
        start_date="2026-03-02",
        end_date="2026-05-29",
        label="XAUUSD PRISTINE HOLDOUT (SPRING 2026)",
        report_prefix="pristine_holdout_spring2026",
        n_bars=20000,
    )

    # 2. BTCUSD Pristine Holdout (Summer 2026: July 2 → Sept 2, 2026)
    results["BTCUSD_pristine"] = run_holdout_test(
        symbol="BTCUSD",
        start_date="2026-07-02",
        end_date="2026-09-02",
        label="BTCUSD PRISTINE HOLDOUT",
        report_prefix="pristine_holdout",
        n_bars=10000,
    )

    # 3. EURUSD Pristine Holdout (Summer 2026: June 8 → Sept 2, 2026)
    results["EURUSD_pristine"] = run_holdout_test(
        symbol="EURUSD",
        start_date="2026-06-08",
        end_date="2026-09-02",
        label="EURUSD PRISTINE HOLDOUT",
        report_prefix="pristine_holdout",
        n_bars=10000,
    )

    log.info("\n" + "=" * 68)
    log.info("ALL PRISTINE HOLDOUT TESTS COMPLETED SUCCESSFULLY!")
    log.info("=" * 68)


if __name__ == "__main__":
    main()
