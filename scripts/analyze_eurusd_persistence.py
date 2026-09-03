"""
scripts/analyze_eurusd_persistence.py
──────────────────────────────────────
Vectorized analysis of HTF alignment persistence across instruments.
Instead of calling compute_bias per-bar (slow), we read pre-cached data and
measure trend persistence using simple sliding-window HH/HL / LH/LL logic
applied once per timeframe. Then cross-join to measure alignment durations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np


def assign_bias_series(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """
    Vectorized bias assignment:  for every bar, look at the last `n` closes.
    Trend proxy: linear regression slope sign.
    BULLISH if slope > 0.05% per bar, BEARISH if < -0.05%, else NEUTRAL.
    Fast approximation that mirrors the structural bias direction.
    """
    pct_change = df["close"].pct_change()
    # Rolling mean of recent pct-changes as slope proxy
    slope = pct_change.rolling(n, min_periods=n // 2).mean()
    bias = pd.Series("NEUTRAL", index=df.index)
    bias[slope > 0.0005] = "BULLISH"
    bias[slope < -0.0005] = "BEARISH"
    return bias


def resample_bias_to_m15(bias_series: pd.Series, m15_index: pd.DatetimeIndex) -> pd.Series:
    """Forward-fill HTF bias onto M15 index."""
    combined = bias_series.reindex(m15_index.union(bias_series.index)).ffill()
    return combined.reindex(m15_index)


def analyze_symbol(symbol: str, start: str, end: str):
    print("=" * 72)
    print(f"TREND PERSISTENCE ANALYSIS: {symbol}  ({start} -> {end})")
    print("=" * 72)

    try:
        d1 = pd.read_parquet(f"data/cache/{symbol}_D1.parquet")
        h4 = pd.read_parquet(f"data/cache/{symbol}_H4.parquet")
        h1 = pd.read_parquet(f"data/cache/{symbol}_H1.parquet")
        m15 = pd.read_parquet(f"data/cache/{symbol}_M15.parquet")
    except FileNotFoundError as e:
        print(f"  [SKIP] Missing data: {e}")
        return

    # Slice to analysis window
    m15 = m15.loc[start:end]
    if m15.empty:
        print(f"  [SKIP] No M15 data in {start} – {end}")
        return

    m15_idx = m15.index

    # Compute bias series per HTF then reindex to M15
    d1_bias = assign_bias_series(d1.loc[:end], n=20)
    h4_bias = assign_bias_series(h4.loc[:end], n=20)
    h1_bias = assign_bias_series(h1.loc[:end], n=20)

    d1_on_m15 = resample_bias_to_m15(d1_bias, m15_idx)
    h4_on_m15 = resample_bias_to_m15(h4_bias, m15_idx)
    h1_on_m15 = resample_bias_to_m15(h1_bias, m15_idx)

    # Count max alignment per bar
    def max_align(d1v, h4v, h1v):
        bull = (d1v == "BULLISH") + (h4v == "BULLISH") + (h1v == "BULLISH")
        bear = (d1v == "BEARISH") + (h4v == "BEARISH") + (h1v == "BEARISH")
        return np.maximum(bull, bear)

    max_aligned = max_align(d1_on_m15.values, h4_on_m15.values, h1_on_m15.values)

    total = len(max_aligned)
    for k in [3, 2, 1, 0]:
        cnt = (max_aligned == k).sum()
        pct = 100 * cnt / total
        print(f"  {k}-HTF Aligned: {cnt:5d} M15 bars  ({pct:5.1f}%)")

    # 3-HTF streak durations (in M15 bars; 1 M15 = 15 min)
    is_3htf = (max_aligned == 3).astype(int)
    # Detect run-length encoding of 1s
    changes = np.diff(np.concatenate([[0], is_3htf, [0]]))
    starts = np.where(changes == 1)[0]
    ends   = np.where(changes == -1)[0]
    streaks_bars = ends - starts
    streaks_hours = streaks_bars * 15 / 60

    if len(streaks_hours) > 0:
        print(f"\n  3-HTF Streak Statistics (consecutive M15 bars):")
        print(f"    Count of streaks : {len(streaks_hours)}")
        print(f"    Median duration  : {np.median(streaks_hours):.1f} hours  ({np.median(streaks_hours)/24:.1f} days)")
        print(f"    Mean duration    : {np.mean(streaks_hours):.1f} hours  ({np.mean(streaks_hours)/24:.1f} days)")
        print(f"    Max duration     : {np.max(streaks_hours):.1f} hours  ({np.max(streaks_hours)/24:.1f} days)")
        print(f"    % of time in 3-HTF streak: {100 * streaks_bars.sum() / total:.1f}%")
    else:
        print("  No 3-HTF streaks found in this window.")

    print()


if __name__ == "__main__":
    # Step 11/12 test windows + EURUSD Q1 2026
    analyze_symbol("EURUSD", "2026-01-05", "2026-04-30")
    analyze_symbol("XAUUSD", "2025-12-01", "2026-02-27")
    analyze_symbol("BTCUSD", "2026-03-01", "2026-05-31")
