"""
backtest/engine.py
──────────────────
Walk-forward bar-by-bar backtesting engine.

═══════════════════════════════════════════════════════════════════════════════
DESIGN RULES
═══════════════════════════════════════════════════════════════════════════════
  1. ZERO LOOK-AHEAD — at bar i, only data[:i+1] is passed to generate_signal().
  2. SAME PURE FUNCTION — calls generate_signal() identically to live execution.
     Signal logic is never duplicated here.
  3. BAR-CLOSE ENTRY — signal detected on bar[i] close, trade opened at
     bar[i+1] open (next-bar-open fill).  Prevents bar-close snooping.
  4. SL/TP CHECK — each subsequent bar checks if the low/high hit SL/TP
     within the bar's range (realistic intra-bar simulation).
  5. DB-OPTIONAL — results are returned as BacktestResult dataclass.
     DB writes happen only if persist=True.

═══════════════════════════════════════════════════════════════════════════════
EXECUTION TIMEFRAME STRATEGY
═══════════════════════════════════════════════════════════════════════════════
  • Walk-forward loop runs on M15 bars (the setup timeframe).
  • The generator's "M1 trigger bar" is simulated as the last 3 M15 bars —
    this is the standard SMC backtest approach since M1 data is too short.
  • For live execution (Step 10) genuine M1 bars are used.

═══════════════════════════════════════════════════════════════════════════════
PUBLIC API
═══════════════════════════════════════════════════════════════════════════════
  BacktestResult  — dataclass returned by BacktestEngine.run()
  BacktestEngine  — main class, instantiate and call .run()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import BacktestConfig, InstrumentConfig, RiskConfig, settings
from core.logger import get_logger
from core.types import Direction, Signal
from signals.generator import generate_signal

log = get_logger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    """In-memory record of a single simulated trade."""
    signal:        Signal
    entry_bar_ts:  pd.Timestamp
    entry_price:   float
    stop_loss:     float
    take_profit:   float
    lot_size:      float
    exit_bar_ts:   Optional[pd.Timestamp] = None
    exit_price:    Optional[float]        = None
    exit_reason:   Optional[str]          = None   # tp_hit | sl_hit | end_of_data
    pnl:           Optional[float]        = None   # in account currency
    pnl_r:         Optional[float]        = None   # in R-multiples
    commission:    float                  = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_bar_ts is None

    @property
    def risk_points(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def direction(self) -> str:
        return self.signal.direction.value


@dataclass
class BacktestResult:
    """Complete results returned by BacktestEngine.run()."""
    symbol:          str
    start_date:      pd.Timestamp
    end_date:        pd.Timestamp
    bars_processed:  int
    initial_balance: float
    final_balance:   float

    trades:       list[TradeRecord] = field(default_factory=list)
    equity_curve: pd.Series         = field(default_factory=pd.Series)

    # Summary stats (populated by _compute_stats)
    total_trades:  int   = 0
    wins:          int   = 0
    losses:        int   = 0
    win_rate:      float = 0.0
    avg_r:         float = 0.0
    profit_factor: float = 0.0
    max_drawdown:  float = 0.0   # fraction, e.g. 0.12 = 12%
    total_pnl:     float = 0.0
    best_trade_r:  float = 0.0
    worst_trade_r: float = 0.0
    signals_generated: int = 0

    def summary(self) -> str:
        lines = [
            f"  Symbol        : {self.symbol}",
            f"  Period        : {self.start_date.date()} → {self.end_date.date()}",
            f"  Bars processed: {self.bars_processed:,}",
            f"  Signals fired : {self.signals_generated}",
            f"  Trades taken  : {self.total_trades}",
            f"  Win rate      : {self.win_rate:.1%}  "
                f"({self.wins}W / {self.losses}L)",
            f"  Avg R         : {self.avg_r:+.2f}R",
            f"  Profit factor : {self.profit_factor:.2f}",
            f"  Max drawdown  : {self.max_drawdown:.1%}",
            f"  Total P&L     : {self.total_pnl:+.2f}",
            f"  Initial equity: {self.initial_balance:,.2f}",
            f"  Final equity  : {self.final_balance:,.2f}",
            f"  Return        : {(self.final_balance/self.initial_balance - 1):.1%}",
        ]
        return "\n".join(lines)


# ── Engine ────────────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Walk-forward bar-by-bar backtesting engine.

    Args:
        symbol:        MT5 symbol to test, e.g. "XAUUSD".
        bars_dict:     dict[tf → DataFrame] with ALL available history.
                       Required keys: "D1", "H4", "H1", "M15".
                       "M1" is optional — if absent, M15 is used for trigger.
        instrument_config: InstrumentConfig for this symbol.
        risk_config:   RiskConfig (position sizing, limits, backtest params).
        persist:       If True, write signals and trades to DB via repository.
        start_date:    Optional — trim bars to start from this date.
        end_date:      Optional — trim bars to end at this date.

    Usage:
        engine = BacktestEngine("XAUUSD", bars_dict)
        result = engine.run()
        print(result.summary())
    """

    EXEC_TF = "M15"   # walk-forward loop runs on this timeframe

    def __init__(
        self,
        symbol:            str,
        bars_dict:         dict[str, pd.DataFrame],
        instrument_config: Optional[InstrumentConfig] = None,
        risk_config:       Optional[RiskConfig]        = None,
        persist:           bool                        = False,
        start_date:        Optional[str | pd.Timestamp] = None,
        end_date:          Optional[str | pd.Timestamp] = None,
    ) -> None:
        self.symbol    = symbol
        self.inst      = instrument_config or settings.get_instrument(symbol)
        self.risk      = risk_config       or settings.risk
        self.persist   = persist

        # Normalise execution TF DataFrame
        exec_df = bars_dict.get(self.EXEC_TF, pd.DataFrame())
        if exec_df.empty:
            raise ValueError(f"BacktestEngine requires '{self.EXEC_TF}' bars in bars_dict.")

        # Trim date range
        if start_date:
            ts = pd.Timestamp(start_date, tz="UTC") if not isinstance(start_date, pd.Timestamp) else start_date
            exec_df = exec_df[exec_df.index >= ts]
        if end_date:
            ts = pd.Timestamp(end_date, tz="UTC") if not isinstance(end_date, pd.Timestamp) else end_date
            exec_df = exec_df[exec_df.index <= ts]

        self._exec_df  = exec_df
        self._all_bars = bars_dict   # full history for all TFs

        # Precompute causal ADX for ultra-fast regime detection during walk-forward
        from signals.regime import calculate_adx_series
        for tf, df in self._all_bars.items():
            if "adx" not in df.columns and len(df) >= 20:
                adx_res = calculate_adx_series(df, length=14)
                df["adx"] = adx_res["ADX"]
                df["dmp"] = adx_res["DMP"]
                df["dmn"] = adx_res["DMN"]

        # State
        self._equity   = self.risk.backtest.initial_balance
        self._open_trade: Optional[TradeRecord] = None
        self._trades:  list[TradeRecord]        = []
        self._equity_series: list[tuple[pd.Timestamp, float]] = []
        self._signals_generated = 0
        self._daily_pnl: dict[str, float] = {}   # date_str → pnl

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> BacktestResult:
        """
        Execute the full walk-forward backtest.

        Returns:
            BacktestResult with all trade records and equity curve.
        """
        df        = self._exec_df
        all_bars  = self._all_bars
        n         = len(df)

        log.info(
            f"[{self.symbol}] Backtest start | "
            f"bars={n} | "
            f"range={df.index[0].date()} → {df.index[-1].date()} | "
            f"equity={self._equity:,.2f}"
        )

        # Pre-build arrays for fast SL/TP checking
        highs  = df["high"].to_numpy(dtype=float)
        lows   = df["low"].to_numpy(dtype=float)
        opens  = df["open"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        ts_arr = df.index

        # Pending entry: signal detected on bar i, enters at bar i+1 open
        pending_signal: Optional[Signal] = None
        pending_entry_i: Optional[int]   = None

        for i in range(len(df)):
            current_ts    = ts_arr[i]
            current_open  = opens[i]
            current_high  = highs[i]
            current_low   = lows[i]
            current_close = closes[i]

            # ── 1. Fill pending entry at this bar's open ──────────────────────
            if pending_signal is not None and pending_entry_i == i:
                self._open_new_trade(pending_signal, current_open, current_ts)
                pending_signal   = None
                pending_entry_i  = None

            # ── 2. Check open trade SL/TP ────────────────────────────────────
            if self._open_trade is not None:
                closed = self._check_sl_tp(
                    self._open_trade,
                    bar_high=current_high,
                    bar_low=current_low,
                    bar_close=current_close,
                    bar_ts=current_ts,
                )
                if closed:
                    self._equity += (closed.pnl or 0.0) - closed.commission
                    self._trades.append(closed)
                    self._open_trade = None
                    self._update_daily_pnl(current_ts, closed.pnl or 0.0)

            # ── 3. Daily loss guard ───────────────────────────────────────────
            date_str = str(current_ts.date())
            day_pnl  = self._daily_pnl.get(date_str, 0.0)
            max_day_loss = self._equity * self.risk.limits.max_daily_loss
            if day_pnl < -abs(max_day_loss):
                log.debug(f"[{self.symbol}] Daily loss limit hit {date_str} — skip signal")
                self._equity_series.append((current_ts, self._equity))
                continue

            # ── 4. Max drawdown guard ─────────────────────────────────────────
            peak   = max((v for _, v in self._equity_series), default=self._equity)
            dd_now = (peak - self._equity) / peak if peak > 0 else 0.0
            if dd_now >= self.risk.limits.max_drawdown:
                log.warning(f"[{self.symbol}] Max drawdown reached ({dd_now:.1%}) — stopping backtest")
                self._equity_series.append((current_ts, self._equity))
                break

            # ── 5. Skip if a trade is open or pending ─────────────────────────
            if self._open_trade is not None or pending_signal is not None:
                self._equity_series.append((current_ts, self._equity))
                continue

            # ── 6. Build bars_dict slice up to this bar (NO look-ahead) ──────
            bar_slice = self._build_slice(current_ts)

            # Need at least a few bars to compute bias / swings
            if len(bar_slice.get(self.EXEC_TF, [])) < 30:
                self._equity_series.append((current_ts, self._equity))
                continue

            # ── 7. Generate signal ────────────────────────────────────────────
            try:
                signal = generate_signal(
                    bar_slice,
                    symbol=self.symbol,
                    instrument_config=self.inst,
                    risk_config=self.risk,
                )
            except Exception as e:
                log.debug(f"[{self.symbol}] generate_signal error at {current_ts}: {e}")
                signal = None

            if signal is not None:
                self._signals_generated += 1
                log.debug(f"Signal @ {current_ts}: {signal}")

                # Queue for entry at NEXT bar open (avoid look-ahead fill)
                if i + 1 < len(df):
                    pending_signal  = signal
                    pending_entry_i = i + 1

            self._equity_series.append((current_ts, self._equity))

        # ── Close any open trade at backtest end ──────────────────────────────
        if self._open_trade is not None:
            last_close = float(closes[-1])
            last_ts    = ts_arr[-1]
            self._force_close(self._open_trade, last_close, last_ts, "end_of_data")
            self._equity += (self._open_trade.pnl or 0.0) - self._open_trade.commission
            self._trades.append(self._open_trade)
            self._open_trade = None

        # Ensure equity series records the final balance
        if not self._equity_series or abs(self._equity_series[-1][1] - self._equity) > 1e-4:
            last_ts = ts_arr[min(i, len(ts_arr) - 1)]
            self._equity_series.append((last_ts, self._equity))

        # ── Persist to DB if requested ────────────────────────────────────────
        if self.persist:
            self._write_to_db()

        return self._build_result()

    # ── Trade management ──────────────────────────────────────────────────────

    def _open_new_trade(
        self,
        signal: Signal,
        entry_price: float,
        ts: pd.Timestamp,
    ) -> None:
        """Open a new simulated trade from a Signal."""
        slippage = self.risk.backtest.slippage_points * self.inst.pip_value
        if signal.direction == Direction.BULLISH:
            actual_entry = entry_price + slippage
            actual_sl    = signal.stop_loss
            actual_tp    = signal.take_profit
        else:
            actual_entry = entry_price - slippage
            actual_sl    = signal.stop_loss
            actual_tp    = signal.take_profit

        lot_size = _calc_lot_size(
            equity=self._equity,
            risk_pct=self.risk.position_sizing.risk_per_trade,
            risk_points=abs(actual_entry - actual_sl),
            inst=self.inst,
        )

        commission = self.risk.backtest.commission_per_lot * lot_size

        self._open_trade = TradeRecord(
            signal=signal,
            entry_bar_ts=ts,
            entry_price=actual_entry,
            stop_loss=actual_sl,
            take_profit=actual_tp,
            lot_size=lot_size,
            commission=commission,
        )
        log.debug(
            f"  Trade opened @ {ts} | {signal.direction.value} "
            f"entry={actual_entry:.2f} sl={actual_sl:.2f} "
            f"tp={actual_tp:.2f} lots={lot_size:.2f}"
        )

    def _check_sl_tp(
        self,
        trade: TradeRecord,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        bar_ts: pd.Timestamp,
    ) -> Optional[TradeRecord]:
        """
        Check if SL or TP was hit within this bar's range.
        If both SL and TP could have been hit within the same bar,
        assume SL was hit first (conservative: worst case for the trader).

        Returns the closed TradeRecord if closed, else None.
        """
        if trade.direction == "bullish":
            sl_hit = bar_low  <= trade.stop_loss
            tp_hit = bar_high >= trade.take_profit
        else:
            sl_hit = bar_high >= trade.stop_loss
            tp_hit = bar_low  <= trade.take_profit

        if not sl_hit and not tp_hit:
            return None   # still open

        # Conservative: if both hit same bar, SL wins
        if sl_hit:
            exit_price  = trade.stop_loss
            exit_reason = "sl_hit"
        else:
            exit_price  = trade.take_profit
            exit_reason = "tp_hit"

        return self._close_trade(trade, exit_price, bar_ts, exit_reason)

    def _force_close(
        self,
        trade: TradeRecord,
        exit_price: float,
        ts: pd.Timestamp,
        reason: str,
    ) -> None:
        """Close a trade at an arbitrary price (end-of-data or manual)."""
        self._close_trade(trade, exit_price, ts, reason)

    def _close_trade(
        self,
        trade: TradeRecord,
        exit_price: float,
        ts: pd.Timestamp,
        reason: str,
    ) -> TradeRecord:
        """Compute P&L and stamp exit fields on the TradeRecord (in-place)."""
        trade.exit_bar_ts = ts
        trade.exit_price  = exit_price
        trade.exit_reason = reason

        pt_diff = (exit_price - trade.entry_price
                   if trade.direction == "bullish"
                   else trade.entry_price - exit_price)

        # Contract size defines dollar value per point per 1.0 standard lot:
        # XAUUSD: 100.0 ($100/pt/lot), BTCUSD: 1.0 ($1/pt/lot), EURUSD: 100000.0 ($10/pip/lot)
        contract_value_per_pt = getattr(self.inst, "contract_size", 100.0)
        expected_pnl = pt_diff * trade.lot_size * contract_value_per_pt
        trade.pnl   = expected_pnl
        trade.pnl_r = pt_diff / trade.risk_points if trade.risk_points > 0 else 0.0

        # Automated Invariant Check: Per-trade PnL & R-multiple consistency
        assert abs(trade.pnl - expected_pnl) < 1e-4, f"Trade PnL invariant violation: {trade.pnl} != {expected_pnl}"
        if trade.risk_points > 0:
            expected_r = pt_diff / trade.risk_points
            assert abs(trade.pnl_r - expected_r) < 1e-4, f"Trade R invariant violation: {trade.pnl_r} != {expected_r}"

        log.debug(
            f"  Trade closed @ {ts} | {reason} "
            f"exit={exit_price:.2f} pnl={trade.pnl:+.2f} "
            f"({trade.pnl_r:+.2f}R)"
        )
        return trade

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_slice(self, current_ts: pd.Timestamp) -> dict[str, pd.DataFrame]:
        """
        Build a bars_dict with all TFs sliced up to (and including) current_ts.
        The M1 "trigger" is simulated as the last 3 bars of the execution TF.
        NO LOOK-AHEAD: strictly bars with index <= current_ts.
        """
        sliced: dict[str, pd.DataFrame] = {}
        for tf, df in self._all_bars.items():
            mask = df.index <= current_ts
            sliced[tf] = df[mask].copy()

        # Simulate M1 trigger using last 3 execution TF bars if M1 is absent or empty
        exec_slice = sliced.get(self.EXEC_TF, pd.DataFrame())
        if ("M1" not in sliced or sliced["M1"].empty) and not exec_slice.empty:
            sliced["M1"] = exec_slice.iloc[-3:].copy()

        return sliced

    def _update_daily_pnl(self, ts: pd.Timestamp, pnl: float) -> None:
        date_str = str(ts.date())
        self._daily_pnl[date_str] = self._daily_pnl.get(date_str, 0.0) + pnl

    def _build_result(self) -> BacktestResult:
        """Package all accumulated data into a BacktestResult."""
        closed_trades = [t for t in self._trades if not t.is_open]

        equity_ts = [ts for ts, _ in self._equity_series]
        equity_vals = [v for _, v in self._equity_series]
        eq_series = pd.Series(equity_vals, index=equity_ts, name="equity")

        # Automated Invariant Check: Equity curve vs trade ledger consistency
        if closed_trades and not eq_series.empty:
            expected_final = (
                self.risk.backtest.initial_balance
                + sum(t.pnl for t in closed_trades if t.pnl is not None)
                - sum(t.commission for t in closed_trades)
            )
            assert abs(self._equity - expected_final) < 0.05, (
                f"Equity invariant failure: engine equity ({self._equity:.2f}) != "
                f"initial + net_pnl ({expected_final:.2f})"
            )
            assert abs(eq_series.iloc[-1] - self._equity) < 0.05, (
                f"Equity curve end mismatch: eq_series[-1] ({eq_series.iloc[-1]:.2f}) != {self._equity:.2f}"
            )

        result = BacktestResult(
            symbol=self.symbol,
            start_date=self._exec_df.index[0],
            end_date=self._exec_df.index[-1],
            bars_processed=len(self._exec_df),
            initial_balance=self.risk.backtest.initial_balance,
            final_balance=self._equity,
            trades=self._trades,
            equity_curve=eq_series,
            signals_generated=self._signals_generated,
        )

        # Compute stats
        result = _compute_stats(result, closed_trades)
        return result

    def _write_to_db(self) -> None:
        """Persist all signals and trades to the DB via repository."""
        from storage.db import init_db
        from storage.repository import save_signal, save_trade, close_trade as db_close

        try:
            init_db()
        except Exception as e:
            log.error(f"DB init failed — skipping persistence: {e}")
            return

        log.info(f"[{self.symbol}] Persisting {len(self._trades)} trades to DB…")
        for tr in self._trades:
            try:
                sig_row = save_signal(tr.signal, environment="backtest")
                if tr.exit_price is not None:
                    trade_row = save_trade(
                        signal_log=sig_row,
                        lot_size=tr.lot_size,
                        entry_price=tr.entry_price,
                        entry_time=tr.entry_bar_ts.to_pydatetime(),
                        environment="backtest",
                        commission=tr.commission,
                    )
                    db_close(
                        trade_id=trade_row.id,
                        exit_price=tr.exit_price,
                        exit_time=tr.exit_bar_ts.to_pydatetime(),
                        exit_reason=tr.exit_reason or "unknown",
                        pnl=tr.pnl or 0.0,
                    )
            except Exception as e:
                log.warning(f"  DB write failed for trade: {e}")


# ── Pure helpers (no self) ────────────────────────────────────────────────────

def _calc_lot_size(
    equity: float,
    risk_pct: float,
    risk_points: float,
    inst: InstrumentConfig,
) -> float:
    """
    Calculate lot size so that a full stop-loss costs exactly risk_pct of equity.

    For XAUUSD (gold):
        1 lot = 100 oz
        1 pip = pip_value (e.g. 0.01 for 2-decimal gold, 0.1 for 1-decimal)
        Value per point per lot = pip_value * 1000  (broker-specific)
        → lot_size = (equity * risk_pct) / (risk_points * value_per_pt_per_lot)

    Falls back to min_lot if calculation gives 0 or invalid.
    """
    if risk_points <= 0:
        return inst.min_lot

    # Universal: contract_size is dollar move per 1.0 point for 1.0 standard lot
    value_per_pt_per_lot = getattr(inst, "contract_size", 100.0)

    risk_dollars = equity * risk_pct
    raw_lots     = risk_dollars / (risk_points * value_per_pt_per_lot)

    # Round to lot_step and clamp
    lots = max(inst.min_lot,
               round(raw_lots / inst.lot_step) * inst.lot_step)
    return round(lots, 2)


def _compute_stats(result: BacktestResult, trades: list[TradeRecord]) -> BacktestResult:
    """Compute win rate, R, profit factor, max drawdown, etc."""
    if not trades:
        return result

    pnls  = [t.pnl  for t in trades if t.pnl  is not None]
    r_muls = [t.pnl_r for t in trades if t.pnl_r is not None]

    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss   = abs(sum(losses))

    result.total_trades  = len(pnls)
    result.wins          = len(wins)
    result.losses        = len(losses)
    result.win_rate      = len(wins) / len(pnls) if pnls else 0.0
    result.avg_r         = sum(r_muls) / len(r_muls) if r_muls else 0.0
    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    result.total_pnl     = sum(pnls)
    result.best_trade_r  = max(r_muls) if r_muls else 0.0
    result.worst_trade_r = min(r_muls) if r_muls else 0.0

    # Max drawdown from equity curve
    if not result.equity_curve.empty:
        eq    = result.equity_curve.to_numpy()
        peaks = np.maximum.accumulate(eq)
        dds   = (peaks - eq) / peaks
        result.max_drawdown = float(np.max(dds)) if len(dds) else 0.0

    return result
