from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class Zone(BaseModel):
    type: Literal['orderblock', 'fvg', 'liquidity-sweep']
    start_time: int = Field(alias='startTime')
    end_time: int = Field(alias='endTime')
    price_high: float = Field(alias='priceHigh')
    price_low: float = Field(alias='priceLow')
    timeframe: str

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
