from fastapi import APIRouter
from typing import List, Dict, Any
from app.mt5_client.data_feed import fetch_ohlc

router = APIRouter()

@router.get("/chart")
def get_chart_data(symbol: str = "XAUUSD", timeframe: str = "M15", num_bars: int = 500) -> List[Dict[str, Any]]:
    df = fetch_ohlc(symbol, timeframe, num_bars)
    if df.empty:
        return []
    
    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": int(row['time'].timestamp()),
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close']
        })
    return candles
