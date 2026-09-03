import pandas as pd
import pandas_ta as ta

m15 = pd.read_parquet('data/cache/XAUUSD_M15.parquet')
h1 = pd.read_parquet('data/cache/XAUUSD_H1.parquet')
h4 = pd.read_parquet('data/cache/XAUUSD_H4.parquet')
d1 = pd.read_parquet('data/cache/XAUUSD_D1.parquet')

chop_range = ("2026-03-02", "2026-05-29")
trend_range = ("2026-08-06", "2026-09-02")

print("--- DATA RANGES ---")
print("Chop M15 bars:", len(m15.loc[chop_range[0]:chop_range[1]]))
print("Trend M15 bars:", len(m15.loc[trend_range[0]:trend_range[1]]))

for name, (start, end) in [("CHOP (Mar-May 2026)", chop_range), ("TREND (Aug 2026)", trend_range)]:
    print(f"\n==================== {name} ====================")
    for tf_name, tf_df in [("D1", d1), ("H4", h4), ("H1", h1), ("M15", m15)]:
        sub_df = tf_df.loc[:end]
        adx_df = ta.adx(sub_df['high'], sub_df['low'], sub_df['close'], length=14)
        adx_col = [c for c in adx_df.columns if c.startswith("ADX_")][0]
        sub_adx = adx_df.loc[start:end, adx_col].dropna()
        
        mean_adx = sub_adx.mean()
        median_adx = sub_adx.median()
        pct_below_20 = (sub_adx < 20).mean() * 100
        pct_below_22 = (sub_adx < 22).mean() * 100
        pct_below_25 = (sub_adx < 25).mean() * 100
        pct_above_25 = (sub_adx >= 25).mean() * 100
        
        print(f"[{tf_name}] Mean ADX: {mean_adx:.2f} | Median: {median_adx:.2f} | <20: {pct_below_20:.1f}% | <25: {pct_below_25:.1f}% | >=25: {pct_above_25:.1f}%")
