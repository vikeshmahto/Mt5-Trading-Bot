import MetaTrader5 as mt5
from app.config import settings
from app.logging_setup import log_system_event

def initialize_mt5() -> bool:
    if not mt5.initialize(path=settings.MT5_PATH,
                          login=settings.MT5_LOGIN,
                          server=settings.MT5_SERVER,
                          password=settings.MT5_PASSWORD):
        error = mt5.last_error()
        log_system_event('error', f"MT5 initialization failed: {error}")
        return False
        
    log_system_event('success', "MT5 Connected successfully")
    return True

def check_connection() -> bool:
    # A simple way to check if we are still connected is to request terminal info
    info = mt5.terminal_info()
    if info is None or not info.connected:
        return False
    return True

def shutdown_mt5():
    mt5.shutdown()
    log_system_event('info', "MT5 connection closed")
