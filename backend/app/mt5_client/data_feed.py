import MetaTrader5 as mt5
import pandas as pd
from app.logging_setup import log_system_event

def get_timeframe(tf_string: str):
    mapping = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf_string, mt5.TIMEFRAME_M15)

def fetch_ohlc(symbol: str, timeframe: str, num_bars: int = 1000) -> pd.DataFrame:
    """
    Fetches OHLC data from MT5 and returns a formatted pandas DataFrame.
    """
    tf = get_timeframe(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, num_bars)
    
    if rates is None or len(rates) == 0:
        log_system_event('warning', f"Failed to fetch data for {symbol} at {timeframe}")
        return pd.DataFrame()
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # We rename columns to match expected standard
    # mt5 returns: time, open, high, low, close, tick_volume, spread, real_volume
    
    return df
