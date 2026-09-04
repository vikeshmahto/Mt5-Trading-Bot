from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime

class Trade(BaseModel):
    id: str
    symbol: str
    direction: Literal['long', 'short']
    entry_price: float = Field(alias='entryPrice')
    exit_price: Optional[float] = Field(None, alias='exitPrice')
    sl: float
    tp: float
    r_multiple: Optional[float] = Field(None, alias='rMultiple')
    outcome: Optional[Literal['win', 'loss', 'breakeven']] = None
    setup_type: str = Field(alias='setupType')
    session: Literal['asian', 'london', 'ny']
    opened_at: datetime = Field(alias='openedAt')
    closed_at: Optional[datetime] = Field(None, alias='closedAt')

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
