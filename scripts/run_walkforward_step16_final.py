"""
scripts/run_walkforward_step16_final.py
────────────────────────────────────────────────────────
Step 16: True Final Pristine Validation

This script executes a 100% fresh, completely untouched walk-forward for the final
configured system. The user specifically requested a period NEVER used in any prior
step to prevent parameter-optimization overfitting (especially on BTCUSD's 500pt SL).

Periods used so far in this project:
- XAUUSD: Dec 25 - Feb 26 (Winter), Mar 26 - May 26 (Spring), Aug 26 - Sep 26 (Summer Chop)
- BTCUSD: Mar 26 - May 26 (Spring), Jul 26 - Sep 26 (Summer)
- EURUSD: Nov 25, Q1 26, Q2 26, Summer 26

Untouched overlap for both active instruments:
- JUNE 2026 (2026-06-01 to 2026-06-30)

Enabled Instruments:
- XAUUSD (Tier 80-100 blocked, min SL 1.5 pts)
- BTCUSD (Tier 80-100 blocked, min SL 500 pts)

No further parameter tuning will be done based on these results.
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

log = get_logger("scripts.step16_final")

START_DATE = "2026-06-01"
END_DATE   = "2026-06-30"


def run_instrument(symbol: str) -> dict:
    inst_config = settings.get_instrument(symbol)
    risk_config = settings.risk

    log.info("=" * 72)
    log.info(f">>> STEP 16 FINAL VALIDATION: {symbol} ({START_DATE} to {END_DATE})")
    log.info("=" * 72)

    # Load data
    bars_dict: dict[str, pd.DataFrame] = {}
    for tf in ["D1", "H4", "H1", "M15"]:
        p = f"data/cache/{symbol}_{tf}.parquet"
        if not os.path.exists(p):
            raise FileNotFoundError(f"Missing: {p}")
        bars_dict[tf] = pd.read_parquet(p)

    m15_check = bars_dict["M15"].loc[START_DATE:END_DATE]
    if len(m15_check) < 50:
        log.warning(f"[{symbol}] Insufficient data for {START_DATE}-{END_DATE}")
        return None

    log.info(f"[{symbol}] M15 bars in window: {len(m15_check)}")

    engine = BacktestEngine(
        symbol=symbol,
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

    reports_dir = Path("reports/walkforward_step16")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    slug = f"step16_final_{symbol}"
    csv_path = reports_dir / f"{slug}_trades.csv"
    md_path  = reports_dir / f"{slug}_report.md"

    export_trades_csv(result.trades, csv_path)
    generate_markdown_report(metrics, md_path)

    trades_df = pd.read_csv(csv_path) if os.path.exists(csv_path) and len(result.trades) > 0 else pd.DataFrame()

    print(f"\n{symbol} FINAL RESULTS:")
    print(f"  Signals   : {result.signals_generated}")
    print(f"  Trades    : {metrics.total_trades}")
    if metrics.total_trades > 0:
        print(f"  Win Rate  : {metrics.win_rate*100:.1f}%")
        print(f"  Gross PnL : ${metrics.total_pnl:+,.2f}")
        print(f"  Comm      : ${metrics.total_commission:,.2f}")
        print(f"  Net PnL   : ${metrics.net_pnl:+,.2f}")
        print(f"  Expectancy: {metrics.expectancy_r:+.2f}R")
        print(f"  Max DD    : {metrics.max_drawdown_pct*100:.1f}%")
        print(f"  Sharpe    : {metrics.sharpe_ratio:.2f}")

    return {
        "symbol": symbol,
        "trades": metrics.total_trades,
        "win_rate": metrics.win_rate,
        "gross": metrics.total_pnl,
        "comm": metrics.total_commission,
        "net": metrics.net_pnl,
        "exp_r": metrics.expectancy_r,
        "max_dd": metrics.max_drawdown_pct,
    }


def main():
    print("========================================================================")
    print("STEP 16: TRUE FINAL PRISTINE VALIDATION")
    print(f"Period: {START_DATE} to {END_DATE} (Untouched by all prior steps)")
    print("========================================================================")

    results = []
    for sym in ["XAUUSD", "BTCUSD"]:
        res = run_instrument(sym)
        if res:
            results.append(res)

    print("\n========================================================================")
    print("FINAL SYSTEM PERFORMANCE ACROSS ENABLED INSTRUMENTS (JUNE 2026)")
    print("========================================================================")
    print(f"{'Symbol':<10} {'Trades':>8} {'Net PnL':>10} {'Expectancy':>12} {'Max DD':>8}")
    print("-" * 52)
    
    total_net = 0
    total_trades = 0
    for r in results:
        net_str = f"${r['net']:+,.2f}" if r["trades"] > 0 else "N/A"
        exp_str = f"{r['exp_r']:+.2f}R" if r["trades"] > 0 else "N/A"
        dd_str  = f"{r['max_dd']*100:.1f}%" if r["trades"] > 0 else "N/A"
        print(f"{r['symbol']:<10} {r['trades']:>8} {net_str:>10} {exp_str:>12} {dd_str:>8}")
        
        total_net += r['net']
        total_trades += r['trades']

    print("-" * 52)
    print(f"COMBINED   {total_trades:>8} {f'${total_net:+,.2f}':>10}")

if __name__ == "__main__":
    main()
