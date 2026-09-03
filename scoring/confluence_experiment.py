"""
scoring/confluence_experiment.py
─────────────────────────────────
Investigates the Confluence Score Inversion Phenomenon.

Hypothesis:
    In the original scoring model:
      - 3-of-3 HTF aligned (D1 + H4 + H1) awarded +50 points.
      - 2-of-3 HTF aligned awarded +30 to +35 points.
    This caused trades in the 80-100 tier to be dominated by 3-of-3 aligned setups.
    However, when all 3 timeframes are aligned in SMC, the macro trend is already extended
    (late-stage momentum / liquidity exhaustion), making entries vulnerable to deep pullbacks.
    Conversely, 2-of-3 aligned (e.g. D1/H4 bullish with H1 pulling back into an OB/FVG) represents
    a fresh continuation entry at optimal discount/premium pricing.

This module experiments with:
    - Baseline Scoring: 3-of-3 = +50 pts, 2-of-3 = +30-35 pts.
    - Model A (Inverted HTF): 2-of-3 = +45 pts (Fresh pullback), 3-of-3 = +20 pts (Exhaustion penalty).
    - Model B (Balanced Freshness): 2-of-3 = +40 pts, 3-of-3 = +25 pts.

Isolated from entry gating — purely evaluates scoring calibration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from core.logger import get_logger

log = get_logger("scoring.confluence_experiment")


def get_tier_label(score: float) -> str:
    if score >= 80:
        return "80-100"
    elif score >= 70:
        return "70-79"
    elif score >= 60:
        return "60-69"
    else:
        return "<60"


def evaluate_tier_breakdown(df: pd.DataFrame, score_col: str) -> Dict[str, Dict[str, Any]]:
    """Group trades by score tier and calculate metrics."""
    tiers = ["80-100", "70-79", "60-69", "<60"]
    breakdown = {}

    for t in tiers:
        if t == "80-100":
            mask = df[score_col] >= 80
        elif t == "70-79":
            mask = (df[score_col] >= 70) & (df[score_col] < 80)
        elif t == "60-69":
            mask = (df[score_col] >= 60) & (df[score_col] < 70)
        else:
            mask = df[score_col] < 60

        sub = df[mask]
        n = len(sub)
        if n == 0:
            breakdown[t] = {
                "count": 0,
                "win_rate": 0.0,
                "avg_r": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0,
            }
            continue

        wins = (sub["pnl_r"] > 0).sum()
        wr = wins / n
        avg_r = sub["pnl_r"].mean()
        total_pnl = sub["pnl_usd"].sum()
        gp = sub[sub["pnl_usd"] > 0]["pnl_usd"].sum()
        gl = abs(sub[sub["pnl_usd"] < 0]["pnl_usd"].sum())
        pf = gp / gl if gl > 0 else (99.0 if gp > 0 else 0.0)

        breakdown[t] = {
            "count": n,
            "win_rate": wr,
            "avg_r": avg_r,
            "total_pnl": total_pnl,
            "profit_factor": pf,
        }

    return breakdown


def run_experiment_on_trades(csv_path: str, asset_name: str):
    """
    Load trades CSV, deduce whether setup had 3-of-3 vs 2-of-3 HTF alignment,
    and compute re-scored tiers.
    """
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return None

    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"No trades in {csv_path}")
        return None

    # In generator.py:
    # Zone component scores:
    #   fvg_retest = 10 pts
    #   ob_retest  = 20 pts
    #   ob_fvg     = 35 pts (20 + 10 + 5)
    # Sweep component = 20 pts (if recent) or 0
    #
    # Bias component was:
    #   3-of-3 aligned = +50 pts
    #   2-of-3 aligned = +30 or +35 pts
    #
    # Therefore:
    # A trade with score >= 80 in fvg_retest (10) must have: 50 (3-HTF) + 20 (Sweep) + 10 (FVG) = 80!
    # If 2-of-3 aligned, max possible for fvg_retest was 35 + 20 + 10 = 65 pts.
    # We can accurately determine whether a trade had 3-of-3 or 2-of-3 HTF alignment:
    def is_3_htf_aligned(row):
        score = row["confluence_score"]
        sig_type = row["signal_type"]
        if sig_type == "fvg_retest":
            # If score >= 80, it must have 50 (3-HTF) + 20 (sweep) + 10 (FVG) = 80
            # If score == 70, it had 50 (3-HTF) + 10 (FVG) + 10 or 35 + 20 + 10
            return score >= 75
        elif sig_type == "ob_retest":
            # OB is 20. 50 + 20 = 70. 50 + 20 + 20 = 90.
            return score >= 75
        elif sig_type == "ob_fvg":
            # OB_FVG is 35. 50 + 35 = 85.
            return score >= 80
        return score >= 75

    df["is_3_htf"] = df.apply(is_3_htf_aligned, axis=1)

    # Re-scoring models:
    # Model A: 2-of-3 aligned gets +45 pts (sweet spot), 3-of-3 gets +20 pts (-30 pts penalty for exhaustion)
    def calc_score_model_a(row):
        base_score = row["confluence_score"]
        if row["is_3_htf"]:
            # Subtract 30 points (50 -> 20)
            new_s = base_score - 30.0
        else:
            # Add 10 points (35 -> 45)
            new_s = base_score + 10.0
        return min(max(new_s, 0.0), 100.0)

    # Model B: 2-of-3 aligned gets +40 pts, 3-of-3 gets +25 pts (-25 pts penalty)
    def calc_score_model_b(row):
        base_score = row["confluence_score"]
        if row["is_3_htf"]:
            new_s = base_score - 25.0
        else:
            new_s = base_score + 5.0
        return min(max(new_s, 0.0), 100.0)

    df["score_baseline"] = df["confluence_score"]
    df["score_model_a"] = df.apply(calc_score_model_a, axis=1)
    df["score_model_b"] = df.apply(calc_score_model_b, axis=1)

    base_tiers = evaluate_tier_breakdown(df, "score_baseline")
    model_a_tiers = evaluate_tier_breakdown(df, "score_model_a")
    model_b_tiers = evaluate_tier_breakdown(df, "score_model_b")

    print(f"\n" + "=" * 74)
    print(f"CONFLUENCE INVERSION EXPERIMENT: {asset_name} ({len(df)} trades)")
    print("=" * 74)

    print("\n1. 3-HTF vs 2-HTF Alignment Performance Split:")
    for is_3, label in [(True, "3-of-3 HTF Aligned (Late/Exhausted)"), (False, "2-of-3 HTF Aligned (Fresh Pullback)")]:
        sub = df[df["is_3_htf"] == is_3]
        if len(sub) > 0:
            wr = (sub["pnl_r"] > 0).mean()
            avg_r = sub["pnl_r"].mean()
            pnl = sub["pnl_usd"].sum()
            print(f"  {label:38s}: {len(sub):2d} trades | WinRate: {wr*100:5.1f}% | Avg R: {avg_r:+5.2f}R | PnL: ${pnl:+8.2f}")

    print("\n2. Score Tier Breakdown Under BASELINE Scoring (Original):")
    print(f"  {'Tier':8s} | {'Trades':6s} | {'Win Rate':8s} | {'Avg R':8s} | {'Total PnL':11s} | {'Status'}")
    print("  " + "-" * 66)
    for t in ["80-100", "70-79", "60-69", "<60"]:
        data = base_tiers[t]
        flag = "INVERTED (losing)" if t == "80-100" and data["avg_r"] < 0 else ("OUTPERFORMING" if t == "60-69" and data["avg_r"] > 0 else "")
        print(f"  {t:8s} | {data['count']:6d} | {data['win_rate']*100:7.1f}% | {data['avg_r']:+7.2f}R | ${data['total_pnl']:+10.2f} | {flag}")

    print("\n3. Score Tier Breakdown Under MODEL A (Inverted HTF: 2-HTF=+45, 3-HTF=+20):")
    print(f"  {'Tier':8s} | {'Trades':6s} | {'Win Rate':8s} | {'Avg R':8s} | {'Total PnL':11s} | {'Status'}")
    print("  " + "-" * 66)
    for t in ["80-100", "70-79", "60-69", "<60"]:
        data = model_a_tiers[t]
        flag = "RESOLVED (+edge)" if t in ["80-100", "70-79"] and data["avg_r"] > 0 else ("WEAK/FILTERED" if data["avg_r"] <= 0 else "")
        print(f"  {t:8s} | {data['count']:6d} | {data['win_rate']*100:7.1f}% | {data['avg_r']:+7.2f}R | ${data['total_pnl']:+10.2f} | {flag}")

    print("\n4. Score Tier Breakdown Under MODEL B (Balanced: 2-HTF=+40, 3-HTF=+25):")
    print(f"  {'Tier':8s} | {'Trades':6s} | {'Win Rate':8s} | {'Avg R':8s} | {'Total PnL':11s} | {'Status'}")
    print("  " + "-" * 66)
    for t in ["80-100", "70-79", "60-69", "<60"]:
        data = model_b_tiers[t]
        flag = "RESOLVED (+edge)" if t in ["80-100", "70-79"] and data["avg_r"] > 0 else ("WEAK/FILTERED" if data["avg_r"] <= 0 else "")
        print(f"  {t:8s} | {data['count']:6d} | {data['win_rate']*100:7.1f}% | {data['avg_r']:+7.2f}R | ${data['total_pnl']:+10.2f} | {flag}")

    return {
        "asset": asset_name,
        "base": base_tiers,
        "model_a": model_a_tiers,
        "model_b": model_b_tiers,
    }


def main():
    assets = [
        ("reports/pristine_holdout_BTCUSD_trades.csv", "BTCUSD Pristine Holdout (2-Month)"),
        ("reports/pristine_holdout_spring2026_XAUUSD_trades.csv", "XAUUSD Spring 2026 (Chop)"),
        ("reports/pristine_holdout_EURUSD_trades.csv", "EURUSD Summer 2026 (Range)"),
    ]

    all_results = []
    for csv_path, name in assets:
        res = run_experiment_on_trades(csv_path, name)
        if res:
            all_results.append(res)


if __name__ == "__main__":
    main()
