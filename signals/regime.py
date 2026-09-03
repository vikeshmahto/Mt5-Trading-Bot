"""
Market Regime Detection Module using ADX and Multi-Timeframe Trend vs Chop Classifier.

Calculates directional strength and classifies regimes strictly without look-ahead:
- 'trending': High directional momentum, trend-following setups thrive (ADX >= 25)
- 'choppy': Low directional momentum, mean-reverting / consolidation (ADX < 20 or D1 < 22)
- 'transitional': Market building momentum or consolidating (20 <= ADX < 25)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict

import numpy as np
import pandas as pd
import pandas_ta as ta

from core.logger import get_logger

log = get_logger("signals.regime")


class MarketRegime(str, Enum):
    TRENDING = "trending"
    CHOPPY = "choppy"
    TRANSITIONAL = "transitional"


@dataclass
class TimeframeRegime:
    timeframe: str
    regime: MarketRegime
    adx: float
    dmp: float
    dmn: float


@dataclass
class MarketRegimeReport:
    symbol: str
    timestamp: Optional[pd.Timestamp]
    composite_regime: MarketRegime
    tf_regimes: Dict[str, TimeframeRegime]
    is_choppy: bool
    is_trending: bool


def calculate_adx_series(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """
    Calculate ADX, +DI (DMP), -DI (DMN) for a DataFrame.
    Returns DataFrame with columns ['ADX', 'DMP', 'DMN'].
    """
    if len(df) < length + 1:
        return pd.DataFrame(
            {"ADX": np.nan, "DMP": np.nan, "DMN": np.nan},
            index=df.index,
        )

    try:
        adx_df = ta.adx(df["high"], df["low"], df["close"], length=length)
        adx_col = [c for c in adx_df.columns if c.startswith("ADX_")][0]
        dmp_col = [c for c in adx_df.columns if c.startswith("DMP_")][0]
        dmn_col = [c for c in adx_df.columns if c.startswith("DMN_")][0]

        res = pd.DataFrame(
            {
                "ADX": adx_df[adx_col],
                "DMP": adx_df[dmp_col],
                "DMN": adx_df[dmn_col],
            },
            index=df.index,
        )
        return res
    except Exception as e:
        log.warning(f"pandas_ta ADX computation error: {e}")
        return pd.DataFrame(
            {"ADX": np.nan, "DMP": np.nan, "DMN": np.nan},
            index=df.index,
        )


def detect_tf_regime(
    df: pd.DataFrame,
    timeframe: str = "M15",
    adx_period: int = 14,
    trend_threshold: float = 25.0,
    chop_threshold: float = 20.0,
) -> TimeframeRegime:
    """
    Classify regime for a single timeframe at the most recent available bar.
    Strictly causal — computed only from historical bars up to current bar.
    """
    if df.empty or len(df) < adx_period * 2:
        return TimeframeRegime(
            timeframe=timeframe,
            regime=MarketRegime.TRANSITIONAL,
            adx=0.0,
            dmp=0.0,
            dmn=0.0,
        )

    # If already precomputed (e.g. in backtest engine or cached bars), use it directly
    if "adx" in df.columns:
        adx_val = float(df["adx"].iloc[-1]) if pd.notna(df["adx"].iloc[-1]) else 0.0
        dmp_val = float(df["dmp"].iloc[-1]) if "dmp" in df.columns and pd.notna(df["dmp"].iloc[-1]) else 0.0
        dmn_val = float(df["dmn"].iloc[-1]) if "dmn" in df.columns and pd.notna(df["dmn"].iloc[-1]) else 0.0
    else:
        # Use up to last 100 bars of this TF for fast, lookahead-free calculation
        calc_df = df.iloc[-min(100, len(df)) :]
        adx_df = calculate_adx_series(calc_df, length=adx_period)

        last_row = adx_df.iloc[-1]
        adx_val = float(last_row["ADX"]) if pd.notna(last_row["ADX"]) else 0.0
        dmp_val = float(last_row["DMP"]) if pd.notna(last_row["DMP"]) else 0.0
        dmn_val = float(last_row["DMN"]) if pd.notna(last_row["DMN"]) else 0.0

    if adx_val >= trend_threshold:
        regime = MarketRegime.TRENDING
    elif adx_val < chop_threshold:
        regime = MarketRegime.CHOPPY
    else:
        regime = MarketRegime.TRANSITIONAL

    return TimeframeRegime(
        timeframe=timeframe,
        regime=regime,
        adx=adx_val,
        dmp=dmp_val,
        dmn=dmn_val,
    )


def detect_market_regime(
    bars_dict: dict[str, pd.DataFrame],
    symbol: str = "XAUUSD",
    current_ts: Optional[pd.Timestamp] = None,
    adx_period: int = 14,
) -> MarketRegimeReport:
    """
    Evaluate multi-timeframe regime and determine composite market regime.

    Classification Rule:
    - TRENDING: Both D1 and H4 show sustained trend momentum (D1 ADX >= 25 and H4 ADX >= 25).
    - CHOPPY: D1 is in consolidation (D1 ADX < 22) OR H4 is choppy (H4 ADX < 20).
    - TRANSITIONAL: In between (e.g. fresh trend developing or late consolidation).
    """
    tf_regimes: Dict[str, TimeframeRegime] = {}

    for tf in ["D1", "H4", "H1", "M15"]:
        if tf in bars_dict and not bars_dict[tf].empty:
            df = bars_dict[tf]
            if current_ts is not None:
                df = df.loc[:current_ts]
            # Timeframe specific thresholds: D1 threshold is 22 for chop
            chop_thresh = 22.0 if tf == "D1" else 20.0
            tf_regimes[tf] = detect_tf_regime(
                df=df,
                timeframe=tf,
                adx_period=adx_period,
                trend_threshold=25.0,
                chop_threshold=chop_thresh,
            )

    d1_regime = tf_regimes.get("D1")
    h4_regime = tf_regimes.get("H4")

    # Composite evaluation
    if d1_regime and h4_regime:
        d1_adx = d1_regime.adx
        h4_adx = h4_regime.adx

        if d1_adx >= 25.0 and h4_adx >= 25.0:
            composite = MarketRegime.TRENDING
        elif d1_adx < 22.0 or h4_adx < 20.0:
            composite = MarketRegime.CHOPPY
        else:
            composite = MarketRegime.TRANSITIONAL
    elif h4_regime:
        composite = h4_regime.regime
    elif d1_regime:
        composite = d1_regime.regime
    else:
        composite = MarketRegime.TRANSITIONAL

    return MarketRegimeReport(
        symbol=symbol,
        timestamp=current_ts,
        composite_regime=composite,
        tf_regimes=tf_regimes,
        is_choppy=(composite == MarketRegime.CHOPPY),
        is_trending=(composite == MarketRegime.TRENDING),
    )
