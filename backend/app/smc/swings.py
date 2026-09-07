import pandas as pd
from typing import List, Dict

def get_swing_highs(df: pd.DataFrame, period: int = 2) -> List[Dict]:
    """
    Returns a list of swing high dictionaries from the dataframe.
    A swing high is formed when a high is > the highs of the 'period' candles before and after.
    """
    swings = []
    if len(df) < (period * 2) + 1:
        return swings
        
    for i in range(period, len(df) - period):
        is_swing = True
        high = df['high'].iloc[i]
        
        for j in range(1, period + 1):
            if df['high'].iloc[i - j] >= high or df['high'].iloc[i + j] >= high:
                is_swing = False
                break
                
        if is_swing:
            swings.append({
                'index': i,
                'time': df['time'].iloc[i],
                'price': high,
                'type': 'high'
            })
            
    return swings

def get_swing_lows(df: pd.DataFrame, period: int = 2) -> List[Dict]:
    """
    Returns a list of swing low dictionaries from the dataframe.
    A swing low is formed when a low is < the lows of the 'period' candles before and after.
    """
    swings = []
    if len(df) < (period * 2) + 1:
        return swings
        
    for i in range(period, len(df) - period):
        is_swing = True
        low = df['low'].iloc[i]
        
        for j in range(1, period + 1):
            if df['low'].iloc[i - j] <= low or df['low'].iloc[i + j] <= low:
                is_swing = False
                break
                
        if is_swing:
            swings.append({
                'index': i,
                'time': df['time'].iloc[i],
                'price': low,
                'type': 'low'
            })
            
    return swings
