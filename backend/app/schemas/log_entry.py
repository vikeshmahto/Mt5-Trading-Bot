from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import datetime

class LogEntry(BaseModel):
    id: str
    timestamp: datetime
    level: Literal['info', 'warning', 'error', 'success']
    message: str

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
