"""
execution/order_manager.py
──────────────────────────
MT5 Order Execution & Position Manager.

Handles:
  • Real-time order placement (BUY / SELL) with automated SL / TP
  • Paper trading / Dry-run mode vs Live MT5 order dispatch
  • Position tracking, modifications (SL to breakeven, trailing), and closing
  • Real-time account balance & equity queries

Design:
  • Uses MetaTrader5 package when live, or simulates fills when paper/dry-run.
  • Magic number tagging to distinguish bot orders from manual trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import MetaTrader5 as mt5

from config.settings import InstrumentConfig, settings
from core.logger import get_logger
from core.types import Direction, Signal

log = get_logger(__name__)

BOT_MAGIC_NUMBER = 777123


@dataclass
class ExecutionResult:
    """Outcome of an order placement attempt."""
    success: bool
    ticket: Optional[int] = None
    entry_price: float = 0.0
    lot_size: float = 0.0
    comment: str = ""
    retcode: int = 0
    error_message: str = ""


class OrderManager:
    """
    Manages order execution and position monitoring via MetaTrader5 API.
    """

    def __init__(self, magic_number: int = BOT_MAGIC_NUMBER, is_paper: bool = False) -> None:
        self.magic_number = magic_number
        self.is_paper = is_paper

    def get_account_info(self) -> dict[str, Any]:
        """Fetch current account balance, equity, and margin status."""
        if self.is_paper:
            return {
                "balance": 10000.0,
                "equity": 10000.0,
                "free_margin": 10000.0,
                "profit": 0.0,
                "currency": "USD",
            }

        acc = mt5.account_info()
        if acc is None:
            log.error(f"Failed to fetch account_info: {mt5.last_error()}")
            return {}

        return {
            "balance": acc.balance,
            "equity": acc.equity,
            "free_margin": acc.margin_free,
            "profit": acc.profit,
            "currency": acc.currency,
        }

    def execute_signal(
        self,
        signal: Signal,
        lot_size: float,
        inst: InstrumentConfig,
        comment: str = "SMC-Bot",
    ) -> ExecutionResult:
        """
        Send a market order based on a Signal.
        """
        symbol = signal.symbol
        direction = signal.direction

        if self.is_paper:
            log.info(
                f"[PAPER TRADE] {symbol} {direction.value.upper()} | "
                f"Lots={lot_size:.2f} Entry={signal.entry_price:.2f} "
                f"SL={signal.stop_loss:.2f} TP={signal.take_profit:.2f}"
            )
            return ExecutionResult(
                success=True,
                ticket=999999,
                entry_price=signal.entry_price,
                lot_size=lot_size,
                comment=f"Paper: {comment}",
                retcode=0,
            )

        # Prepare MT5 order request
        order_type = mt5.ORDER_TYPE_BUY if direction == Direction.BULLISH else mt5.ORDER_TYPE_SELL

        # Get latest tick
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            err = f"Could not get tick for symbol {symbol}: {mt5.last_error()}"
            log.error(err)
            return ExecutionResult(success=False, error_message=err)

        price = tick.ask if direction == Direction.BULLISH else tick.bid

        # Check filling mode support
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            err = f"Symbol info unavailable for {symbol}"
            return ExecutionResult(success=False, error_message=err)

        # Determine filling mode
        filling = mt5.ORDER_FILLING_IOC
        if sym_info.filling_mode & mt5.ORDER_FILLING_FOK:
            filling = mt5.ORDER_FILLING_FOK
        elif sym_info.filling_mode & mt5.ORDER_FILLING_IOC:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": float(price),
            "sl": float(round(signal.stop_loss, inst.digits)),
            "tp": float(round(signal.take_profit, inst.digits)),
            "deviation": int(inst.max_spread_points * 2),
            "magic": self.magic_number,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        log.info(
            f"Sending MT5 Order: {symbol} {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} "
            f"vol={lot_size} price={price:.2f} SL={request['sl']:.2f} TP={request['tp']:.2f}"
        )

        result = mt5.order_send(request)

        if result is None:
            err = f"Order send failed (result=None): {mt5.last_error()}"
            log.error(err)
            return ExecutionResult(success=False, error_message=err)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            err = f"Order rejected by MT5. retcode={result.retcode} ({result.comment})"
            log.error(err)
            return ExecutionResult(
                success=False,
                retcode=result.retcode,
                comment=result.comment,
                error_message=err,
            )

        fill_price = result.price if result.price > 0 else price
        log.info(f"Order executed successfully! Ticket={result.order} Fill={fill_price:.2f}")

        return ExecutionResult(
            success=True,
            ticket=result.order,
            entry_price=fill_price,
            lot_size=result.volume,
            comment=result.comment,
            retcode=result.retcode,
        )

    def get_open_positions(self, symbol: Optional[str] = None) -> list[dict[str, Any]]:
        """Fetch all currently open positions created by this bot."""
        if self.is_paper:
            return []

        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []

        bot_positions = []
        for pos in positions:
            if pos.magic == self.magic_number:
                bot_positions.append({
                    "ticket": pos.ticket,
                    "symbol": pos.symbol,
                    "type": "bullish" if pos.type == mt5.POSITION_TYPE_BUY else "bearish",
                    "volume": pos.volume,
                    "open_price": pos.price_open,
                    "current_price": pos.price_current,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "profit": pos.profit,
                    "open_time": datetime.fromtimestamp(pos.time, tz=timezone.utc),
                    "comment": pos.comment,
                })
        return bot_positions

    def close_position(self, ticket: int, symbol: str, volume: float, direction: str) -> bool:
        """Close an open position by ticket."""
        if self.is_paper:
            log.info(f"[PAPER] Closed position {ticket}")
            return True

        close_type = mt5.ORDER_TYPE_SELL if direction == "bullish" else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            log.error(f"Cannot close position {ticket}: tick unavailable")
            return False

        price = tick.bid if direction == "bullish" else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": symbol,
            "volume": float(volume),
            "type": close_type,
            "price": float(price),
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "Close by Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        res = mt5.order_send(request)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Failed to close position {ticket}: {res.comment if res else mt5.last_error()}")
            return False

        log.info(f"Position {ticket} closed successfully at {price:.2f}")
        return True
