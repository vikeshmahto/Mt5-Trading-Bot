"""
scripts/check_mt5_xauusd_history.py
───────────────────────────────────
Queries MT5 to check earliest and latest available historical bars for XAUUSD.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import MetaTrader5 as mt5
from data.mt5_client import MT5Client

def check_history():
    client = MT5Client()
    if not client.connect():
        print("Failed to connect to MT5.")
        return

    symbol = "XAUUSD"
    tf = mt5.TIMEFRAME_M15

    # Request large number of bars from current pos
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50000)
    if rates is None or len(rates) == 0:
        print(f"No rates returned for {symbol}")
        client.disconnect()
        return

    earliest_ts = datetime.fromtimestamp(rates[0]['time'], tz=timezone.utc)
    latest_ts = datetime.fromtimestamp(rates[-1]['time'], tz=timezone.utc)

    print("==================================================")
    print("      MT5 HISTORICAL DATA RANGE FOR XAUUSD        ")
    print("==================================================")
    print(f"  Symbol           : {symbol}")
    print(f"  Timeframe        : M15")
    print(f"  Total Bars       : {len(rates):,}")
    print(f"  Earliest Bar     : {earliest_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Latest Bar       : {latest_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("==================================================")

    client.disconnect()

if __name__ == "__main__":
    check_history()
