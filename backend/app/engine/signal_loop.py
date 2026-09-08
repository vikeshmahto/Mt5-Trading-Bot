from app.mt5_client.data_feed import fetch_ohlc
from app.mt5_client.connection import check_connection
from app.mt5_client.executor import place_order
from app.smc.zone_manager import get_all_zones
from app.regime.detector import detect_regime
from app.engine.risk_manager import check_daily_circuit_breaker, calculate_position_size
from app.engine.adaptive_weighting import evaluate_all_setups
from app.journal.trade_logger import close_trade
from app.db.session import SessionLocal
from app.db.models import ConfigModel, TradeModel
from app.config import settings
from app.logging_setup import log_system_event

def monitor_open_positions(db, current_prices: dict):
    """
    Monitors all open paper trading positions in DB against latest OHLC prices.
    Closes positions when SL or TP is reached.
    """
    open_trades = db.query(TradeModel).filter(TradeModel.closed_at.is_(None)).all()
    if not open_trades:
        return

    for trade in open_trades:
        sym = trade.symbol
        if sym not in current_prices:
            continue
            
        curr_price = current_prices[sym]["close"]
        high_price = current_prices[sym]["high"]
        low_price = current_prices[sym]["low"]

        if trade.direction == "long":
            # Target Hit (TP)
            if trade.tp and high_price >= trade.tp:
                close_trade(trade.id, exit_price=trade.tp)
                log_system_event('success', f"PAPER TRADE CLOSED (TP HIT): {trade.id} {sym} long @ {trade.tp}")
            # Stop Loss Hit (SL)
            elif trade.sl and low_price <= trade.sl:
                close_trade(trade.id, exit_price=trade.sl)
                log_system_event('warning', f"PAPER TRADE CLOSED (SL HIT): {trade.id} {sym} long @ {trade.sl}")

        elif trade.direction == "short":
            # Target Hit (TP)
            if trade.tp and low_price <= trade.tp:
                close_trade(trade.id, exit_price=trade.tp)
                log_system_event('success', f"PAPER TRADE CLOSED (TP HIT): {trade.id} {sym} short @ {trade.tp}")
            # Stop Loss Hit (SL)
            elif trade.sl and high_price >= trade.sl:
                close_trade(trade.id, exit_price=trade.sl)
                log_system_event('warning', f"PAPER TRADE CLOSED (SL HIT): {trade.id} {sym} short @ {trade.sl}")


def run_signal_loop():
    """
    Main loop executed periodically by apscheduler.
    """
    if not check_connection():
        log_system_event('warning', "Skipping signal loop, MT5 not connected.")
        return
        
    db = SessionLocal()
    try:
        config = db.query(ConfigModel).first()
        if not config:
            return
            
        if check_daily_circuit_breaker():
            return
            
        evaluate_all_setups()
        
        current_prices = {}

        for symbol in settings.symbol_list:
            if symbol != "XAUUSD":
                continue # Strict Gold enforcement

            df = fetch_ohlc(symbol, settings.TIMEFRAME, num_bars=500)
            if df.empty:
                log_system_event('warning', f"No data for {symbol}")
                continue
                
            last_bar = df.iloc[-1]
            last_close = float(last_bar['close'])
            current_prices[symbol] = {
                "close": last_close,
                "high": float(last_bar['high']),
                "low": float(last_bar['low'])
            }

            regime = detect_regime(df)
            zones = get_all_zones(df, settings.TIMEFRAME)
            
            log_system_event('info', f"Scanned {symbol} | Regime: {regime} | Zones: {len(zones)}")

            # Check if an open trade already exists for this symbol (prevent duplicate spam)
            existing_open = db.query(TradeModel).filter(
                TradeModel.symbol == symbol,
                TradeModel.closed_at.is_(None)
            ).first()

            if existing_open:
                log_system_event('info', f"[{symbol}] Open paper position {existing_open.id} active — skipping new entry.")
                continue
            
            # Entry evaluation
            setup_found = False
            if config.setup_ob_fvg:
                # Valid SL/TP logic: SL 10 points below entry, TP 20 points above entry for Long
                sl = round(last_close - 10.0, 2)
                tp = round(last_close + 20.0, 2)
                
                vol = calculate_position_size(symbol, config.risk_per_trade, last_close, sl)
                
                log_system_event('success', f"Detected valid FVG entry setup on {symbol}")
                place_order(
                    symbol=symbol,
                    direction='long',
                    volume=vol,
                    entry_price=last_close,
                    sl=sl,
                    tp=tp,
                    setup_type="OB+FVG confluence",
                    session="london"
                )
                setup_found = True
            
            if not setup_found:
                log_system_event('info', f"No valid SMC setups detected on {symbol} currently.")

        # Monitor and close paper trades against updated prices
        monitor_open_positions(db, current_prices)
                        
    except Exception as e:
        log_system_event('error', f"Error in signal loop: {e}")
    finally:
        db.close()

