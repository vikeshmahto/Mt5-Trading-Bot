"""
scripts/run_walkforward_step18_fresh.py
────────────────────────────────────────────────────────
Step 18: Extended Fresh Validation (Dec 2025 & Jan 2026)

To completely rule out overfitting, this script fetches NEW historical data
for December 2025 and January 2026 (which is totally outside the current
cache bounds for BTCUSD) and runs the final locked configuration.

Months to test:
- Month 1: 2025-12-01 to 2025-12-31
- Month 2: 2026-01-01 to 2026-01-31
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
from data.mt5_client import MT5Client
from data.fetcher import fetch_bars

log = get_logger("scripts.step18_fresh")

TEST_MONTHS = [
    ("2025-12-01", "2025-12-31", "Dec 2025"),
    ("2026-01-01", "2026-01-31", "Jan 2026"),
]

def load_or_fetch(symbol: str) -> dict[str, pd.DataFrame]:
    """Ensure we have enough data going back to Nov 2025 for indicators."""
    bars_dict = {}
    with MT5Client():
        for tf in ["D1", "H4", "H1", "M15"]:
            cache_path = f"data/cache/{symbol}_{tf}_step18.parquet"
            if os.path.exists(cache_path):
                bars_dict[tf] = pd.read_parquet(cache_path)
            else:
                log.info(f"Fetching fresh {tf} data for {symbol}...")
                # Fetch 25000 bars to ensure we cover Dec 2025 and Jan 2026 (plus buffer)
                df = fetch_bars(symbol, tf, 25000, include_open=False)
                if df.empty:
                    log.error(f"Failed to fetch {tf} for {symbol}")
                else:
                    df.to_parquet(cache_path)
                    bars_dict[tf] = df
    return bars_dict

def run_month(symbol: str, start: str, end: str, label: str, bars_dict: dict) -> dict:
    inst_config = settings.get_instrument(symbol)
    risk_config = settings.risk

    # M15 check
    m15_check = bars_dict["M15"].loc[start:end]
    if len(m15_check) < 50:
        log.warning(f"[{symbol}] Insufficient data for {start}-{end}")
        return None

    engine = BacktestEngine(
        symbol=symbol,
        bars_dict=bars_dict,
        instrument_config=inst_config,
        risk_config=risk_config,
        start_date=start,
        end_date=end,
        persist=False,
    )

    result = engine.run()
    metrics = calculate_metrics(result.trades, result.equity_curve, risk_config.backtest.initial_balance)
    
    if metrics.total_trades > 0:
        win_rate = metrics.win_rate * 100
        net = metrics.net_pnl
        exp = metrics.expectancy_r
        dd = metrics.max_drawdown_pct * 100
    else:
        win_rate = net = exp = dd = 0

    return {
        "symbol": symbol,
        "month": label,
        "trades": metrics.total_trades,
        "win_rate": win_rate,
        "net": net,
        "exp": exp,
        "dd": dd
    }

def main():
    print("========================================================================")
    print("STEP 18: EXTENDED FRESH VALIDATION (Dec 2025 & Jan 2026)")
    print("========================================================================")
    
    results = []
    for sym in ["XAUUSD", "BTCUSD"]:
        bars_dict = load_or_fetch(sym)
        for start, end, label in TEST_MONTHS:
            res = run_month(sym, start, end, label, bars_dict)
            if res:
                results.append(res)
    
    print("\nFINAL RESULTS FOR 2 FRESH MONTHS:")
    print(f"{'Symbol':<10} {'Month':<10} {'Trades':>8} {'Net PnL':>10} {'Expectancy':>12} {'Max DD':>8}")
    print("-" * 65)
    for r in results:
        net_str = f"${r['net']:+,.2f}" if r["trades"] > 0 else "N/A"
        exp_str = f"{r['exp']:+.2f}R" if r["trades"] > 0 else "N/A"
        dd_str  = f"{r['dd']:.1f}%" if r["trades"] > 0 else "N/A"
        print(f"{r['symbol']:<10} {r['month']:<10} {r['trades']:>8} {net_str:>10} {exp_str:>12} {dd_str:>8}")

if __name__ == "__main__":
    main()
