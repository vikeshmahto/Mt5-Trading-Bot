import pandas as pd
import numpy as np
from app.config import settings


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Pure-pandas ADX implementation (no pandas-ta / numba dependency).
    Returns a Series of ADX values aligned to df's index.
    """
    high = df['high']
    low = df['low']
    close = df['close']

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    dm_pos = high.diff()
    dm_neg = -low.diff()

    dm_pos = dm_pos.where((dm_pos > dm_neg) & (dm_pos > 0), 0.0)
    dm_neg = dm_neg.where((dm_neg > dm_pos) & (dm_neg > 0), 0.0)

    # Smoothed ATR, +DM, -DM using Wilder's smoothing
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    sdm_pos = dm_pos.ewm(alpha=1 / period, adjust=False).mean()
    sdm_neg = dm_neg.ewm(alpha=1 / period, adjust=False).mean()

    # Directional Indicators
    di_pos = 100 * sdm_pos / atr.replace(0, np.nan)
    di_neg = 100 * sdm_neg / atr.replace(0, np.nan)

    # ADX
    dx = (100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan))
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return adx


def detect_regime(df: pd.DataFrame) -> str:
    """
    Classifies the market as 'trending' or 'ranging' using ADX.
    Requires at least 30 bars for a reliable reading.
    Returns 'trending' | 'ranging'.
    """
    if df is None or len(df) < 30:
        return 'ranging'

    adx = _compute_adx(df)
    latest_adx = adx.iloc[-1]

    if pd.isna(latest_adx):
        return 'ranging'

    return 'trending' if latest_adx > settings.ADX_TRENDING_THRESHOLD else 'ranging'
