"""
data/fetcher.py
───────────────
Pull OHLCV bars from MT5 for one or more timeframes.

Key design decisions:
  - Returns plain pandas DataFrames with a proper DatetimeIndex (UTC).
  - No look-ahead: we only fetch *completed* bars — the currently open bar
    is excluded by default (include_open=False).
  - MT5 timeframe constants are mapped from human-readable strings:
      "M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"

Public API:
    fetch_bars(symbol, timeframe, n_bars, include_open=False) -> pd.DataFrame
    fetch_multi(symbol, timeframes, n_bars_per_tf, include_open=False)
        -> dict[str, pd.DataFrame]
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)

# ── MT5 timeframe constant map ────────────────────────────────────────────────
TF_MAP: dict[str, int] = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
    "W1":  mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

# Columns we keep from the raw MT5 array
_OHLCV_COLS = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]


class FetchError(RuntimeError):
    """Raised when MT5 returns no data or an error."""


def fetch_bars(
    symbol: str,
    timeframe: str,
    n_bars: int = 500,
    include_open: bool = False,
    from_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Fetch up to `n_bars` completed OHLCV bars for `symbol` on `timeframe`.

    Args:
        symbol:       MT5 symbol string, e.g. "XAUUSD"
        timeframe:    String key from TF_MAP, e.g. "H1"
        n_bars:       Number of bars to request (we add 1 internally if
                      trimming the open bar)
        include_open: If False (default), the currently-open (incomplete) bar
                      is dropped. Always set to False for signal generation.
        from_date:    UTC datetime to fetch from. Defaults to now.

    Returns:
        pd.DataFrame with DatetimeIndex (UTC) and columns:
            open, high, low, close, tick_volume, spread, real_volume

    Raises:
        ValueError:  Unknown timeframe string.
        FetchError:  MT5 returned no data.
    """
    if timeframe not in TF_MAP:
        raise ValueError(
            f"Unknown timeframe '{timeframe}'. Valid: {list(TF_MAP.keys())}"
        )

    tf_const = TF_MAP[timeframe]

    # Request one extra bar so we can drop the open candle if needed
    request_count = n_bars + 1 if not include_open else n_bars

    if from_date is not None:
        rates = mt5.copy_rates_from(symbol, tf_const, from_date, request_count)
    else:
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, request_count)

    if rates is None or len(rates) == 0:
        err = mt5.last_error()
        raise FetchError(
            f"No data returned for {symbol} {timeframe}. "
            f"MT5 error: {err}. Is the symbol available on your broker?"
        )

    df = _rates_to_dataframe(rates)

    # Drop the currently open (incomplete) bar — it's the last row
    if not include_open and len(df) > 0:
        df = df.iloc[:-1]

    # Trim to exactly n_bars (oldest bars are dropped if we got more)
    if len(df) > n_bars:
        df = df.iloc[-n_bars:]

    log.debug(
        f"Fetched {len(df)} bars | {symbol} {timeframe} | "
        f"{df.index[0]} → {df.index[-1]}"
    )
    return df


def fetch_multi(
    symbol: str,
    timeframes: list[str],
    n_bars_per_tf: dict[str, int] | int = 500,
    include_open: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Fetch multiple timeframes for a single symbol in one call.

    Args:
        symbol:          MT5 symbol, e.g. "XAUUSD"
        timeframes:      List of TF strings, e.g. ["D1", "H4", "H1", "M15", "M1"]
        n_bars_per_tf:   Either a single int (same for all TFs) or a dict
                         mapping TF → count.
        include_open:    Passed through to fetch_bars().

    Returns:
        dict mapping timeframe string → DataFrame
    """
    if isinstance(n_bars_per_tf, int):
        counts = {tf: n_bars_per_tf for tf in timeframes}
    else:
        counts = n_bars_per_tf

    result: dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        n = counts.get(tf, 500)
        try:
            df = fetch_bars(symbol, tf, n_bars=n, include_open=include_open)
            result[tf] = df
            log.info(
                f"  {symbol} {tf:>4s}: {len(df):>5d} bars | "
                f"{df.index[0].date()} → {df.index[-1].date()}"
            )
        except FetchError as exc:
            log.error(f"  {symbol} {tf}: FAILED — {exc}")
            result[tf] = pd.DataFrame()   # empty placeholder — callers should check

    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _rates_to_dataframe(rates: np.ndarray) -> pd.DataFrame:
    """
    Convert the raw structured numpy array from mt5.copy_rates_* into a
    clean DataFrame with a UTC DatetimeIndex.
    """
    df = pd.DataFrame(rates)

    # MT5 returns 'time' as UNIX seconds (UTC)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    df.index.name = "timestamp"

    # Keep only the OHLCV columns that exist in this response
    existing_cols = [c for c in _OHLCV_COLS if c in df.columns]
    df = df[existing_cols]

    # Ensure standard float types
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = df[col].astype(float)

    return df
