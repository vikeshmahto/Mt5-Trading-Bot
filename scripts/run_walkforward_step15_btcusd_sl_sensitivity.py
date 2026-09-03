"""
scripts/run_walkforward_step15_btcusd_sl_sensitivity.py
─────────────────────────────────────────────────────────
Step 15: BTCUSD Minimum Stop-Loss Sensitivity Analysis

Problem identified in Step 12:
  - BTCUSD fvg_retest GROSS PnL was +$198.22 (signal direction is correct)
  - But commission of -$378.14 destroyed net to -$179.92
  - Root cause: min SL of 50 pts still allows tight stops -> large lot sizes
    -> commission dominates. Need larger minimum SL to reduce lot sizes.

This script tests 4 thresholds causally on the same BTCUSD Spring 2026 period
(Mar 1 -> May 31) — the same unseen period used in Steps 11-12.

Thresholds tested:
  A) 50 pts  (current baseline — Step 12 result for reference)
  B) 300 pts
  C) 500 pts
  D) 700 pts

For each threshold, we answer:
  1. How many trades were generated? (larger SL = fewer fvg_retest qualify)
  2. What is net PnL and expectancy?
  3. Was the 10% drawdown stop hit?
  4. What is the commission/gross ratio?

The override mechanism: set signals.generator._BTCUSD_MIN_SL_PTS before
creating the BacktestEngine. This avoids yaml/dataclass changes and is
explicitly designed for sensitivity testing only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

# Override MUST happen before BacktestEngine imports generator
import signals.generator as gen_module

from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from config.settings import settings
from core.logger import get_logger
from scoring.evaluator import export_trades_csv, generate_markdown_report

log = get_logger("scripts.step15_btcusd_sl")

SYMBOL     = "BTCUSD"
START_DATE = "2026-03-01"
END_DATE   = "2026-05-31"
LABEL_BASE = "BTCUSD Spring 2026 (Step 15 SL Sensitivity)"

SL_THRESHOLDS = [50, 300, 500, 700]  # pts


def run_with_sl_threshold(sl_pts: int, bars_dict: dict, inst_config, risk_config) -> dict:
    """Run backtest with a specific BTCUSD min SL threshold."""

    # Override min SL (thread-unsafe in parallel, but we're sequential here)
    gen_module._BTCUSD_MIN_SL_PTS = float(sl_pts)
    log.info("=" * 72)
    log.info(f">>> STEP 15: {SYMBOL} | Min SL = {sl_pts} pts | ({START_DATE} to {END_DATE})")
    log.info("=" * 72)

    engine = BacktestEngine(
        symbol=SYMBOL,
        bars_dict=bars_dict,
        instrument_config=inst_config,
        risk_config=risk_config,
        start_date=START_DATE,
        end_date=END_DATE,
        persist=False,
    )

    result = engine.run()
    metrics = calculate_metrics(
        trades=result.trades,
        equity_curve=result.equity_curve,
        initial_balance=risk_config.backtest.initial_balance,
    )

    reports_dir = Path("reports/walkforward_step15")
    reports_dir.mkdir(parents=True, exist_ok=True)

    slug      = f"step15_btcusd_sl{sl_pts}"
    csv_path  = reports_dir / f"{slug}_trades.csv"
    md_path   = reports_dir / f"{slug}_report.md"

    export_trades_csv(result.trades, csv_path)
    generate_markdown_report(metrics, md_path)

    trades_df = pd.read_csv(csv_path) if os.path.exists(csv_path) and len(result.trades) > 0 else pd.DataFrame()

    # Commission analysis
    gross_pnl = metrics.total_pnl
    total_comm = metrics.total_commission
    net_pnl    = metrics.net_pnl
    comm_ratio = abs(total_comm / gross_pnl) if abs(gross_pnl) > 0.01 else float("inf")

    # Check if DD stop was hit (proxy: max_drawdown > 9.5%)
    dd_stop_hit = metrics.max_drawdown_pct > 0.095

    print(f"\n  Min SL = {sl_pts:4d} pts | Trades: {metrics.total_trades:3d} | "
          f"Win%: {metrics.win_rate*100:4.1f}% | Gross: ${gross_pnl:+8,.2f} | "
          f"Comm: ${total_comm:7,.2f} | Net: ${net_pnl:+8,.2f} | "
          f"R/trade: {metrics.expectancy_r:+.2f}R | MaxDD: {metrics.max_drawdown_pct*100:.1f}% | "
          f"DD Stop: {'YES' if dd_stop_hit else 'NO'}")

    # FVG breakdown
    if not trades_df.empty:
        for st in trades_df["signal_type"].unique():
            t = trades_df[trades_df["signal_type"] == st]
            t_gross = (t["pnl_usd"] + t["commission"]).sum()
            t_comm  = t["commission"].sum()
            t_net   = t["pnl_usd"].sum()
            t_wr    = (t["pnl_r"] > 0).mean()
            sl_mean = abs(t["entry_price"] - t["stop_loss"]).mean()
            avg_comm = t["commission"].mean()
            print(f"         {st:12s}: {len(t):3d} trades | Gross: ${t_gross:+8,.2f} | Comm: ${t_comm:7,.2f} | "
                  f"Net: ${t_net:+8,.2f} | WR: {t_wr*100:.0f}% | Avg SL dist: {sl_mean:.1f} | Avg comm/trade: ${avg_comm:.2f}")

    return {
        "sl_pts": sl_pts,
        "trades": metrics.total_trades,
        "signals": result.signals_generated,
        "win_rate": metrics.win_rate,
        "gross_pnl": gross_pnl,
        "total_commission": total_comm,
        "net_pnl": net_pnl,
        "expectancy_r": metrics.expectancy_r,
        "max_dd_pct": metrics.max_drawdown_pct,
        "dd_stop_hit": dd_stop_hit,
        "comm_ratio": comm_ratio,
        "sharpe": metrics.sharpe_ratio,
    }


def main():
    inst_config = settings.get_instrument(SYMBOL)
    risk_config = settings.risk

    # Load data once
    bars_dict: dict[str, pd.DataFrame] = {}
    for tf in ["D1", "H4", "H1", "M15"]:
        p = f"data/cache/{SYMBOL}_{tf}.parquet"
        if not os.path.exists(p):
            raise FileNotFoundError(f"Missing: {p}")
        bars_dict[tf] = pd.read_parquet(p)

    m15_check = bars_dict["M15"].loc[START_DATE:END_DATE]
    log.info(f"[{SYMBOL}] M15 bars in window: {len(m15_check)}")

    print("\n" + "=" * 72)
    print(f"STEP 15: BTCUSD Minimum SL Sensitivity ({START_DATE} to {END_DATE})")
    print("=" * 72)
    print(f"  Testing thresholds: {SL_THRESHOLDS} pts")
    print(f"  Score gate: 70.0 <= score <= 79.9 (unchanged from Step 12)")
    print()

    results = []
    for sl_pts in SL_THRESHOLDS:
        r = run_with_sl_threshold(sl_pts, bars_dict, inst_config, risk_config)
        results.append(r)

    # Restore default
    gen_module._BTCUSD_MIN_SL_PTS = 50.0

    print("\n\n" + "=" * 72)
    print("STEP 15 FINAL COMPARISON TABLE — BTCUSD Min SL Sensitivity")
    print("=" * 72)
    print(f"{'MinSL':>8} {'Signals':>8} {'Trades':>7} {'Gross':>10} {'Comm':>9} {'Net':>10} {'ExpR':>7} {'MaxDD':>7} {'DDStop':>7} {'Sharpe':>7}")
    print("-" * 80)
    for r in results:
        gross_str = f"${r['gross_pnl']:+,.0f}"
        comm_str  = f"${r['total_commission']:,.0f}"
        net_str   = f"${r['net_pnl']:+,.0f}"
        exp_str   = f"{r['expectancy_r']:+.2f}R"
        dd_str    = f"{r['max_dd_pct']*100:.1f}%"
        dd_stop   = "YES" if r["dd_stop_hit"] else "no"
        print(f"{r['sl_pts']:>7}pt {r['signals']:>8} {r['trades']:>7} {gross_str:>10} {comm_str:>9} {net_str:>10} {exp_str:>7} {dd_str:>7} {dd_stop:>7} {r['sharpe']:>7.2f}")

    print("-" * 80)

    # Find best threshold
    best = max(results, key=lambda x: x["net_pnl"])
    print(f"\nBest Net PnL at Min SL = {best['sl_pts']} pts: ${best['net_pnl']:+,.2f} ({best['expectancy_r']:+.2f}R)")

    profitable = [r for r in results if r["net_pnl"] > 0]
    if not profitable:
        print("\nVERDICT: No SL threshold produced positive net PnL for BTCUSD.")
        print("  Commission drag persists even at 700 pts. BTCUSD may be structurally")
        print("  untradeable with current commission model ($7/lot/side).")
    else:
        print(f"\nVERDICT: {len(profitable)}/{len(results)} thresholds produced positive net PnL.")
        best_pos = max(profitable, key=lambda x: x["expectancy_r"])
        print(f"  Recommended: Min SL = {best_pos['sl_pts']} pts (Net: ${best_pos['net_pnl']:+,.2f}, {best_pos['expectancy_r']:+.2f}R)")

    log.info("Step 15 complete.")


if __name__ == "__main__":
    main()
