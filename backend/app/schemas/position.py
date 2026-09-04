from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import datetime

class Position(BaseModel):
    id: str
    symbol: str
    direction: Literal['long', 'short']
    entry_price: float = Field(alias='entryPrice')
    current_price: float = Field(alias='currentPrice')
    sl: float
    tp: float
    floating_pnl: float = Field(alias='floatingPnl')
    opened_at: datetime = Field(alias='openedAt')

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
