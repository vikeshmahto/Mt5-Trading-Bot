"""
data/aligner.py
───────────────
Merge multi-timeframe OHLCV DataFrames into a single structure keyed by M1
timestamp, with a strict NO-LOOK-AHEAD guarantee.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS TRICKY
═══════════════════════════════════════════════════════════════════════════════
An H1 bar whose open_time is 13:00 is NOT completed until 14:00 (when the next
H1 bar opens). So for any M1 bar at 13:00–13:59, the correct last-completed H1
bar is the one at 12:00, not 13:00.

Naive approach (wrong): merge_asof(M1, H1, direction='backward')
  → M1 at 13:30 gets H1 at 13:00 (still open!) ❌

Correct approach:
  1. For each HTF, compute "available_from" = next bar's open_time.
     (A bar is available only once the next bar has opened.)
  2. Re-index the HTF DataFrame on "available_from".
  3. merge_asof(M1, shifted_HTF, direction='backward')
     → M1 at 13:30 gets H1 shifted entry whose available_from ≤ 13:30,
       which corresponds to H1 bar at 12:00 ✓

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API
═══════════════════════════════════════════════════════════════════════════════

align_timeframes(bars_dict, base_tf="M1") → AlignedData
    Takes the dict from fetcher.fetch_multi() and returns AlignedData.

AlignedData.df
    Flat pd.DataFrame indexed by M1 timestamp.
    Columns: open/high/low/close/tick_volume for each TF, prefixed.
    E.g.:  M1_open, M1_close, H1_open, H1_close, D1_open, …

AlignedData.iter_bars()
    Generator that yields (timestamp, BarsSnapshot) one M1 bar at a time.
    BarsSnapshot contains a per-TF dict for use by signals/generator.py.

AlignedData.snapshot_at(ts)
    Return BarsSnapshot for a specific M1 timestamp (for backtest engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generator, Iterator, Optional

import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)

# Columns we align from each timeframe (plus tick_volume for reference)
_ALIGN_COLS = ["open", "high", "low", "close", "tick_volume"]


# ── BarsSnapshot ─────────────────────────────────────────────────────────────

@dataclass
class BarsSnapshot:
    """
    A point-in-time view of all timeframes for one M1 bar.
    Contains only COMPLETED bars — no look-ahead.

    Attributes:
        timestamp:   The M1 bar's open time (UTC).
        tf_bars:     dict[tf_string → pd.Series with index=OHLCV columns].
                     Value is None if no completed HTF bar exists yet.
        m1_series:   The current M1 bar's OHLCV as pd.Series.
    """
    timestamp: pd.Timestamp
    tf_bars: dict[str, Optional[pd.Series]]
    m1_series: pd.Series

    def get(self, tf: str) -> Optional[pd.Series]:
        """Return the latest completed bar for the given timeframe, or None."""
        return self.tf_bars.get(tf)

    def has_all(self, timeframes: list[str]) -> bool:
        """Return True only if all requested TFs have at least one completed bar."""
        return all(self.tf_bars.get(tf) is not None for tf in timeframes)


# ── AlignedData ───────────────────────────────────────────────────────────────

@dataclass
class AlignedData:
    """
    Multi-timeframe data aligned to the base (M1) timeframe with no look-ahead.

    Built by align_timeframes(). Consumed by backtest/engine.py and
    execution/live_runner.py.
    """
    df: pd.DataFrame                          # flat aligned DataFrame
    base_tf: str                              # "M1"
    htf_list: list[str]                       # ["D1", "H4", "H1", "M15"]
    _all_tfs: list[str] = field(repr=False)   # base_tf + htf_list

    def snapshot_at(self, ts: pd.Timestamp) -> BarsSnapshot:
        """
        Return a BarsSnapshot for the M1 bar at `ts`.

        Raises KeyError if `ts` is not in the aligned DataFrame.
        """
        if ts not in self.df.index:
            raise KeyError(f"Timestamp {ts} not found in aligned data.")
        row = self.df.loc[ts]
        return self._row_to_snapshot(ts, row)

    def iter_bars(self) -> Generator[BarsSnapshot, None, None]:
        """
        Yield one BarsSnapshot per M1 bar, in chronological order.
        Use this in the backtest engine to replay history bar-by-bar.
        """
        for ts, row in self.df.iterrows():
            yield self._row_to_snapshot(ts, row)

    def _row_to_snapshot(self, ts: pd.Timestamp, row: pd.Series) -> BarsSnapshot:
        """Convert a single aligned row into a typed BarsSnapshot."""
        tf_bars: dict[str, Optional[pd.Series]] = {}

        # Base TF (M1) is always present
        m1_cols = [c for c in row.index if c.startswith(f"{self.base_tf}_")]
        m1_series = row[m1_cols].rename(
            index=lambda c: c[len(self.base_tf) + 1:]  # strip "M1_" prefix
        )

        # Higher TFs
        for tf in self.htf_list:
            prefix = f"{tf}_"
            tf_cols = [c for c in row.index if c.startswith(prefix)]
            if not tf_cols:
                tf_bars[tf] = None
                continue
            vals = row[tf_cols]
            if vals.isna().all():
                tf_bars[tf] = None
            else:
                tf_bars[tf] = vals.rename(
                    index=lambda c: c[len(prefix):]   # strip "H1_" etc.
                )

        return BarsSnapshot(
            timestamp=ts,
            tf_bars=tf_bars,
            m1_series=m1_series,
        )

    @property
    def shape(self) -> tuple[int, int]:
        return self.df.shape

    def coverage_report(self) -> str:
        """Human-readable summary of how many M1 bars have each HTF populated."""
        lines = [f"AlignedData — {len(self.df):,} M1 bars"]
        lines.append(f"  Range: {self.df.index[0]}  →  {self.df.index[-1]}")
        for tf in self.htf_list:
            prefix = f"{tf}_close"
            if prefix in self.df.columns:
                non_null = self.df[prefix].notna().sum()
                pct = non_null / len(self.df) * 100
                lines.append(f"  {tf:>4s}: {non_null:>6,} / {len(self.df):,} rows filled ({pct:.1f}%)")
        return "\n".join(lines)


# ── Main public function ──────────────────────────────────────────────────────

def align_timeframes(
    bars_dict: dict[str, pd.DataFrame],
    base_tf: str = "M1",
) -> AlignedData:
    """
    Merge multi-TF DataFrames into a no-look-ahead aligned structure.

    Args:
        bars_dict:   Output of fetcher.fetch_multi().
                     Keys are TF strings ("D1", "H4", "H1", "M15", "M1").
                     Values are DataFrames with UTC DatetimeIndex.
        base_tf:     The finest-grained (driver) timeframe. Default "M1".

    Returns:
        AlignedData with .df, .iter_bars(), .snapshot_at()

    Raises:
        ValueError:  If base_tf is missing or any DataFrame is empty.
    """
    if base_tf not in bars_dict:
        raise ValueError(f"Base timeframe '{base_tf}' not found in bars_dict keys: {list(bars_dict.keys())}")

    base_df = bars_dict[base_tf]
    if base_df.empty:
        raise ValueError(f"Base timeframe '{base_tf}' DataFrame is empty.")

    # All other TFs are higher-timeframes to be aligned
    htf_list = [tf for tf in bars_dict if tf != base_tf and not bars_dict[tf].empty]

    log.info(
        f"Aligning {base_tf} ({len(base_df):,} bars) "
        f"against HTFs: {htf_list}"
    )

    # ── Step 1: Prefix the base TF columns ───────────────────────────────────
    base_cols = [c for c in _ALIGN_COLS if c in base_df.columns]
    aligned = base_df[base_cols].copy()
    aligned.columns = [f"{base_tf}_{c}" for c in base_cols]

    # ── Step 2: For each HTF, shift index → then merge_asof ──────────────────
    for tf in htf_list:
        htf_df = bars_dict[tf]
        shifted = _shift_htf_to_available_time(htf_df, tf)

        if shifted.empty:
            log.warning(f"  {tf}: nothing to align after shifting — skipped.")
            continue

        # merge_asof: for each M1 timestamp, find the latest HTF row
        # whose "available_from" index ≤ M1 timestamp (backward fill)
        aligned = pd.merge_asof(
            aligned.reset_index(),      # M1 timestamps as a column
            shifted.reset_index(),      # HTF timestamps as a column
            on="timestamp",
            direction="backward",
            suffixes=("", f"_{tf}"),    # shouldn't collide due to prefixing
        ).set_index("timestamp")

        log.info(
            f"  {tf:>4s}: merged {len(shifted):,} shifted bars — "
            f"coverage {shifted.index[0].date()} → {shifted.index[-1].date()}"
        )

    # ── Step 3: Sort index (should already be sorted) ────────────────────────
    aligned.sort_index(inplace=True)

    log.info(f"Alignment complete: {aligned.shape[0]:,} rows × {aligned.shape[1]} columns")

    return AlignedData(
        df=aligned,
        base_tf=base_tf,
        htf_list=htf_list,
        _all_tfs=[base_tf] + htf_list,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _shift_htf_to_available_time(
    htf_df: pd.DataFrame,
    tf: str,
) -> pd.DataFrame:
    """
    Re-index a HTF DataFrame so each bar's index becomes the timestamp
    at which that bar becomes AVAILABLE (i.e., when the next bar opens).

    Example for H1:
      Original:  13:00 → {open=X, high=Y, …}   (bar still open until 14:00)
      Shifted:   14:00 → {open=X, high=Y, …}   (now visible at 14:00 onward)

    This means a merge_asof with M1 at 13:30 will NOT pick up the 13:00 bar
    (because it's keyed at 14:00, which is > 13:30).  ✓ No look-ahead.

    The LAST row of the original HTF is dropped: its close time is unknown
    (it may still be the currently open bar). Since fetcher.py already drops
    the open bar, the last row is the most recently completed bar — but we
    cannot know when the NEXT bar will open, so we conservatively drop it.
    """
    # Select only the columns we want
    cols = [c for c in _ALIGN_COLS if c in htf_df.columns]
    df = htf_df[cols].copy()

    # Compute "available_from" = next bar's open time
    next_open_times = df.index.to_series().shift(-1)   # NaT for the last row

    # Drop the last row (we can't know its available_from without a future bar)
    df = df.iloc[:-1].copy()
    available_from = next_open_times.iloc[:-1]

    # Re-index on available_from times
    df.index = pd.DatetimeIndex(available_from.values, tz="UTC")
    df.index.name = "timestamp"

    # Prefix columns with the TF name
    df.columns = [f"{tf}_{c}" for c in cols]

    return df
