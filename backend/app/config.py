from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MT5_LOGIN: int = 0
    MT5_PASSWORD: str = ""
    MT5_SERVER: str = ""
    MT5_PATH: str = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    
    SYMBOLS: str = "XAUUSD,BTCUSD"
    DRY_RUN: bool = True
    
    DATABASE_URL: str = "sqlite:///./trading_bot.db"
    
    # Engine Settings
    TIMEFRAME: str = "M15"
    SCHEDULER_INTERVAL_MINUTES: int = 15
    FRACTAL_PERIOD: int = 2
    ADX_TRENDING_THRESHOLD: int = 25
    DISPLACEMENT_MULTIPLIER: float = 1.5
    ROLLING_WINRATE_TRADES: int = 30
    MIN_WINRATE_THRESHOLD: float = 0.40 # 40%

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def symbol_list(self) -> List[str]:
        return [s.strip() for s in self.SYMBOLS.split(",") if s.strip()]

settings = Settings()
