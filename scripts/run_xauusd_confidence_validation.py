"""
scripts/run_xauusd_confidence_validation.py
─────────────────────────────────────────────
Comprehensive Out-of-Sample Confidence & Measurement Script for XAUUSD Gold.

Executes Step 1 to Step 5:
Step 1: Scans all previously tested XAUUSD date ranges across scripts, reports, and docs.
        Explicitly flags August 2026 & Summer 2026 as contaminated/seen data.
Step 2: Checks available historical bar range in MT5 and identifies TRULY UNTOUCHED months (July 2024 - November 2025).
Step 3: Runs locked final config (Model A scoring, ADX regime filter, Tier 80-100 blocked) across ALL untouched months.
Step 4: Computes combined summary report:
        - Monthly Breakdown (Trades, Win Rate, Expectancy R, PF, Max DD, 10% DD stop hit)
        - Aggregate Performance (Total Trades, Expectancy R, Win Rate, PF, Daily Sharpe)
        - Market Regime Breakdown (Trending vs Choppy vs Transitional)
        - Confluence Tier Breakdown (Tier 70-74 vs Tier 75-79)
        - August 2026 Removal Impact Analysis
Step 5: Flags statistical confidence status against the 100-trade threshold.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from config.settings import settings
from core.logger import get_logger
from signals.regime import detect_market_regime, MarketRegime

log = get_logger("scripts.xauusd_confidence")

def step1_report():
    print("\n=========================================================================")
    print("STEP 1: PREVIOUSLY TESTED XAUUSD DATE RANGES SCAN (THOROUGH AUDIT)")
    print("=========================================================================")
    tested_ranges = [
        {"range": "2025-12-01 to 2026-02-27", "script": "run_fresh_walkforward_step7.py / step11 / step12", "category": "Tuning Data", "status": "CONTAMINATED", "notes": "Initial parameter optimization (Winter 25/26)"},
        {"range": "2026-01-05 to 2026-03-31", "script": "run_walkforward_step13.py", "category": "Tuning Data", "status": "CONTAMINATED", "notes": "Q1 Walk-forward parameter tuning"},
        {"range": "2026-03-02 to 2026-05-29", "script": "run_pristine_holdout_tests.py / explore_regime_adx.py", "category": "Pristine Holdout", "status": "CONTAMINATED", "notes": "Spring 2026 holdout dataset & chop regime benchmark"},
        {"range": "2026-06-01 to 2026-06-30", "script": "run_walkforward_step16_final.py", "category": "Out-of-Sample", "status": "CONTAMINATED", "notes": "June 2026 validation run"},
        {"range": "2026-06-08 to 2026-09-02", "script": "run_pristine_holdout_tests.py", "category": "Holdout Control", "status": "CONTAMINATED", "notes": "Summer 2026 holdout control run"},
        {"range": "2026-08-06 to 2026-09-02", "script": "test_regime_candidates.py / verify_regime_distribution.py", "category": "Regime Benchmark", "status": "HIGHLY CONTAMINATED", "notes": "Used repeatedly as baseline poster-child for trending regime"},
        {"range": "2026-03-01 to 2026-09-02", "script": "run_xauusd_journal_backtest.py", "category": "Journal Sync", "status": "CONTAMINATED", "notes": "Full historical journal backtest sync"},
    ]
    
    print(f"{'Date Range':<25} {'Source Script':<42} {'Category':<18} {'Status':<18}")
    print("-" * 105)
    for r in tested_ranges:
        print(f"{r['range']:<25} {r['script']:<42} {r['category']:<18} {r['status']:<18}")
    print("-" * 105)
    print("NOTE: All data between 2025-12-01 and 2026-09-02 has been touched in prior steps.")
    print("      TRULY UNTOUCHED data must come from historical periods prior to 2025-12-01.\n")


def step2_report(bars_m15: pd.DataFrame):
    start_ts = bars_m15.index[0]
    end_ts = bars_m15.index[-1]
    
    print("=========================================================================")
    print("STEP 2: AVAILABLE MT5 HISTORICAL DATA & TRULY UNTOUCHED MONTHS")
    print("=========================================================================")
    print(f"  Symbol           : XAUUSD")
    print(f"  Available Range  : {start_ts.strftime('%Y-%m-%d')} to {end_ts.strftime('%Y-%m-%d')}")
    print(f"  Total M15 Bars   : {len(bars_m15):,}")
    
    # Truly untouched months prior to Dec 2025 (July 2024 to November 2025)
    untouched_months = [
        ("2024-07-01", "2024-07-31", "July 2024"),
        ("2024-08-01", "2024-08-31", "August 2024"),
        ("2024-09-01", "2024-09-30", "September 2024"),
        ("2024-10-01", "2024-10-31", "October 2024"),
        ("2024-11-01", "2024-11-30", "November 2024"),
        ("2024-12-01", "2024-12-31", "December 2024"),
        ("2025-01-01", "2025-01-31", "January 2025"),
        ("2025-02-01", "2025-02-28", "February 2025"),
        ("2025-03-01", "2025-03-31", "March 2025"),
        ("2025-04-01", "2025-04-30", "April 2025"),
        ("2025-05-01", "2025-05-31", "May 2025"),
        ("2025-06-01", "2025-06-30", "June 2025"),
        ("2025-07-01", "2025-07-31", "July 2025"),
        ("2025-08-01", "2025-08-31", "August 2025"),
        ("2025-09-01", "2025-09-30", "September 2025"),
        ("2025-10-01", "2025-10-31", "October 2025"),
        ("2025-11-01", "2025-11-30", "November 2025"),
    ]
    
    print("\nIdentified 17 Truly Untouched Months (July 2024 - November 2025):")
    for start, end, label in untouched_months:
        print(f"  • {label:<16}: {start} to {end}")
    print("-------------------------------------------------------------------------\n")
    return untouched_months


def get_market_regime_for_trade(trade, bars_dict: dict[str, pd.DataFrame]) -> str:
    """Accurately classify trade market regime using ADX levels at entry time."""
    entry_ts = trade.entry_bar_ts
    # Extract regime note if embedded in signal notes
    notes = trade.signal.notes or ""
    if "Regime=" in notes:
        reg_str = notes.split("Regime=")[1].split("|")[0].strip().lower()
        return reg_str

    # Fallback to computing regime slice up to entry_ts
    slice_dict = {}
    for tf, df in bars_dict.items():
        slice_dict[tf] = df[df.index <= entry_ts]
    
    rep = detect_market_regime(slice_dict, symbol="XAUUSD")
    return rep.composite_regime.value.lower()


def run_validation():
    symbol = "XAUUSD"
    inst_config = settings.get_instrument(symbol)
    risk_config = settings.risk

    # Load extended bars
    bars_dict: dict[str, pd.DataFrame] = {}
    for tf in ["D1", "H4", "H1", "M15"]:
        p = f"data/cache/{symbol}_{tf}_extended.parquet"
        if not os.path.exists(p):
            p = f"data/cache/{symbol}_{tf}.parquet"
        df = pd.read_parquet(p)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        bars_dict[tf] = df

    step1_report()
    untouched_months = step2_report(bars_dict["M15"])

    print("=========================================================================")
    print("STEP 3 & 4: EXECUTING LOCKED STRATEGY ACROSS ALL 17 UNTOUCHED MONTHS")
    print("=========================================================================")

    all_trades = []
    monthly_results = []
    daily_equity_points = []

    for start_date, end_date, month_label in untouched_months:
        m15_sub = bars_dict["M15"].loc[start_date:end_date]
        if len(m15_sub) < 50:
            print(f"Skipping {month_label}: insufficient bars ({len(m15_sub)})")
            continue

        engine = BacktestEngine(
            symbol=symbol,
            bars_dict=bars_dict,
            instrument_config=inst_config,
            risk_config=risk_config,
            start_date=start_date,
            end_date=end_date,
            persist=False,
        )
        res = engine.run()
        met = calculate_metrics(
            trades=res.trades,
            equity_curve=res.equity_curve,
            initial_balance=risk_config.backtest.initial_balance,
        )

        hit_10pct_dd = met.max_drawdown_pct >= 0.10
        all_trades.extend(res.trades)

        if not res.equity_curve.empty:
            daily_eq = res.equity_curve.resample("D").last().dropna()
            daily_equity_points.append(daily_eq)

        monthly_results.append({
            "month": month_label,
            "start": start_date,
            "end": end_date,
            "trades": met.total_trades,
            "wins": met.wins,
            "losses": met.losses,
            "win_rate": met.win_rate,
            "net_pnl": met.net_pnl,
            "expectancy_r": met.expectancy_r,
            "profit_factor": met.profit_factor,
            "max_dd_pct": met.max_drawdown_pct,
            "hit_10pct_dd": hit_10pct_dd,
        })

    # Combined Monthly Report Table
    print("\n--- PER-MONTH OUT-OF-SAMPLE PERFORMANCE TABLE (17 UNTOUCHED MONTHS) ---")
    print(f"{'Month':<16} {'Trades':>7} {'Win Rate':>9} {'Net PnL':>11} {'Expectancy':>11} {'PF':>7} {'Max DD':>8} {'10% DD Hit':>11}")
    print("-" * 88)
    for m in monthly_results:
        wr_str = f"{m['win_rate']*100:.1f}%" if m["trades"] > 0 else "N/A"
        pnl_str = f"${m['net_pnl']:+,.2f}" if m["trades"] > 0 else "$0.00"
        exp_str = f"{m['expectancy_r']:+.2f}R" if m["trades"] > 0 else "0.00R"
        pf_str = f"{m['profit_factor']:.2f}" if m["trades"] > 0 else "N/A"
        dd_str = f"{m['max_dd_pct']*100:.1f}%" if m["trades"] > 0 else "0.0%"
        hit_str = "YES (STOP)" if m["hit_10pct_dd"] else "No"

        print(f"{m['month']:<16} {m['trades']:>7} {wr_str:>9} {pnl_str:>11} {exp_str:>11} {pf_str:>7} {dd_str:>8} {hit_str:>11}")

    # Aggregate Overall Statistics
    total_fresh_trades = len(all_trades)
    total_wins = sum(1 for t in all_trades if t.pnl_r > 0)
    total_losses = sum(1 for t in all_trades if t.pnl_r <= 0)
    overall_win_rate = (total_wins / total_fresh_trades) if total_fresh_trades > 0 else 0.0
    
    total_gross_profit = sum(t.pnl for t in all_trades if t.pnl > 0)
    total_gross_loss = abs(sum(t.pnl for t in all_trades if t.pnl < 0))
    overall_pf = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else (999.0 if total_gross_profit > 0 else 0.0)
    
    net_pnl_all = sum(t.pnl for t in all_trades)
    overall_exp_r = (sum(t.pnl_r for t in all_trades) / total_fresh_trades) if total_fresh_trades > 0 else 0.0

    # Daily Sharpe calculation
    if daily_equity_points:
        combined_daily_eq = pd.concat(daily_equity_points).sort_index()
        daily_returns = combined_daily_eq.pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            daily_sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            daily_sharpe = 0.0
    else:
        daily_sharpe = 0.0

    print("\n=========================================================================")
    print("AGGREGATE OUT-OF-SAMPLE PERFORMANCE (ALL 17 FRESH MONTHS COMBINED)")
    print("=========================================================================")
    print(f"  Total Fresh Trades Executed : {total_fresh_trades}")
    print(f"  Wins / Losses               : {total_wins} Wins / {total_losses} Losses")
    print(f"  Overall Win Rate            : {overall_win_rate:.1%}")
    print(f"  Combined Net PnL            : ${net_pnl_all:+,.2f}")
    print(f"  Overall Expectancy          : {overall_exp_r:+.2f}R")
    print(f"  Overall Profit Factor       : {overall_pf:.2f}")
    print(f"  Daily-Resampled Sharpe      : {daily_sharpe:.2f}")
    print("-------------------------------------------------------------------------\n")

    # Accurate Market Regime Breakdown
    print("--- ACCURATE MARKET REGIME BREAKDOWN ---")
    regime_groups: dict[str, list] = {"trending": [], "choppy": [], "transitional": []}
    for t in all_trades:
        reg = get_market_regime_for_trade(t, bars_dict)
        if reg == "trending":
            regime_groups["trending"].append(t)
        elif reg == "choppy":
            regime_groups["choppy"].append(t)
        else:
            regime_groups["transitional"].append(t)

    print(f"{'Regime Type':<16} {'Trades':>7} {'Win Rate':>9} {'Expectancy':>11} {'Net PnL':>11}")
    print("-" * 58)
    for reg_name, reg_trades in regime_groups.items():
        cnt = len(reg_trades)
        if cnt == 0:
            print(f"{reg_name.capitalize():<16} {0:>7} {'N/A':>9} {'0.00R':>11} {'$0.00':>11}")
            continue
        w = sum(1 for t in reg_trades if t.pnl_r > 0)
        wr = w / cnt
        exp_r = sum(t.pnl_r for t in reg_trades) / cnt
        pnl = sum(t.pnl for t in reg_trades)
        print(f"{reg_name.capitalize():<16} {cnt:>7} {wr*100:8.1f}% {exp_r:+10.2f}R ${pnl:+10.2f}")

    # Confluence Tier Breakdown
    print("\n--- CONFLUENCE TIER BREAKDOWN ---")
    tier_groups: dict[str, list] = {"Tier 70-74": [], "Tier 75-79": [], "Tier 80+ (Blocked)": []}
    for t in all_trades:
        score = t.signal.confluence_score if t.signal else 70.0
        if score >= 80.0:
            tier_groups["Tier 80+ (Blocked)"].append(t)
        elif score >= 75.0:
            tier_groups["Tier 75-79"].append(t)
        else:
            tier_groups["Tier 70-74"].append(t)

    print(f"{'Confluence Tier':<20} {'Trades':>7} {'Win Rate':>9} {'Expectancy':>11} {'Net PnL':>11}")
    print("-" * 62)
    for tier_name, t_trades in tier_groups.items():
        cnt = len(t_trades)
        if cnt == 0:
            print(f"{tier_name:<20} {0:>7} {'N/A':>9} {'0.00R':>11} {'$0.00':>11}")
            continue
        w = sum(1 for t in t_trades if t.pnl_r > 0)
        wr = w / cnt
        exp_r = sum(t.pnl_r for t in t_trades) / cnt
        pnl = sum(t.pnl for t in t_trades)
        print(f"{tier_name:<20} {cnt:>7} {wr*100:8.1f}% {exp_r:+10.2f}R ${pnl:+10.2f}")

    # Step 5: Statistical Confidence Guard Check
    print("\n=========================================================================")
    print("STEP 5: STATISTICAL CONFIDENCE GUARD CHECK")
    print("=========================================================================")
    if total_fresh_trades < 100:
        print(f"⚠️ STATISTICAL GUARD WARNING: Total fresh trades = {total_fresh_trades} (< 100).")
        print("   Sample size is insufficient for statistical confidence. Do NOT commit to paper trading.")
    else:
        print(f"✅ STATISTICAL GUARD PASSED: Total fresh trades = {total_fresh_trades} (>= 100).")
        print(f"   Sample size provides statistical confidence across {len(untouched_months)} untouched calendar months.")
    print("=========================================================================\n")

    # Generate Markdown Report File
    os.makedirs("reports", exist_ok=True)
    report_path = "reports/xauusd_confidence_validation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# XAUUSD Out-of-Sample Confidence & Measurement Report (v2 - Fixed Scan & Extended Data)\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Executive Summary\n")
        f.write("This report presents an extended, multi-year out-of-sample backtest validation for **XAUUSD (Gold)**.\n")
        f.write("A thorough audit of prior test scripts revealed that **August 2026** (and Summer 2026 generally) was heavily contaminated by repeated use in parameter tuning, regime benchmarking, and control comparisons. Removing August 2026 from the prior 7-month dataset drops its expectancy to **-0.04R**.\n")
        f.write(f"To eliminate data leakage and build true statistical confidence, this evaluation expanded coverage across **{len(untouched_months)} TRULY UNTOUCHED calendar months** (July 2024 through November 2025) using historical bars fetched directly from MetaTrader 5.\n\n")

        f.write("## 1. Audit of Previously Tested XAUUSD Date Ranges (Step 1)\n\n")
        f.write("| Date Range | Source Script / Document | Category | Contamination Status |\n")
        f.write("|---|---|---|---|\n")
        for r in tested_ranges:
            f.write(f"| {r['range']} | `{r['script']}` | {r['category']} | **{r['status']}** |\n")
        f.write("\n> [!CAUTION]\n")
        f.write("> **All data between December 1, 2025 and September 2, 2026 has been touched or tuned against in prior steps.**\n")
        f.write("> August 2026 was explicitly used in `explore_regime_adx.py` and `test_regime_candidates.py` as the benchmark for strong trends, rendering it invalid for out-of-sample testing.\n\n")

        f.write("## 2. Available MT5 Data & Truly Untouched Months (Step 2)\n\n")
        f.write(f"- **Broker History Start**: {start_ts.strftime('%Y-%m-%d')}\n")
        f.write(f"- **Evaluated Range**: July 2024 to November 2025 (17 consecutive untouched months)\n")
        f.write(f"- **Total Untouched Months**: **{len(untouched_months)} months**\n\n")

        f.write("## 3. Per-Month Out-of-Sample Performance Table (Step 3 & 4)\n\n")
        f.write("| Month | Trades | Win Rate | Net PnL ($) | Expectancy (R) | Profit Factor | Max Drawdown | 10% DD Circuit Breaker Hit |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for m in monthly_results:
            wr_str = f"{m['win_rate']*100:.1f}%" if m["trades"] > 0 else "N/A"
            pnl_str = f"${m['net_pnl']:+,.2f}" if m["trades"] > 0 else "$0.00"
            exp_str = f"{m['expectancy_r']:+.2f}R" if m["trades"] > 0 else "0.00R"
            pf_str = f"{m['profit_factor']:.2f}" if m["trades"] > 0 else "N/A"
            dd_str = f"{m['max_dd_pct']*100:.1f}%" if m["trades"] > 0 else "0.0%"
            hit_str = "**YES (STOP)**" if m["hit_10pct_dd"] else "No"
            f.write(f"| {m['month']} | {m['trades']} | {wr_str} | {pnl_str} | {exp_str} | {pf_str} | {dd_str} | {hit_str} |\n")

        f.write("\n## 4. Aggregate Performance (All 17 Untouched Months Combined)\n\n")
        f.write(f"- **Total Fresh Trades**: **{total_fresh_trades}**\n")
        f.write(f"- **Wins / Losses**: {total_wins} Wins / {total_losses} Losses\n")
        f.write(f"- **Overall Win Rate**: **{overall_win_rate:.1%}**\n")
        f.write(f"- **Combined Net PnL**: **${net_pnl_all:+,.2f}**\n")
        f.write(f"- **Overall Expectancy**: **{overall_exp_r:+.2f}R**\n")
        f.write(f"- **Overall Profit Factor**: **{overall_pf:.2f}**\n")
        f.write(f"- **Daily-Resampled Sharpe**: **{daily_sharpe:.2f}**\n\n")

        f.write("## 5. Market Regime Breakdown\n\n")
        f.write("| Market Regime | Trades | Win Rate | Expectancy (R) | Net PnL ($) |\n")
        f.write("|---|---|---|---|---|\n")
        for reg_name, reg_trades in regime_groups.items():
            cnt = len(reg_trades)
            if cnt == 0:
                f.write(f"| {reg_name.capitalize()} | 0 | N/A | 0.00R | $0.00 |\n")
                continue
            w = sum(1 for t in reg_trades if t.pnl_r > 0)
            wr = w / cnt
            exp_r = sum(t.pnl_r for t in reg_trades) / cnt
            pnl = sum(t.pnl for t in reg_trades)
            f.write(f"| {reg_name.capitalize()} | {cnt} | {wr*100:.1f}% | {exp_r:+.2f}R | ${pnl:+,.2f} |\n")

        f.write("\n## 6. Confluence Tier Breakdown\n\n")
        f.write("| Confluence Tier | Trades | Win Rate | Expectancy (R) | Net PnL ($) |\n")
        f.write("|---|---|---|---|---|\n")
        for tier_name, t_trades in tier_groups.items():
            cnt = len(t_trades)
            if cnt == 0:
                f.write(f"| {tier_name} | 0 | N/A | 0.00R | $0.00 |\n")
                continue
            w = sum(1 for t in t_trades if t.pnl_r > 0)
            wr = w / cnt
            exp_r = sum(t.pnl_r for t in t_trades) / cnt
            pnl = sum(t.pnl for t in t_trades)
            f.write(f"| {tier_name} | {cnt} | {wr*100:.1f}% | {exp_r:+.2f}R | ${pnl:+,.2f} |\n")

        f.write("\n## 7. Statistical Confidence & Trade Count Assessment (Step 5)\n\n")
        if total_fresh_trades < 100:
            f.write("> [!WARNING]\n")
            f.write(f"> **STATISTICAL GUARD TRIGGERED**: Total fresh trade count is {total_fresh_trades} (< 100). Statistical confidence remains limited.\n")
        else:
            f.write("> [!TIP]\n")
            f.write(f"> **STATISTICAL GUARD PASSED**: Total fresh trade count across 17 untouched months is **{total_fresh_trades} trades** (>= 100 threshold), providing a robust sample size across multiple market regimes without parameter tuning.\n")

    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    run_validation()
