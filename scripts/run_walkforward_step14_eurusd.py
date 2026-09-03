"""
scripts/run_walkforward_step14_eurusd.py
─────────────────────────────────────────
Step 14: EURUSD Multi-Period Validation of H4+H1-Only Forex Rule

Tests the Step 13 forex HTF fix across 3 distinct periods to answer:
  Q1: Does the H4+H1-only rule EVER fire (generate any signals)?
  Q2: If it fires, are those trades profitable?
  Q3: If it NEVER fires across all periods, the rule is "dead" — EURUSD
      is untradeable by this system and should be excluded from live trading.

Test Windows (all within available M15 data: 2025-11-13 to 2026-09-03):
  Period A: 2025-11-13 → 2025-12-31  (Pre-Q1, ~7 weeks)
  Period B: 2026-01-05 → 2026-03-31  (Q1 2026 — same as Step 13, expect 0)
  Period C: 2026-04-01 → 2026-06-30  (Q2 2026 — fresh, untested)
  Period D: 2026-07-01 → 2026-08-31  (Summer 2026 — most recent)

All Step 8-13 filters remain active.
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

log = get_logger("scripts.step14_eurusd")


def run_walkforward_slice(
    symbol: str,
    start_date: str,
    end_date: str,
    label: str,
    output_prefix: str,
):
    inst_config = settings.get_instrument(symbol)
    risk_config = settings.risk

    log.info("=" * 72)
    log.info(f">>> STEP 14: {symbol} [{label}] ({start_date} to {end_date})")
    log.info("=" * 72)

    all_tfs = ["D1", "H4", "H1", "M15"]
    bars_dict: dict[str, pd.DataFrame] = {}

    for tf in all_tfs:
        cache_file = f"data/cache/{symbol}_{tf}.parquet"
        if os.path.exists(cache_file):
            bars_dict[tf] = pd.read_parquet(cache_file)
        else:
            log.warning(f"Missing cache: {cache_file} — skipping period")
            return None

    # Check M15 data covers the period
    m15_check = bars_dict["M15"].loc[start_date:end_date]
    if len(m15_check) < 50:
        log.warning(f"Insufficient M15 data for {start_date}–{end_date} ({len(m15_check)} bars) — skipping")
        return None

    log.info(f"[{symbol}] M15 bars in window: {len(m15_check)}")

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

    reports_dir = Path("reports/walkforward_step14")
    reports_dir.mkdir(parents=True, exist_ok=True)

    csv_path = reports_dir / f"{output_prefix}_{symbol}_trades.csv"
    md_path  = reports_dir / f"{output_prefix}_{symbol}_report.md"

    export_trades_csv(result.trades, csv_path)
    generate_markdown_report(metrics, md_path)

    trades_df = pd.read_csv(csv_path) if os.path.exists(csv_path) and len(result.trades) > 0 else pd.DataFrame()

    print("\n" + "=" * 72)
    print(f"STEP 14 REPORT: {label}")
    print("=" * 72)
    print(f"  Signals Generated : {result.signals_generated}")
    print(f"  Trades Closed     : {metrics.total_trades}")

    if metrics.total_trades == 0:
        print("  *** NO SIGNALS FIRED — H4+H1 rule did not activate in this period ***")
    else:
        wins   = metrics.wins
        losses = metrics.losses
        print(f"  Win / Loss        : {wins} / {losses}")
        print(f"  Win Rate          : {metrics.win_rate * 100:.1f}%")
        print(f"  Gross PnL         : ${metrics.total_pnl:+,.2f}")
        print(f"  Total Commission  : ${metrics.total_commission:,.2f}")
        print(f"  Net PnL           : ${metrics.net_pnl:+,.2f} ({(metrics.net_pnl / risk_config.backtest.initial_balance)*100:+.2f}%)")
        print(f"  Expectancy        : {metrics.expectancy_r:+.2f}R")
        print(f"  Max Drawdown      : {metrics.max_drawdown_pct * 100:.2f}%")
        print(f"  Sharpe            : {metrics.sharpe_ratio:.2f}")

        if not trades_df.empty:
            print("\n  Score Tier Breakdown:")
            for tier, lo, hi in [("80-100", 80, 101), ("70-79", 70, 80), ("<70", 0, 70)]:
                t = trades_df[(trades_df["confluence_score"] >= lo) & (trades_df["confluence_score"] < hi)]
                if len(t) > 0:
                    wr = (t["pnl_r"] > 0).mean()
                    print(f"    {tier:8s}: {len(t):3d} trades | WinRate: {wr*100:5.1f}% | Net: ${t['pnl_usd'].sum():+,.2f} | Avg R: {t['pnl_r'].mean():+.2f}R")

            print("\n  Setup Type Breakdown:")
            for st in trades_df["signal_type"].unique():
                t = trades_df[trades_df["signal_type"] == st]
                wr = (t["pnl_r"] > 0).mean()
                print(f"    {st:12s}: {len(t):3d} trades | WinRate: {wr*100:5.1f}% | Net: ${t['pnl_usd'].sum():+,.2f} | Avg R: {t['pnl_r'].mean():+.2f}R")

    return {
        "label": label,
        "signals": result.signals_generated,
        "trades": metrics.total_trades,
        "net_pnl": metrics.net_pnl,
        "expectancy": metrics.expectancy_r,
        "win_rate": metrics.win_rate,
        "max_dd": metrics.max_drawdown_pct,
    }


def main():
    test_periods = [
        {
            "start": "2025-11-13",
            "end":   "2025-12-31",
            "label": "EURUSD Period A: Nov-Dec 2025 (Pre-Q1)",
            "prefix": "step14_periodA",
        },
        {
            "start": "2026-01-05",
            "end":   "2026-03-31",
            "label": "EURUSD Period B: Q1 2026 (Same as Step 13 baseline)",
            "prefix": "step14_periodB",
        },
        {
            "start": "2026-04-01",
            "end":   "2026-06-30",
            "label": "EURUSD Period C: Q2 2026 (Fresh, untested)",
            "prefix": "step14_periodC",
        },
        {
            "start": "2026-07-01",
            "end":   "2026-08-31",
            "label": "EURUSD Period D: Summer 2026 (Most recent)",
            "prefix": "step14_periodD",
        },
    ]

    summary = []
    for p in test_periods:
        result = run_walkforward_slice(
            symbol="EURUSD",
            start_date=p["start"],
            end_date=p["end"],
            label=p["label"],
            output_prefix=p["prefix"],
        )
        if result:
            summary.append(result)

    print("\n\n" + "=" * 72)
    print("STEP 14 FINAL SUMMARY — EURUSD H4+H1 Rule Multi-Period Validation")
    print("=" * 72)
    print(f"{'Period':<50} {'Signals':>8} {'Trades':>7} {'Net PnL':>10} {'Expect':>8} {'MaxDD':>7}")
    print("-" * 72)
    total_signals = 0
    for r in summary:
        total_signals += r["signals"]
        net_str = f"${r['net_pnl']:+,.2f}" if r["trades"] > 0 else "N/A"
        exp_str = f"{r['expectancy']:+.2f}R" if r["trades"] > 0 else "N/A"
        dd_str  = f"{r['max_dd']*100:.1f}%" if r["trades"] > 0 else "N/A"
        print(f"{r['label'][:50]:<50} {r['signals']:>8} {r['trades']:>7} {net_str:>10} {exp_str:>8} {dd_str:>7}")

    print("-" * 72)
    print()
    if total_signals == 0:
        print("VERDICT: H4+H1 rule NEVER FIRED across all 4 EURUSD periods.")
        print("=> This is a DEAD RULE. EURUSD should be EXCLUDED from live trading")
        print("   until a period is found where genuine H4+H1 confluence exists.")
    else:
        fired_periods = [r for r in summary if r["signals"] > 0]
        profitable = [r for r in fired_periods if r["net_pnl"] > 0]
        print(f"VERDICT: H4+H1 rule fired in {len(fired_periods)}/4 periods.")
        print(f"  Profitable: {len(profitable)}/{len(fired_periods)} of periods where it fired.")

    log.info("Step 14 complete.")


if __name__ == "__main__":
    main()
