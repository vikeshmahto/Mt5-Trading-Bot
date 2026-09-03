"""
scripts/verify_step3.py
───────────────────────
Smoke-test for Step 3: multi-timeframe alignment with no-look-ahead proof.

Tests:
  1. Basic alignment: shapes, columns, coverage
  2. No-look-ahead proof: for sampled M1 bars, verify each HTF bar is
     genuinely a COMPLETED bar (its next bar opens at or before the M1 time)
  3. BarsSnapshot API works correctly
  4. iter_bars() yields consistently

Run:
    python scripts/verify_step3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from data.mt5_client import MT5Client
from data.fetcher import fetch_multi
from data.aligner import align_timeframes

log = get_logger(__name__, level=settings.log_level)

SYMBOL = "XAUUSD"
TIMEFRAMES = ["D1", "H4", "H1", "M15", "M1"]

N_BARS = {
    "D1":  365,
    "H4":  500,
    "H1":  500,
    "M15": 500,
    "M1":  500,
}

TF_PERIOD_MINUTES = {
    "D1":  1440,
    "H4":  240,
    "H1":  60,
    "M15": 15,
    "M1":  1,
}


def main() -> None:
    log.info("=" * 65)
    log.info("STEP 3 — Multi-TF Alignment + No-Look-Ahead Verification")
    log.info("=" * 65)

    with MT5Client():
        log.info("Fetching data …")
        bars = fetch_multi(SYMBOL, TIMEFRAMES, N_BARS, include_open=False)

    # ── Build aligned structure ───────────────────────────────────────────────
    log.info("\nAligning timeframes …")
    aligned = align_timeframes(bars, base_tf="M1")

    log.info("\n" + aligned.coverage_report())

    # ── Shape & column sanity ─────────────────────────────────────────────────
    log.info(f"\nFlat DataFrame shape : {aligned.shape}")
    log.info(f"Columns              : {list(aligned.df.columns)}")
    assert aligned.shape[0] > 0, "Empty aligned DataFrame!"
    for tf in ["D1", "H4", "H1", "M15"]:
        assert f"{tf}_close" in aligned.df.columns, f"Missing column: {tf}_close"
    log.info("✓ All expected HTF columns present")

    # ── No-look-ahead proof ───────────────────────────────────────────────────
    log.info("\n── No-look-ahead verification ──────────────────────────────")
    log.info("For sampled M1 bars, confirm each HTF bar is truly completed:")
    log.info("  Rule: next HTF bar opens at or before the M1 bar time.\n")

    htf_list = ["D1", "H4", "H1", "M15"]
    raw_bars = bars   # original unaligned DataFrames for cross-check

    # Sample 5 evenly-spaced M1 bars from the middle of the data
    sample_indices = [100, 200, 300, 400, 450]
    violations = 0

    for idx in sample_indices:
        if idx >= len(aligned.df):
            continue
        snap = aligned.df.iloc[idx]
        m1_ts = aligned.df.index[idx]
        log.info(f"M1 bar @ {m1_ts}")

        for tf in htf_list:
            col = f"{tf}_open"
            if col not in snap.index or pd.isna(snap[col]):
                log.info(f"  {tf:>4s}: (no data yet)")
                continue

            htf_open_val = snap[col]
            htf_df = raw_bars[tf]

            # Find which HTF bar this value corresponds to
            # Match on open price (should be unique enough for verification)
            matching = htf_df[htf_df["open"].round(2) == round(htf_open_val, 2)]
            if matching.empty:
                log.warning(f"  {tf:>4s}: could not cross-reference bar open={htf_open_val}")
                continue

            htf_bar_ts = matching.index[-1]   # take the most recent match

            # Find the NEXT HTF bar after htf_bar_ts
            later = htf_df[htf_df.index > htf_bar_ts]
            if later.empty:
                log.info(f"  {tf:>4s}: bar @{htf_bar_ts.time()} — no next bar (last in dataset)")
                continue

            next_htf_ts = later.index[0]

            # ✅ No-look-ahead rule: next_htf_ts must be ≤ m1_ts
            ok = next_htf_ts <= m1_ts
            marker = "✓" if ok else "✗ VIOLATION"
            log.info(
                f"  {tf:>4s}: bar @{htf_bar_ts}  "
                f"next_open={next_htf_ts}  m1={m1_ts}  {marker}"
            )
            if not ok:
                violations += 1

        log.info("")

    if violations == 0:
        log.info("✓ No look-ahead violations found in sample")
    else:
        log.error(f"❌ {violations} look-ahead violations detected!")

    # ── BarsSnapshot API ─────────────────────────────────────────────────────
    log.info("── BarsSnapshot API test ────────────────────────────────────")
    first_ts = aligned.df.index[200]
    snap_obj = aligned.snapshot_at(first_ts)
    log.info(f"snapshot_at({first_ts}):")
    log.info(f"  M1  open={snap_obj.m1_series.get('open'):.2f}  "
             f"close={snap_obj.m1_series.get('close'):.2f}")
    for tf in htf_list:
        bar = snap_obj.get(tf)
        if bar is not None:
            log.info(f"  {tf:>4s} open={bar.get('open', float('nan')):.2f}  "
                     f"close={bar.get('close', float('nan')):.2f}")
        else:
            log.info(f"  {tf:>4s}: (no completed bar yet)")

    has_all = snap_obj.has_all(["H4", "H1", "M15"])
    log.info(f"  has_all(['H4','H1','M15']): {has_all}")

    # ── iter_bars() quick test ────────────────────────────────────────────────
    log.info("\n── iter_bars() test ─────────────────────────────────────────")
    count = 0
    for snap in aligned.iter_bars():
        count += 1
    log.info(f"iter_bars() yielded {count:,} snapshots (expected {len(aligned.df):,})")
    assert count == len(aligned.df), "iter_bars count mismatch!"
    log.info("✓ iter_bars() count matches")

    log.info("")
    if violations == 0:
        log.info("✅  Step 3 PASSED — alignment correct, no look-ahead bias.")
    else:
        log.error(f"❌  Step 3 FAILED — {violations} look-ahead violations.")
        sys.exit(1)


if __name__ == "__main__":
    main()
