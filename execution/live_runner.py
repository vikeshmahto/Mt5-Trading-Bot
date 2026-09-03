"""
execution/live_runner.py
────────────────────────
Real-time SMC Trading Bot Live & Paper Runner.

Architecture:
  1. Multi-Timeframe Poller: pulls D1, H4, H1, M15, M1 on each iteration.
  2. Pure Signal Pipeline: runs generate_signal(bars_dict).
  3. Risk Gateway: checks limits, spread, session, daily loss before order placement.
  4. Order Dispatcher: executes through MT5 with automated SL/TP.
  5. Position Synchronizer: queries MT5 open trades & syncs closed trades (TP/SL) to Neon DB.
  6. Health & Heartbeat: periodic terminal status logs and graceful shutdown handler.

Usage:
    python -m execution.live_runner --environment paper
    python -m execution.live_runner --environment live
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
import threading
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger
from data.mt5_client import MT5Client, MT5ConnectionError
from execution.order_manager import OrderManager
from execution.risk_manager import RiskManager
from signals.generator import generate_signal
from storage.db import init_db
from storage.repository import (
    close_trade,
    get_open_trades,
    save_signal,
    save_trade,
    update_heartbeat,
)

log = get_logger("live_runner", log_file="logs/live_runner.log", level=settings.log_level)

def _push_event(event_type: str, data: dict) -> None:
    """Fire-and-forget event push to dashboard backend."""
    def _post():
        try:
            requests.post(
                "http://localhost:8000/api/internal/push",
                json={"event_type": event_type, "data": data},
                timeout=1.0
            )
        except Exception:
            pass
    threading.Thread(target=_post, daemon=True).start()


class LiveRunner:
    """
    Live / Paper trading bot orchestrator.
    """

    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        environment: str = "paper",
        poll_interval_sec: int = 15,
    ) -> None:
        self.symbols = symbols or settings.active_symbols
        self.environment = environment
        self.poll_interval = poll_interval_sec
        self.is_running = False

        self.order_mgr = OrderManager(is_paper=(environment == "paper"))
        self.risk_mgr = RiskManager()

        # Track processed bar timestamps to avoid duplicate entries on the same bar
        self._last_processed_m1: dict[str, datetime] = {}
        
        self.mt5_client = MT5Client()

    def start(self) -> None:
        """Initialize connections and enter the live loop."""
        self.is_running = True
        log.info("=" * 65)
        log.info(f"STARTING SMC TRADING BOT [{self.environment.upper()} MODE]")
        log.info(f"Active Symbols: {self.symbols} | Poll Interval: {self.poll_interval}s")
        log.info("=" * 65)

        # 1. Initialize Database (Neon Postgres or SQLite)
        try:
            init_db()
            log.info("Database initialized successfully.")
        except Exception as e:
            log.error(f"Database initialization failed: {e}")

        # 2. Main Execution Loop
        try:
            self.mt5_client.connect()
            self._main_loop()
        finally:
            self.mt5_client.disconnect()

    def stop(self) -> None:
        """Signal the loop to stop."""
        log.info("Stopping SMC Trading Bot...")
        self.is_running = False

    def _main_loop(self) -> None:
        """Continuous polling and execution loop."""
        last_heartbeat = 0.0

        while self.is_running:
            try:
                loop_start = time.time()
                
                # Check MT5 connection and reconnect if necessary
                if not self.mt5_client.is_connected():
                    log.warning("MT5 connection lost! Attempting to reconnect...")
                    try:
                        self.mt5_client.connect()
                    except MT5ConnectionError as e:
                        log.error(f"Reconnection failed: {e}. Will retry next cycle.")
                        time.sleep(5.0)
                        continue

                # A. Position & Trade Synchronization
                self._sync_positions_with_db()

                # B. Process each configured symbol
                for symbol in self.symbols:
                    self._process_symbol(symbol)

                # C. Heartbeat Logging (every 60 seconds)
                if time.time() - last_heartbeat >= 60.0:
                    self._log_heartbeat()
                    last_heartbeat = time.time()

                # D. Sleep until next cycle
                elapsed = time.time() - loop_start
                sleep_time = max(1.0, self.poll_interval - elapsed)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                log.info("Keyboard interrupt received.")
                self.stop()
                break
            except Exception as e:
                log.error(f"Error in live loop: {e}", exc_info=True)
                time.sleep(5.0)

    def _process_symbol(self, symbol: str) -> None:
        """Pull latest bars, evaluate signals, and execute allowed trades."""
        inst = settings.get_instrument(symbol)
        tfs = ["D1", "H4", "H1", "M15", "M1"]
        bar_counts = {"D1": 365, "H4": 500, "H1": 500, "M15": 500, "M1": 300}

        # 1. Fetch Multi-Timeframe Bars
        bars = fetch_multi(symbol, tfs, bar_counts, include_open=False)
        m1_df = bars.get("M1")

        if m1_df is None or m1_df.empty:
            return

        latest_m1_ts = m1_df.index[-1].to_pydatetime()

        # Prevent duplicate signal processing on the same M1 candle
        if self._last_processed_m1.get(symbol) == latest_m1_ts:
            return

        # 2. Run Pure Signal Generator
        signal_obj = generate_signal(bars, symbol=symbol, instrument_config=inst, risk_config=settings.risk)

        if signal_obj is None:
            return

        self._last_processed_m1[symbol] = latest_m1_ts
        log.info(f"[{symbol}] Signal detected: {signal_obj}")

        # 3. Log signal to Database regardless of whether it's executed
        sig_log_row = save_signal(signal_obj, environment=self.environment)
        _push_event("signal_checked", {
            "symbol": symbol,
            "direction": signal_obj.direction.value,
            "type": signal_obj.signal_type.value,
            "score": signal_obj.confluence_score,
            "timestamp": latest_m1_ts.isoformat()
        })

        # 4. Risk Evaluation
        acc_info = self.order_mgr.get_account_info()
        allowed, reason, lot_size = self.risk_mgr.can_trade(
            signal=signal_obj,
            account_info=acc_info,
            inst_config=inst,
            environment=self.environment,
        )

        if not allowed:
            log.info(f"[{symbol}] Trade skipped by Risk Manager: {reason}")
            return

        # 5. Order Execution
        exec_res = self.order_mgr.execute_signal(
            signal=signal_obj,
            lot_size=lot_size,
            inst=inst,
            comment=f"SMC-{signal_obj.signal_type.value}",
        )

        if not exec_res.success:
            log.error(f"[{symbol}] Execution failed: {exec_res.error_message}")
            return

        # 6. Save Trade Record to Database
        save_trade(
            signal_log=sig_log_row,
            lot_size=exec_res.lot_size,
            entry_price=exec_res.entry_price,
            entry_time=datetime.now(timezone.utc),
            environment=self.environment,
            mt5_ticket=exec_res.ticket,
            commission=settings.risk.backtest.commission_per_lot * exec_res.lot_size,
            notes=f"Retcode: {exec_res.retcode}",
        )
        _push_event("trade_opened", {
            "symbol": symbol,
            "ticket": exec_res.ticket,
            "entry_price": exec_res.entry_price,
            "lot_size": exec_res.lot_size
        })

    def _sync_positions_with_db(self) -> None:
        """
        Check DB open trades against live MT5 positions.
        If an MT5 position closed (TP/SL hit), update the Trade record in DB.
        """
        if self.environment == "paper":
            return

        db_open_trades = get_open_trades()
        if not db_open_trades:
            return

        mt5_positions = self.order_mgr.get_open_positions()
        live_tickets = {pos["ticket"]: pos for pos in mt5_positions}

        for db_trade in db_open_trades:
            if not db_trade.mt5_ticket:
                continue

            # If ticket no longer in active MT5 positions, it closed
            if db_trade.mt5_ticket not in live_tickets:
                # Query MT5 deals history for closing details
                now_utc = datetime.now(timezone.utc)
                deals = self._get_deal_history(db_trade.mt5_ticket)
                exit_price = db_trade.take_profit or db_trade.entry_price
                exit_reason = "closed"
                pnl = 0.0

                if deals:
                    exit_deal = deals[-1]
                    exit_price = exit_deal.get("price", exit_price)
                    pnl = exit_deal.get("profit", 0.0)
                    comment = exit_deal.get("comment", "").lower()
                    if "tp" in comment or "[tp" in comment:
                        exit_reason = "tp_hit"
                    elif "sl" in comment or "[sl" in comment:
                        exit_reason = "sl_hit"
                    else:
                        exit_reason = "manual"

                close_trade(
                    trade_id=db_trade.id,
                    exit_price=float(exit_price),
                    exit_time=now_utc,
                    exit_reason=exit_reason,
                    pnl=float(pnl),
                )
                log.info(
                    f"Synced closed trade: Ticket={db_trade.mt5_ticket} "
                    f"ExitPrice={exit_price} PnL=${pnl:+.2f} ({exit_reason})"
                )
                _push_event("trade_closed", {
                    "symbol": db_trade.symbol,
                    "ticket": db_trade.mt5_ticket,
                    "pnl_usd": float(pnl),
                    "exit_reason": exit_reason
                })

    def _get_deal_history(self, ticket: int) -> list[dict]:
        """Fetch closed deal records for a specific position from MT5."""
        import MetaTrader5 as mt5
        now = datetime.now()
        deals = mt5.history_deals_get(position=ticket)
        if not deals:
            return []
        deal_list = []
        for d in deals:
            deal_list.append({
                "ticket": d.ticket,
                "price": d.price,
                "profit": d.profit,
                "commission": d.commission,
                "comment": d.comment,
                "time": datetime.fromtimestamp(d.time, tz=timezone.utc),
            })
        return deal_list

    def _log_heartbeat(self) -> None:
        """Periodic status update."""
        acc = self.order_mgr.get_account_info()
        bal = acc.get("balance", 0.0)
        eq = acc.get("equity", 0.0)
        fl_pnl = acc.get("profit", 0.0)
        open_pos = self.order_mgr.get_open_positions()

        log.info(
            f"[HEARTBEAT] Bot Active | Balance: ${bal:,.2f} | Equity: ${eq:,.2f} "
            f"| Floating: ${fl_pnl:+,.2f} | Open Positions: {len(open_pos)}"
        )
        
        try:
            update_heartbeat(
                component="live_runner",
                status="active",
                extra_info={
                    "environment": self.environment,
                    "active_symbols": self.symbols,
                    "balance": bal,
                    "equity": eq,
                    "open_positions": len(open_pos)
                }
            )
            _push_event("heartbeat", {
                "environment": self.environment,
                "active_symbols": self.symbols,
                "balance": bal,
                "equity": eq,
                "open_positions": len(open_pos)
            })
        except Exception as e:
            log.error(f"Failed to log heartbeat to DB: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SMC MT5 Trading Bot Runner")
    parser.add_argument(
        "--environment",
        choices=["paper", "live"],
        default=settings.environment if settings.environment in ["paper", "live"] else "paper",
        help="Trading mode (paper or live)",
    )
    parser.add_argument("--symbols", nargs="+", default=None, help="Symbols to trade (e.g. XAUUSD)")
    parser.add_argument("--interval", type=int, default=15, help="Poll interval in seconds")

    args = parser.parse_args()

    runner = LiveRunner(
        symbols=args.symbols,
        environment=args.environment,
        poll_interval_sec=args.interval,
    )

    def _sig_handler(sig, frame):
        runner.stop()

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    runner.start()


if __name__ == "__main__":
    main()
