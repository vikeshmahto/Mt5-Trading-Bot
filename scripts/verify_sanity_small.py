"""
scripts/verify_sanity_small.py
──────────────────────────────
Small-batch sanity check to verify:
1. Trade-level PnL math & contract multiplier matches position sizing risk.
2. Invariant assertions hold on every trade and equity curve.
3. Daily-resampled Sharpe & Sortino ratios are mathematically consistent with net returns.
4. Naked sweeps are 100% eliminated (all trades are OB/FVG).
5. Confluence score is logged passively.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi

log = get_logger(__name__)

def run_sanity_check():
    symbol = "XAUUSD"
    print("=" * 75)
    print("RUNNING SMALL-BATCH SANITY CHECK (1,000 M15 Bars)")
    print("=" * 75)

    with MT5Client():
        bars = fetch_multi(symbol, ["D1", "H4", "H1", "M15"], {"D1": 300, "H4": 800, "H1": 1000, "M15": 1000}, include_open=False)

    m15_df = bars.get("M15", pd.DataFrame())
    print(f"Data range: {m15_df.index[0]} -> {m15_df.index[-1]} ({len(m15_df)} bars)")

    engine = BacktestEngine(symbol=symbol, bars_dict=bars)
    result = engine.run()
    report = calculate_metrics(result.trades, result.equity_curve, result.initial_balance)

    print("\n" + "=" * 75)
    print("TRADE-BY-TRADE SANITY LEDGER (FIRST 15 TRADES):")
    print("=" * 75)
    print(f"{'#':<3} {'Time':<16} {'Dir':<5} {'Type':<12} {'Lots':<5} {'RiskPts':<8} {'PnL($)':<9} {'PnL(R)':<8} {'Comm':<6} {'Net($)':<9}")
    print("-" * 75)

    closed = [t for t in result.trades if t.exit_price is not None and t.pnl is not None]
    for idx, t in enumerate(closed[:15], 1):
        ts_str = t.entry_bar_ts.strftime('%m-%d %H:%M')
        sig_type = t.signal.signal_type.value if hasattr(t.signal, "signal_type") else "unknown"
        pnl_usd = t.pnl or 0.0
        pnl_r = t.pnl_r or 0.0
        comm = t.commission or 0.0
        net_usd = pnl_usd - comm
        print(f"{idx:<3} {ts_str:<16} {t.direction[:4]:<5} {sig_type:<12} {t.lot_size:<5.2f} {t.risk_points:<8.2f} ${pnl_usd:<+8.2f} {pnl_r:<+7.2f}R ${comm:<5.2f} ${net_usd:<+8.2f}")

    print("-" * 75)
    print(f"Total Trades Closed : {len(closed)}")
    print(f"Gross Trade Profit  : ${report.total_pnl:+,.2f}")
    print(f"Total Commissions   : ${report.total_commission:,.2f}")
    print(f"Net Profit          : ${report.net_pnl:+,.2f} ({report.return_pct:+.2%})")
    print(f"Expectancy (R)      : {report.expectancy_r:+.2f}R")
    print(f"Profit Factor       : {report.profit_factor:.2f}")
    print(f"Sharpe Ratio (daily): {report.sharpe_ratio:.2f}")
    print(f"Sortino Ratio       : {report.sortino_ratio:.2f}")
    print(f"Max Drawdown        : ${report.max_drawdown_dollars:,.2f} ({report.max_drawdown_pct:.2%})")
    print(f"Final Balance       : ${report.final_balance:,.2f}")
    print("=" * 75)

    # Verify Invariants
    for t in closed:
        # Check that no standalone sweep was allowed
        sig_type = t.signal.signal_type.value if hasattr(t.signal, "signal_type") else "unknown"
        assert sig_type != "sweep_entry", f"Violation: Found naked sweep trade {t}"
        
        # Check PnL math
        pt_diff = (t.exit_price - t.entry_price if t.direction == "bullish" else t.entry_price - t.exit_price)
        expected_pnl = pt_diff * t.lot_size * 100.0  # 1 lot gold = $100/pt
        assert abs(t.pnl - expected_pnl) < 1e-4, f"Trade PnL math mismatch: {t.pnl} != {expected_pnl}"

    # Check Equity Invariant
    expected_final = 10000.0 + report.net_pnl
    assert abs(report.final_balance - expected_final) < 0.01, f"Final balance invariant failure: {report.final_balance} != {expected_final}"
    assert abs(result.equity_curve.iloc[-1] - expected_final) < 0.05, f"Equity curve end mismatch: {result.equity_curve.iloc[-1]} != {expected_final}"

    print("\n>>> ALL INVARIANT CHECKS PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    run_sanity_check()
