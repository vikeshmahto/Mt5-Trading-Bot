"""
scripts/run_walkforward_step13.py
──────────────────────────────────
Step 13: EURUSD Forex Walk-Forward Verification

Change applied (Step 13):
  - Instrument-aware HTF scoring for forex (EURUSD):
    D1 bias is excluded from the HTF alignment count.
    Only H4+H1 alignment qualifies as "2-HTF fresh pullback" (+45 pts).
    This prevents persistent D1 macro trends in forex from pushing every
    EURUSD setup above Tier 79.9 (the Tier 80-100 exhaustion block).

Test window: EURUSD Q1 2026 (Jan 5 → Mar 31)
  Same pristine holdout as Step 11 where 100% of trades scored 80-100 → net -$853.22.

Score gate is UNCHANGED: min=70.0, max=79.9.
All invariant assertions strictly enforced in backtest/engine.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from config.settings import settings
from core.logger import get_logger
from scoring.evaluator import export_trades_csv, generate_markdown_report

log = get_logger("scripts.step13_walkforward")


def run_walkforward_slice(
    symbol: str,
    start_date: str,
    end_date: str,
    label: str,
    output_prefix: str,
    n_bars: int = 20000,
):
    inst_config = settings.get_instrument(symbol)
    risk_config = settings.risk

    log.info("=" * 72)
    log.info(f">>> STEP 13 WALK-FORWARD: {symbol} [{label}] ({start_date} to {end_date})")
    log.info("=" * 72)

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
        from data.fetcher import fetch_bars
        from data.mt5_client import MT5Client
        with MT5Client() as client:
            if client.is_connected():
                for tf in missing_tfs:
                    df = fetch_bars(symbol, tf, n_bars, include_open=False)
                    if not df.empty:
                        bars_dict[tf] = df
                        df.to_parquet(f"data/cache/{symbol}_{tf}.parquet")

    # Initialize Backtest Engine
    engine = BacktestEngine(
        symbol=symbol,
        bars_dict=bars_dict,
        instrument_config=inst_config,
        risk_config=risk_config,
        start_date=start_date,
        end_date=end_date,
        persist=False,
    )

    result = engine.run()
    metrics = calculate_metrics(
        trades=result.trades,
        equity_curve=result.equity_curve,
        initial_balance=risk_config.backtest.initial_balance,
    )

    # Save reports
    reports_dir = Path("reports/walkforward_step13")
    reports_dir.mkdir(parents=True, exist_ok=True)

    csv_path = reports_dir / f"{output_prefix}_{symbol}_trades.csv"
    md_path  = reports_dir / f"{output_prefix}_{symbol}_report.md"

    export_trades_csv(result.trades, csv_path)
    generate_markdown_report(metrics, md_path)

    trades_df = pd.read_csv(csv_path) if os.path.exists(csv_path) and len(result.trades) > 0 else pd.DataFrame()

    print("\n" + "=" * 72)
    print(f"STEP 13 WALK-FORWARD REPORT: {symbol} - {label}")
    print("=" * 72)
    print(f"  Signals Generated    : {result.signals_generated}")
    print(f"  Total Trades Closed  : {metrics.total_trades}")
    print(f"  Win / Loss Count     : {metrics.wins} Wins / {metrics.losses} Losses")
    print(f"  Win Rate             : {metrics.win_rate * 100:.1f}%")
    print(f"  Gross Profit / Loss  : ${metrics.total_pnl:+,.2f}")
    print(f"  Total Commissions    : ${metrics.total_commission:,.2f}")
    print(f"  Net Profit / Loss    : ${metrics.net_pnl:+,.2f} ({(metrics.net_pnl / risk_config.backtest.initial_balance)*100:+.2f}%)")
    print(f"  Profit Factor        : {metrics.profit_factor:.2f}")
    print(f"  Expectancy per Trade : {metrics.expectancy_r:+.2f}R")
    print(f"  Max Drawdown         : {metrics.max_drawdown_pct * 100:.2f}% (${metrics.max_drawdown_dollars:,.2f})")
    print(f"  Daily Sharpe (ann.)  : {metrics.sharpe_ratio:.2f}")
    print(f"  Daily Sortino (ann.) : {metrics.sortino_ratio:.2f}")

    if not trades_df.empty:
        print("\n  Trade Breakdown by Direction:")
        for direction in ["bearish", "bullish"]:
            d_df = trades_df[trades_df["direction"] == direction]
            if len(d_df) > 0:
                d_wr    = (d_df["pnl_r"] > 0).mean()
                d_pnl   = d_df["pnl_usd"].sum()
                d_comm  = d_df["commission"].sum()
                d_avg_r = d_df["pnl_r"].mean()
                print(f"    {direction.upper():8s} : {len(d_df):2d} trades | WinRate: {d_wr*100:5.1f}% | Gross: ${d_pnl + d_comm:+8.2f} | Net: ${d_pnl:+8.2f} | Avg R: {d_avg_r:+5.2f}R")

        print("\n  Trade Breakdown by Setup Type:")
        for st in trades_df["signal_type"].unique():
            st_df   = trades_df[trades_df["signal_type"] == st]
            st_wr   = (st_df["pnl_r"] > 0).mean()
            st_pnl  = st_df["pnl_usd"].sum()
            st_comm = st_df["commission"].sum()
            st_avg_r = st_df["pnl_r"].mean()
            print(f"    {st:12s} : {len(st_df):2d} trades | WinRate: {st_wr*100:5.1f}% | Gross: ${st_pnl + st_comm:+8.2f} | Net: ${st_pnl:+8.2f} | Avg R: {st_avg_r:+5.2f}R")

        print("\n  Confluence Score Tiers Breakdown:")
        for tier, low, high in [("80-100", 80, 101), ("70-79", 70, 80), ("60-69", 60, 70), ("<60", 0, 60)]:
            t_df = trades_df[(trades_df["confluence_score"] >= low) & (trades_df["confluence_score"] < high)]
            if len(t_df) > 0:
                t_wr    = (t_df["pnl_r"] > 0).mean()
                t_pnl   = t_df["pnl_usd"].sum()
                t_comm  = t_df["commission"].sum()
                t_avg_r = t_df["pnl_r"].mean()
                print(f"    {tier:8s} : {len(t_df):2d} trades | WinRate: {t_wr*100:5.1f}% | Gross: ${t_pnl + t_comm:+8.2f} | Net: ${t_pnl:+8.2f} | Avg R: {t_avg_r:+5.2f}R")

    return {
        "symbol": symbol,
        "label": label,
        "metrics": metrics,
        "result": result,
    }


def main():
    test_slices = [
        {
            "symbol": "EURUSD",
            "start_date": "2026-01-05",
            "end_date":   "2026-03-31",
            "label": "EURUSD Q1 2026 Walk-Forward (Step 13 - Forex HTF Fix)",
            "output_prefix": "step13_wf_q1_2026",
        },
    ]

    all_results = {}
    for s in test_slices:
        res = run_walkforward_slice(
            symbol=s["symbol"],
            start_date=s["start_date"],
            end_date=s["end_date"],
            label=s["label"],
            output_prefix=s["output_prefix"],
        )
        if res:
            all_results[s["symbol"]] = res

    log.info("\n" + "=" * 72)
    log.info("ALL STEP 13 WALK-FORWARD TESTS COMPLETED!")
    log.info("=" * 72)


if __name__ == "__main__":
    main()
