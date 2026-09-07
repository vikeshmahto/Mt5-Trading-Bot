from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional
from datetime import datetime

class SystemStatus(BaseModel):
    bot_status: Literal['running', 'paused', 'stopped'] = Field(alias='botStatus')
    mt5_connected: bool = Field(alias='mt5Connected')
    regime: Literal['trending', 'ranging']
    last_tick_at: Optional[datetime] = Field(None, alias='lastTickAt')

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
