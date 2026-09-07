from app.mt5_client.data_feed import fetch_ohlc
from app.mt5_client.connection import check_connection
from app.mt5_client.executor import place_order
from app.smc.zone_manager import get_all_zones
from app.regime.detector import detect_regime
from app.engine.risk_manager import check_daily_circuit_breaker, calculate_position_size
from app.engine.adaptive_weighting import evaluate_all_setups
from app.db.session import SessionLocal
from app.db.models import ConfigModel
from app.config import settings
from app.logging_setup import log_system_event

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
        
        for symbol in settings.symbol_list:
            df = fetch_ohlc(symbol, settings.TIMEFRAME, num_bars=500)
            if df.empty:
                log_system_event('warning', f"No data for {symbol}")
                continue
                
            regime = detect_regime(df)
            zones = get_all_zones(df, settings.TIMEFRAME)
            
            log_system_event('info', f"Scanned {symbol} | Regime: {regime} | Zones: {len(zones)}")
            
            # Simple mockup logic for entry based on zones (Placeholder for actual SMC entry rules)
            # e.g., if price touches an active FVG zone and config allows FVG trades
            setup_found = False
            if config.setup_ob_fvg: # Relaxed regime check for testing
                last_close = df.iloc[-1]['close']
                for z in zones:
                    if z.type == 'fvg':
                        # For testing, we just pretend we found a setup if there's any FVG
                        sl = z.price_low - (z.price_high - z.price_low) * 0.1 # Example SL below zone
                        tp = last_close + (last_close - sl) * 2 # 2R target
                        
                        vol = calculate_position_size(symbol, config.risk_per_trade, last_close, sl)
                        
                        log_system_event('success', f"Detected FVG entry setup on {symbol}")
                        place_order(
                            symbol=symbol,
                            direction='long',
                            volume=vol,
                            entry_price=last_close,
                            sl=sl,
                            tp=tp,
                            setup_type="OB+FVG confluence",
                            session="ny" # Simplification
                        )
                        setup_found = True
                        break # Only one order per symbol per loop max
            
            if not setup_found:
                log_system_event('info', f"No valid SMC setups detected on {symbol} currently.")
                        
    except Exception as e:
        log_system_event('error', f"Error in signal loop: {e}")
    finally:
        db.close()
