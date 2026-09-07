from fastapi import APIRouter, Query
from typing import List, Optional
from app.smc.zone_manager import get_all_zones
from app.mt5_client.data_feed import fetch_ohlc
from app.schemas.zone import Zone

router = APIRouter()

@router.get("/zones", response_model=List[Zone])
def get_zones(symbol: str = "XAUUSD", timeframe: str = "M15"):
    df = fetch_ohlc(symbol, timeframe, num_bars=500)
    if df.empty:
        return []
    return get_all_zones(df, timeframe)

@router.get("/candles")
def get_candles(symbol: str = "XAUUSD", timeframe: str = "M15", num_bars: int = 200):
    df = fetch_ohlc(symbol, timeframe, num_bars=num_bars)
    if df.empty:
        return []
    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": int(row['time'].timestamp()),
            "open": round(float(row['open']), 2),
            "high": round(float(row['high']), 2),
            "low": round(float(row['low']), 2),
            "close": round(float(row['close']), 2),
        })
    return candles

