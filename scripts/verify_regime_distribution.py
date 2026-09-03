"""
Standalone Test for Regime Detection Module (signals/regime.py)

Evaluates regime classification strictly bar-by-bar (no look-ahead) over:
1. XAUUSD March 2 to May 29, 2026 (Choppy / Consolidation period)
2. XAUUSD August 6 to September 2, 2026 (Strong Bullish Trend period)

Prints regime distribution per timeframe (D1, H4, H1, M15) and composite market regime.
"""

import sys
import os
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signals.regime import (
    MarketRegime,
    detect_market_regime,
    calculate_adx_series,
)
from core.logger import get_logger

log = get_logger("test.regime_distribution")

def run_standalone_test():
    print("\n" + "=" * 72)
    print("STANDALONE TEST: signals/regime.py REGIME CLASSIFICATION ACCURACY")
    print("=" * 72)

    # 1. Load cached bars
    cache_dir = Path("data/cache")
    if not cache_dir.exists():
        raise FileNotFoundError("data/cache directory not found!")

    bars_dict = {
        "D1": pd.read_parquet(cache_dir / "XAUUSD_D1.parquet"),
        "H4": pd.read_parquet(cache_dir / "XAUUSD_H4.parquet"),
        "H1": pd.read_parquet(cache_dir / "XAUUSD_H1.parquet"),
        "M15": pd.read_parquet(cache_dir / "XAUUSD_M15.parquet"),
    }

    # Pre-calculate causal ADX series on each TF (strictly past data)
    adx_series_dict = {}
    for tf, df in bars_dict.items():
        adx_series_dict[tf] = calculate_adx_series(df, length=14)

    periods = [
        ("XAUUSD March-May 2026 (CHOP / CONSOLIDATION)", "2026-03-02", "2026-05-29"),
        ("XAUUSD August 2026 (STRONG TRENDING RUN)", "2026-08-06", "2026-09-02"),
    ]

    for label, start_date, end_date in periods:
        print(f"\nEvaluating: {label} [{start_date} to {end_date}]")
        print("-" * 72)

        m15_slice = bars_dict["M15"].loc[start_date:end_date]
        total_bars = len(m15_slice)

        composite_counts = {r.value: 0 for r in MarketRegime}
        tf_counts = {
            tf: {r.value: 0 for r in MarketRegime}
            for tf in ["D1", "H4", "H1", "M15"]
        }

        # Sample across M15 execution bars
        sample_indices = m15_slice.index[::4]
        n_samples = len(sample_indices)

        for ts in sample_indices:
            # Build strictly causal slices up to timestamp ts
            sliced_dict = {
                tf: df.loc[:ts]
                for tf, df in bars_dict.items()
            }

            report = detect_market_regime(
                bars_dict=sliced_dict,
                symbol="XAUUSD",
                current_ts=ts,
            )

            composite_counts[report.composite_regime.value] += 1
            for tf, tf_rep in report.tf_regimes.items():
                tf_counts[tf][tf_rep.regime.value] += 1

        print(f"Total M15 Bars: {total_bars} | Sampled Points: {n_samples}")
        print("\n[Composite Market Regime Distribution]:")
        for reg in [MarketRegime.TRENDING, MarketRegime.TRANSITIONAL, MarketRegime.CHOPPY]:
            pct = (composite_counts[reg.value] / n_samples) * 100
            count = composite_counts[reg.value]
            bar_chart = "#" * int(pct / 3)
            print(f"  {reg.value:12s}: {pct:5.1f}% ({count:4d}/{n_samples}) | {bar_chart}")

        print("\n[Per-Timeframe Regime Breakdown]:")
        for tf in ["D1", "H4", "H1", "M15"]:
            d_pct = (tf_counts[tf]["trending"] / n_samples) * 100
            t_pct = (tf_counts[tf]["transitional"] / n_samples) * 100
            c_pct = (tf_counts[tf]["choppy"] / n_samples) * 100
            print(
                f"  {tf:4s} -> Trending: {d_pct:5.1f}% | "
                f"Transitional: {t_pct:5.1f}% | "
                f"Choppy: {c_pct:5.1f}%"
            )

    print("\n" + "=" * 72)
    print("REGIME CLASSIFICATION TEST FINISHED")
    print("=" * 72)

if __name__ == "__main__":
    run_standalone_test()
