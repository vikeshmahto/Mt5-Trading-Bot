"""
signals/generator.py
────────────────────
Core signal generation function — the ONLY place where SMC logic is assembled
into a trade Signal.  Called identically by both backtest/engine.py and
execution/live_runner.py.

═══════════════════════════════════════════════════════════════════════════════
DESIGN RULES  (enforced by the architecture)
═══════════════════════════════════════════════════════════════════════════════
  1. PURE FUNCTION — no I/O, no DB access, no order calls, no globals mutated.
  2. DETERMINISTIC — same bars_dict always produces the same output.
  3. SINGLE ENTRY POINT — generate_signal() is the ONLY public function.
     Backtest and live code both call this; signal logic is never duplicated.

═══════════════════════════════════════════════════════════════════════════════
SIGNAL GENERATION LOGIC  (SMC multi-TF cascade)
═══════════════════════════════════════════════════════════════════════════════

  STEP 1 — Bias filter (D1 / H4 / H1)
    Need ≥ 2 of 3 bias timeframes aligned to establish directional bias.
    D1 carries the most weight; if D1 is neutral → return None.

  STEP 2 — Setup detection (H1 + M15)
    For the trade direction:
      • Find the most recent UNMITIGATED OrderBlock on H1 or M15.
      • Find the most recent UNFILLED FVG on H1 or M15.
      • Find a recent liquidity sweep that confirms the direction.

  STEP 3 — Entry trigger (M1)
    The trigger fires when the latest completed M1 bar's price is:
      a) Inside / touching the OB zone, OR
      b) Inside / touching the FVG zone,
    AND the M1 bar itself shows a reversal character
    (close is in the direction of the trade).

  STEP 4 — SL / TP
    Long:   SL = OB.low  - sl_buffer   TP = entry + risk * target_rr
    Short:  SL = OB.high + sl_buffer   TP = entry - risk * target_rr
    If no OB → use recent swing low/high as SL reference.

  STEP 5 — Confluence score (0–100)
    D1 aligned:           +20
    H4 aligned:           +15
    H1 aligned:           +15  (subtotal: up to +50 from bias)
    Recent sweep (≤10 bars ago on M15): +20
    Unmitigated OB found: +20
    FVG confluence:       +10
    OB + FVG overlap:      +5 bonus (total cap: 100)

  Return Signal if score ≥ min_score AND R:R ≥ min_rr.
  Return None otherwise.

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API
═══════════════════════════════════════════════════════════════════════════════

generate_signal(
    bars_dict        : dict[str, pd.DataFrame],
    symbol           : str,
    instrument_config: InstrumentConfig,
    risk_config      : RiskConfig,
) -> Optional[Signal]
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from config.settings import InstrumentConfig, RiskConfig
from core.logger import get_logger
from core.types import (
    Bias, BiasResult, Direction,
    FairValueGap, LiquiditySweep, OrderBlock,
    Signal, SignalType,
)
from signals.bias import get_multi_tf_bias
from signals.fvg import detect_fvgs, get_fresh_fvgs
from signals.liquidity_sweep import detect_liquidity_sweeps, get_recent_sweeps
from signals.order_blocks import detect_order_blocks, get_unmitigated_obs
from signals.regime import detect_market_regime, MarketRegime

log = get_logger(__name__)

# ── Scoring weights ───────────────────────────────────────────────────────────
_SCORE_D1_BIAS      = 20
_SCORE_H4_BIAS      = 15
_SCORE_H1_BIAS      = 15
_SCORE_SWEEP        = 20
_SCORE_OB           = 20
_SCORE_FVG          = 10
_SCORE_OB_FVG_BONUS  = 5   # extra for OB + FVG confluence at same zone

# How many M15 bars back a sweep is still "recent" to count for scoring
_SWEEP_RECENCY_BARS = 10

# Stop-loss buffer below/above OB in price points (adjusted per instrument)
_DEFAULT_SL_BUFFER = 1.0   # override with config if needed

# If no OB found, how many bars back to look for a swing point as SL reference
_SWING_SL_LOOKBACK = 5

# ── Per-instrument minimum SL distances (Step 10: anti-micro-stop filter) ────
# These are module-level so sensitivity tests can override them before engine.run().
# e.g.:  import signals.generator as gen; gen._BTCUSD_MIN_SL_PTS = 500.0
_BTCUSD_MIN_SL_PTS = 500.0    # Step 15 optimization: 500 pts prevents commission drag
_XAUUSD_MIN_SL_PTS = 1.50     # 1.5 pts on Gold
_EURUSD_MIN_SL_PTS = 0.00060  # 6 pips on EURUSD


# ── Main public function ──────────────────────────────────────────────────────

def generate_signal(
    bars_dict: dict[str, pd.DataFrame],
    symbol: str = "XAUUSD",
    instrument_config: Optional[InstrumentConfig] = None,
    risk_config: Optional[RiskConfig] = None,
) -> Optional[Signal]:
    """
    Analyse multi-timeframe bars and return a Signal if all conditions align.

    Args:
        bars_dict:         dict[tf_string → OHLCV DataFrame].
                           Expected keys: "D1", "H4", "H1", "M15", "M1".
                           Missing keys are tolerated (some scoring disabled).
        symbol:            MT5 symbol string, e.g. "XAUUSD".
        instrument_config: InstrumentConfig from settings (for R:R, target pts).
        risk_config:       RiskConfig from settings (for min_score, min_rr).

    Returns:
        Signal if all conditions met, None otherwise.
        PURE — no side effects.
    """
    # ── Defaults when called without config (e.g., from tests) ───────────────
    from config.settings import settings
    inst = instrument_config or settings.get_instrument(symbol)
    risk = risk_config       or settings.risk

    min_score = risk.scoring.min_score_to_trade
    min_rr    = risk.scoring.min_rr_ratio

    # ── Extract per-TF DataFrames ─────────────────────────────────────────────
    d1_df  = bars_dict.get("D1",  pd.DataFrame())
    h4_df  = bars_dict.get("H4",  pd.DataFrame())
    h1_df  = bars_dict.get("H1",  pd.DataFrame())
    m15_df = bars_dict.get("M15", pd.DataFrame())
    m1_df  = bars_dict.get("M1",  pd.DataFrame())

    if m1_df.empty:
        log.debug(f"[{symbol}] generate_signal: M1 DataFrame empty — skip")
        return None

    # ── STEP 0: Market Regime Gate (Hard Filter) ─────────────────────────────
    regime_report = detect_market_regime(bars_dict, symbol=symbol)
    if regime_report.is_choppy:
        d1_adx = regime_report.tf_regimes["D1"].adx if "D1" in regime_report.tf_regimes else 0.0
        h4_adx = regime_report.tf_regimes["H4"].adx if "H4" in regime_report.tf_regimes else 0.0
        log.debug(
            f"[{symbol}] Market regime is CHOPPY "
            f"(D1_adx={d1_adx:.1f}, H4_adx={h4_adx:.1f}) — suppress new entry"
        )
        return None

    # ── STEP 1: Bias ─────────────────────────────────────────────────────────
    bias_tfs = {
        k: bars_dict[k].iloc[-min(300, len(bars_dict[k])):]
        for k in ["D1", "H4", "H1"]
        if k in bars_dict and not bars_dict[k].empty
    }
    bias_results = get_multi_tf_bias(bias_tfs, timeframes=list(bias_tfs.keys()))

    d1_result = bias_results.get("D1")
    h4_result = bias_results.get("H4")
    h1_result = bias_results.get("H1")

    d1_bias = d1_result.bias if d1_result else Bias.NEUTRAL
    h4_bias = h4_result.bias if h4_result else Bias.NEUTRAL
    h1_bias = h1_result.bias if h1_result else Bias.NEUTRAL

    bullish_count = sum(b == Bias.BULLISH for b in [d1_bias, h4_bias, h1_bias])
    bearish_count = sum(b == Bias.BEARISH for b in [d1_bias, h4_bias, h1_bias])

    is_counter_trend = False

    # ── Explicit Bias Rules ──────────────────────────────────────────────────
    # Rule 1: Bullish Direction
    if bullish_count >= 2:
        direction = Direction.BULLISH
        if d1_bias == Bias.BEARISH:
            is_counter_trend = True  # H4 + H1 bullish against D1 bearish
    # Rule 2: Bearish Direction
    elif bearish_count >= 2:
        direction = Direction.BEARISH
        if d1_bias == Bias.BULLISH:
            is_counter_trend = True  # H4 + H1 bearish pullback against D1 bullish
    else:
        log.debug(f"[{symbol}] No bias confluence (bull={bullish_count} bear={bearish_count}) — skip")
        return None

    # ── STEP 2: Setup detection (H1 + M15) ───────────────────────────────────
    setup_ob:    Optional[OrderBlock]     = None
    setup_fvg:   Optional[FairValueGap]  = None
    setup_sweep: Optional[LiquiditySweep] = None
    setup_tf:    str                      = ""

    # Detect on both H1 and M15; prefer M15 (more precise entry)
    for tf_label, tf_df in [("M15", m15_df), ("H1", h1_df)]:
        if tf_df.empty or len(tf_df) < 5:
            continue

        detection_df = tf_df.iloc[-min(300, len(tf_df)):]

        ob_dir = direction
        obs    = detect_order_blocks(detection_df, timeframe=tf_label)
        fresh_obs = get_unmitigated_obs(obs, direction=ob_dir, n_recent=5)
        if fresh_obs and setup_ob is None:
            setup_ob = fresh_obs[-1]   # most recent unmitigated OB
            setup_tf = tf_label

        fvgs      = detect_fvgs(detection_df, timeframe=tf_label)
        fresh_fvgs = get_fresh_fvgs(fvgs, direction=ob_dir, n_recent=5)
        if fresh_fvgs and setup_fvg is None:
            setup_fvg = fresh_fvgs[-1]
            if not setup_tf:
                setup_tf = tf_label

        sweeps = detect_liquidity_sweeps(detection_df, timeframe=tf_label)
        dir_sweeps = get_recent_sweeps(sweeps, n=3, direction=direction)
        if dir_sweeps and setup_sweep is None:
            setup_sweep = dir_sweeps[-1]
            if not setup_tf:
                setup_tf = tf_label

    # Need at least an OB or FVG to have a valid structural zone
    if setup_ob is None and setup_fvg is None:
        log.debug(f"[{symbol}] No OB or FVG found for {direction.value} (standalone sweeps filtered) — skip")
        return None

    # ── STEP 3: Entry trigger (M1) ────────────────────────────────────────────
    m1_last = m1_df.iloc[-1]
    m1_ts   = m1_df.index[-1]
    m1_high = float(m1_last["high"])
    m1_low  = float(m1_last["low"])
    m1_close = float(m1_last["close"])
    m1_open  = float(m1_last["open"])

    in_ob  = _price_in_zone(m1_low, m1_high, setup_ob)   if setup_ob  else False
    in_fvg = _price_in_zone(m1_low, m1_high, setup_fvg)  if setup_fvg else False

    # Check sweep reversal confirmation if a sweep occurred
    is_sweep_reversal = False
    if setup_sweep is not None:
        if not m15_df.empty:
            recent_idx = m15_df.index[-min(8, len(m15_df))]
            if setup_sweep.timestamp >= recent_idx:
                if direction == Direction.BULLISH and m1_close >= setup_sweep.swept_level:
                    is_sweep_reversal = True
                elif direction == Direction.BEARISH and m1_close <= setup_sweep.swept_level:
                    is_sweep_reversal = True

    # Must be in an active OB or FVG zone (no naked sweeps)
    if not in_ob and not in_fvg:
        log.debug(
            f"[{symbol}] M1 price [{m1_low:.2f}–{m1_high:.2f}] "
            f"not in OB or FVG zone — skip"
        )
        return None

    # M1 candle must show reversal character (close in trade direction)
    if direction == Direction.BULLISH and m1_close < m1_open:
        log.debug(f"[{symbol}] M1 bearish close in bull zone — skip")
        return None
    if direction == Direction.BEARISH and m1_close > m1_open:
        log.debug(f"[{symbol}] M1 bullish close in bear zone — skip")
        return None

    # ── STEP 4: SL / TP ──────────────────────────────────────────────────────
    sl_buffer = inst.pip_value * 2   # 2 pips buffer

    entry_price, stop_loss, take_profit = _calculate_sl_tp(
        direction=direction,
        m1_close=m1_close,
        setup_ob=setup_ob,
        setup_fvg=setup_fvg,
        setup_sweep=setup_sweep,
        in_ob=in_ob,
        in_fvg=in_fvg,
        is_sweep_reversal=is_sweep_reversal,
        m1_df=m1_df,
        sl_buffer=sl_buffer,
        min_rr=min_rr,
        symbol=symbol,
    )

    if entry_price is None:
        log.debug(f"[{symbol}] Could not compute valid SL/TP — skip")
        return None

    risk_pts   = abs(entry_price - stop_loss)
    reward_pts = abs(take_profit - entry_price)
    actual_rr  = reward_pts / risk_pts if risk_pts > 0 else 0.0

    if actual_rr < min_rr:
        log.debug(f"[{symbol}] R:R {actual_rr:.2f} < min {min_rr} — skip")
        return None

    # ── STEP 5: Confluence score (Model A) & Hard Entry Gate (Step 8) ────────
    score = _compute_score(
        direction=direction,
        d1_bias=d1_bias, h4_bias=h4_bias, h1_bias=h1_bias,
        setup_ob=setup_ob, setup_fvg=setup_fvg, setup_sweep=setup_sweep,
        m15_df=m15_df,
        symbol=symbol,
    )

    min_score = 70.0
    max_score = 79.9
    if risk_config and hasattr(risk_config, "scoring") and risk_config.scoring:
        min_score = float(getattr(risk_config.scoring, "min_score_to_trade", 70.0))
        max_score = float(getattr(risk_config.scoring, "max_score_to_trade", 79.9))

    if score < min_score or score > max_score:
        log.debug(f"[{symbol}] Confluence score {score:.1f} outside valid window [{min_score:.1f}, {max_score:.1f}] — skip")
        return None

    # ── Determine signal type ─────────────────────────────────────────────────
    if in_ob and in_fvg:
        sig_type = SignalType.OB_FVG
    elif in_ob:
        sig_type = SignalType.OB_RETEST
    else:
        sig_type = SignalType.FVG_RETEST

    # ── STEP 5B: Setup Quality Filter (Step 9: Restrict Standalone FVG) ───────
    if sig_type == SignalType.FVG_RETEST:
        has_nearby_ob = False
        if setup_ob is not None and setup_fvg is not None:
            zone_span = max(
                setup_ob.high - setup_ob.low,
                setup_fvg.top - setup_fvg.bottom,
                1.0,
            )
            has_nearby_ob = abs(setup_ob.mid - setup_fvg.mid) <= zone_span * 2.5

        has_confirmed_sweep = False
        if setup_sweep is not None:
            if not m15_df.empty:
                recent_thresh = m15_df.index[-min(_SWEEP_RECENCY_BARS, len(m15_df))]
                has_confirmed_sweep = setup_sweep.timestamp >= recent_thresh
            else:
                has_confirmed_sweep = True

        if not has_nearby_ob and not has_confirmed_sweep:
            log.debug(f"[{symbol}] Standalone FVG without nearby OB or sweep confirmation — skip")
            return None

    # ── Build notes ───────────────────────────────────────────────────────────
    ct_tag = " [COUNTER-TREND]" if is_counter_trend else ""
    notes = (
        f"Regime={regime_report.composite_regime.value} | "
        f"Bias: D1={d1_bias.value} H4={h4_bias.value} H1={h1_bias.value}{ct_tag} | "
        f"Type={sig_type.value} | TF={setup_tf} | "
        f"OB={setup_ob is not None} FVG={setup_fvg is not None} "
        f"Sweep={setup_sweep is not None} | score={score:.0f}"
    )

    signal = Signal(
        symbol=symbol,
        direction=direction,
        signal_type=sig_type,
        timestamp=m1_ts,
        entry_price=round(entry_price, 5),
        stop_loss=round(stop_loss, 5),
        take_profit=round(take_profit, 5),
        risk_reward=round(actual_rr, 2),
        confluence_score=round(score, 1),
        d1_bias=d1_result,
        h4_bias=h4_result,
        h1_bias=h1_result,
        trigger_ob=setup_ob,
        trigger_fvg=setup_fvg,
        trigger_sweep=setup_sweep,
        setup_timeframe=setup_tf,
        is_counter_trend=is_counter_trend,
        notes=notes,
    )

    log.info(f"Signal generated: {signal}")
    return signal


# ── Internal helpers ──────────────────────────────────────────────────────────

def _price_in_zone(
    bar_low: float,
    bar_high: float,
    zone,                  # OrderBlock | FairValueGap
    tolerance: float = 0.0,
) -> bool:
    """
    True if the bar's range [bar_low, bar_high] overlaps with the zone.
    Optional tolerance expands the zone by that many points on each side.
    """
    if zone is None:
        return False
    if isinstance(zone, OrderBlock):
        z_low, z_high = zone.low - tolerance, zone.high + tolerance
    else:  # FairValueGap
        z_low, z_high = zone.bottom - tolerance, zone.top + tolerance
    # Overlap if bar_high >= zone_low AND bar_low <= zone_high
    return bar_high >= z_low and bar_low <= z_high


def _calculate_sl_tp(
    direction: Direction,
    m1_close: float,
    setup_ob: Optional[OrderBlock],
    setup_fvg: Optional[FairValueGap],
    setup_sweep: Optional[LiquiditySweep],
    in_ob: bool,
    in_fvg: bool,
    is_sweep_reversal: bool,
    m1_df: pd.DataFrame,
    sl_buffer: float,
    min_rr: float,
    symbol: str = "XAUUSD",
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Compute (entry, stop_loss, take_profit).
    Anchors SL to the specific zone that triggered the entry.
    Enforces minimum SL distance per instrument to prevent micro-stop commission burn (Step 10).
    """
    entry = m1_close

    # ── SL reference ─────────────────────────────────────────────────────────
    if direction == Direction.BULLISH:
        if in_ob and setup_ob and setup_ob.low < entry:
            sl = setup_ob.low - sl_buffer
        elif in_fvg and setup_fvg and setup_fvg.bottom < entry:
            sl = setup_fvg.bottom - sl_buffer
        elif is_sweep_reversal and setup_sweep and setup_sweep.sweep_low < entry:
            sl = setup_sweep.sweep_low - sl_buffer
        elif setup_ob and setup_ob.low < entry:
            sl = setup_ob.low - sl_buffer
        elif setup_sweep and setup_sweep.sweep_low < entry:
            sl = setup_sweep.sweep_low - sl_buffer
        else:
            # Fallback: recent swing low from M1
            sl = m1_df["low"].iloc[-_SWING_SL_LOOKBACK:].min() - sl_buffer

        tp = entry + (entry - sl) * min_rr

    else:  # BEARISH
        if in_ob and setup_ob and setup_ob.high > entry:
            sl = setup_ob.high + sl_buffer
        elif in_fvg and setup_fvg and setup_fvg.top > entry:
            sl = setup_fvg.top + sl_buffer
        elif is_sweep_reversal and setup_sweep and setup_sweep.sweep_high > entry:
            sl = setup_sweep.sweep_high + sl_buffer
        elif setup_ob and setup_ob.high > entry:
            sl = setup_ob.high + sl_buffer
        elif setup_sweep and setup_sweep.sweep_high > entry:
            sl = setup_sweep.sweep_high + sl_buffer
        else:
            sl = m1_df["high"].iloc[-_SWING_SL_LOOKBACK:].max() + sl_buffer

        tp = entry - (sl - entry) * min_rr

    # Sanity: SL must be on the correct side of entry
    if direction == Direction.BULLISH and sl >= entry:
        return None, None, None
    if direction == Direction.BEARISH and sl <= entry:
        return None, None, None

    # ── Minimum SL Distance Filter (Step 10: Prevent Micro-Stop Commission Burn) ──
    # Read from module-level constants (overridable for sensitivity tests - Step 15)
    import signals.generator as _self_module
    min_sl_dist = 1.0
    if symbol == "BTCUSD":
        min_sl_dist = _self_module._BTCUSD_MIN_SL_PTS
    elif symbol == "XAUUSD":
        min_sl_dist = _self_module._XAUUSD_MIN_SL_PTS
    elif symbol == "EURUSD":
        min_sl_dist = _self_module._EURUSD_MIN_SL_PTS

    current_sl_dist = abs(entry - sl)
    if current_sl_dist < min_sl_dist:
        if direction == Direction.BULLISH:
            sl = entry - min_sl_dist
            tp = entry + (min_sl_dist * min_rr)
        else:
            sl = entry + min_sl_dist
            tp = entry - (min_sl_dist * min_rr)

    return entry, sl, tp


# Instruments that use H4+H1-only HTF scoring (D1 is structural background, not momentum)
_FOREX_INSTRUMENTS = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP"}


def _compute_score(
    direction: Direction,
    d1_bias: Bias,
    h4_bias: Bias,
    h1_bias: Bias,
    setup_ob: Optional[OrderBlock],
    setup_fvg: Optional[FairValueGap],
    setup_sweep: Optional[LiquiditySweep],
    m15_df: pd.DataFrame,
    symbol: str = "",
) -> float:
    """
    Compute confluence score 0-100 using Model A (Inverted HTF weighting - Step 8).
    - 2-of-3 HTF aligned = +45 points (Fresh pullback sweet spot)
    - 3-of-3 HTF aligned = +20 points (Late-stage trend exhaustion penalty)

    Step 13 (EURUSD/Forex): D1 in forex stays aligned for months (structural
    background), so it is excluded from the HTF alignment count. Only H4+H1
    alignment is evaluated. This prevents every forex setup from scoring 80+
    due to persistent D1 alignment masking fresh pullback signals.
    """
    score = 0.0

    # ── Bias scores (Model A: Inverted HTF Weighting) ─────────────────────────
    is_forex = symbol.upper() in _FOREX_INSTRUMENTS

    if is_forex:
        # For forex: only H4 + H1 count (D1 is structural background context only)
        # H4+H1 both aligned = 2-HTF fresh pullback (+45)
        # Only one of H4/H1 aligned = 1-HTF (+0, no meaningful confluence)
        h4_aligned = (h4_bias.value == direction.value)
        h1_aligned = (h1_bias.value == direction.value)
        htf_aligned = int(h4_aligned) + int(h1_aligned)

        if htf_aligned == 2:
            score += 45.0
        # 1 or 0 aligned in H4/H1 = no bias bonus (insufficient confluence)
        # Note: D1 adds no points for forex instruments (Step 13)
    else:
        # Non-forex (Gold, BTC): use full 3-HTF Model A as before
        htf_aligned = 0
        if d1_bias.value == direction.value:
            htf_aligned += 1
        if h4_bias.value == direction.value:
            htf_aligned += 1
        if h1_bias.value == direction.value:
            htf_aligned += 1

        if htf_aligned == 2:
            score += 45.0
        elif htf_aligned == 3:
            score += 20.0

    # ── Zone scores ───────────────────────────────────────────────────────────
    if setup_ob is not None:
        score += _SCORE_OB      # 20

    if setup_fvg is not None:
        score += _SCORE_FVG     # 10

    # OB + FVG bonus (their zones overlap or are very close)
    if setup_ob is not None and setup_fvg is not None:
        ob_mid  = setup_ob.mid
        fvg_mid = setup_fvg.mid
        zone_span = max(
            setup_ob.high - setup_ob.low,
            setup_fvg.top - setup_fvg.bottom,
            1.0,   # prevent division by zero
        )
        if abs(ob_mid - fvg_mid) <= zone_span * 2:
            score += _SCORE_OB_FVG_BONUS  # 5

    # ── Sweep score ───────────────────────────────────────────────────────────
    if setup_sweep is not None:
        # Only award sweep score if it's recent (within last N M15 bars)
        if not m15_df.empty:
            recent_threshold = m15_df.index[-min(_SWEEP_RECENCY_BARS, len(m15_df))]
            if setup_sweep.timestamp >= recent_threshold:
                score += _SCORE_SWEEP     # 20
        else:
            score += _SCORE_SWEEP   # if no M15 data, trust the sweep

    return min(score, 100.0)   # cap at 100
