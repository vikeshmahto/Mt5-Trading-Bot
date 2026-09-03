import pandas as pd
import numpy as np
import pandas_ta as ta

m15 = pd.read_parquet('data/cache/XAUUSD_M15.parquet')
h1 = pd.read_parquet('data/cache/XAUUSD_H1.parquet')
h4 = pd.read_parquet('data/cache/XAUUSD_H4.parquet')
d1 = pd.read_parquet('data/cache/XAUUSD_D1.parquet')

# Precompute causal indicators (strictly rolling up to bar t, no look-ahead)
for df in [d1, h4, h1, m15]:
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    adx_col = [c for c in adx_df.columns if c.startswith("ADX_")][0]
    df['adx'] = adx_df[adx_col]
    # 20-bar Efficiency Ratio
    tr = np.maximum(df['high'] - df['low'], 
                    np.maximum(abs(df['high'] - df['close'].shift(1)),
                               abs(df['low'] - df['close'].shift(1))))
    sum_tr = tr.rolling(20).sum()
    net_move = abs(df['close'] - df['close'].shift(20))
    df['er_20'] = net_move / sum_tr.replace(0, np.nan)

chop_range = ("2026-03-02", "2026-05-29")
trend_range = ("2026-08-06", "2026-09-02")

def evaluate_classifier(name, classify_row_func):
    print(f"\n==================================================")
    print(f"Testing Classifier: {name}")
    print(f"==================================================")
    for period_name, (start, end) in [("CHOP (Mar-May 2026)", chop_range), ("TREND (Aug 2026)", trend_range)]:
        sub_m15 = m15.loc[start:end]
        
        # Align HTF metrics to each M15 timestamp using asof / merge_asof (strictly past data)
        merged = pd.merge_asof(sub_m15[[]], d1[['adx', 'er_20']], left_index=True, right_index=True, suffixes=('', '_d1'))
        merged.rename(columns={'adx': 'adx_d1', 'er_20': 'er_d1'}, inplace=True)
        merged = pd.merge_asof(merged, h4[['adx', 'er_20']], left_index=True, right_index=True)
        merged.rename(columns={'adx': 'adx_h4', 'er_20': 'er_h4'}, inplace=True)
        merged = pd.merge_asof(merged, h1[['adx']], left_index=True, right_index=True)
        merged.rename(columns={'adx': 'adx_h1'}, inplace=True)
        merged['adx_m15'] = sub_m15['adx']
        
        labels = merged.apply(classify_row_func, axis=1)
        counts = labels.value_counts(normalize=True) * 100
        print(f"\n{period_name} ({len(labels)} M15 bars):")
        for k in ["trending", "transitional", "choppy"]:
            print(f"  {k:12s}: {counts.get(k, 0.0):5.1f}%")

# Option 1: D1 ADX
def opt1(row):
    adx = row['adx_d1']
    if pd.isna(adx): return "transitional"
    if adx >= 25: return "trending"
    elif adx < 22: return "choppy"
    else: return "transitional"

# Option 2: H4 ADX
def opt2(row):
    adx = row['adx_h4']
    if pd.isna(adx): return "transitional"
    if adx >= 25: return "trending"
    elif adx < 20: return "choppy"
    else: return "transitional"

# Option 3: D1 + H4 Composite ADX
def opt3(row):
    d1_adx, h4_adx = row['adx_d1'], row['adx_h4']
    if pd.isna(d1_adx) or pd.isna(h4_adx): return "transitional"
    if d1_adx >= 25 and h4_adx >= 25:
        return "trending"
    elif d1_adx < 22 or h4_adx < 20:
        return "choppy"
    else:
        return "transitional"

# Option 4: D1/H4 ADX + D1 Efficiency Ratio
def opt4(row):
    d1_adx, h4_adx, er = row['adx_d1'], row['adx_h4'], row['er_d1']
    if pd.isna(d1_adx) or pd.isna(h4_adx): return "transitional"
    # If D1 is in a range (efficiency low or D1 ADX low) -> choppy
    if er < 0.28 or d1_adx < 22:
        return "choppy"
    elif d1_adx >= 25 and h4_adx >= 25:
        return "trending"
    else:
        return "transitional"

evaluate_classifier("Option 1: D1 ADX (>=25 trend, <22 chop)", opt1)
evaluate_classifier("Option 2: H4 ADX (>=25 trend, <20 chop)", opt2)
evaluate_classifier("Option 3: D1 + H4 Composite ADX", opt3)
evaluate_classifier("Option 4: D1/H4 ADX + D1 Efficiency Ratio", opt4)
