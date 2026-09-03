"""
config/settings.py
──────────────────
Central settings loader.  Reads:
  - config/instruments.yaml  → per-instrument config
  - config/risk.yaml         → risk rules
  - .env                     → MT5 credentials, DB URL, environment flag

Usage:
    from config.settings import settings
    print(settings.instruments["XAUUSD"].target_points)
    print(settings.risk.max_concurrent_trades)
    print(settings.mt5_login)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# ── Resolve paths ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent          # mt5-trading-system/
CONFIG_DIR = ROOT_DIR / "config"
INSTRUMENTS_YAML = CONFIG_DIR / "instruments.yaml"
RISK_YAML = CONFIG_DIR / "risk.yaml"
DOT_ENV = ROOT_DIR / ".env"

# Load .env (silently OK if missing — CI / backtest may not have it)
load_dotenv(DOT_ENV, override=False)


# ── Instrument config dataclass ──────────────────────────────────────────────
@dataclass
class SessionConfig:
    start: str   # "HH:MM" UTC
    end: str     # "HH:MM" UTC


@dataclass
class InstrumentConfig:
    symbol: str
    description: str
    bias_timeframes: list[str]
    setup_timeframes: list[str]
    entry_timeframe: str
    target_points: int
    max_spread_points: float
    sessions: dict[str, SessionConfig]
    digits: int
    pip_value: float
    contract_size: float = 100.0
    lot_step: float = 0.01
    min_lot: float = 0.01

    @classmethod
    def from_dict(cls, symbol: str, d: dict[str, Any]) -> "InstrumentConfig":
        sessions = {
            name: SessionConfig(**times)
            for name, times in d.get("sessions", {}).items()
        }
        return cls(
            symbol=symbol,
            description=d["description"],
            bias_timeframes=d["bias_timeframes"],
            setup_timeframes=d["setup_timeframes"],
            entry_timeframe=d["entry_timeframe"],
            target_points=d["target_points"],
            max_spread_points=d["max_spread_points"],
            sessions=sessions,
            digits=d["digits"],
            pip_value=d["pip_value"],
            contract_size=float(d.get("contract_size", 100.0)),
            lot_step=d["lot_step"],
            min_lot=d["min_lot"],
        )


# ── Risk config dataclass ────────────────────────────────────────────────────
@dataclass
class PositionSizingConfig:
    risk_per_trade: float
    max_total_risk: float


@dataclass
class LimitsConfig:
    max_concurrent_trades: int
    max_trades_per_instrument: int
    max_concurrent_same_direction_trades: int
    max_daily_loss: float
    max_drawdown: float


@dataclass
class ScoringConfig:
    min_score_to_trade: float
    min_rr_ratio: float
    max_score_to_trade: float = 79.9


@dataclass
class BacktestConfig:
    slippage_points: float
    commission_per_lot: float
    initial_balance: float


@dataclass
class RiskConfig:
    position_sizing: PositionSizingConfig
    limits: LimitsConfig
    scoring: ScoringConfig
    backtest: BacktestConfig

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskConfig":
        return cls(
            position_sizing=PositionSizingConfig(**d["position_sizing"]),
            limits=LimitsConfig(**d["limits"]),
            scoring=ScoringConfig(**d["scoring"]),
            backtest=BacktestConfig(**d["backtest"]),
        )


# ── Master settings object ────────────────────────────────────────────────────
@dataclass
class Settings:
    # Instrument configs: symbol → InstrumentConfig
    instruments: dict[str, InstrumentConfig] = field(default_factory=dict)

    # Risk config
    risk: RiskConfig = field(default_factory=lambda: None)  # type: ignore[assignment]

    # MT5 connection (from .env)
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""

    # Database
    db_url: str = "sqlite:///trading.db"

    # Execution mode
    environment: str = "backtest"   # live | paper | backtest

    # Logging
    log_level: str = "INFO"

    def get_instrument(self, symbol: str) -> InstrumentConfig:
        """Raises KeyError with a friendly message if symbol not configured."""
        if symbol not in self.instruments:
            available = list(self.instruments.keys())
            raise KeyError(
                f"Symbol '{symbol}' not found in instruments.yaml. "
                f"Available: {available}"
            )
        return self.instruments[symbol]

    @property
    def active_symbols(self) -> list[str]:
        return list(self.instruments.keys())


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _build_settings() -> Settings:
    """Read YAML + env vars and return a fully populated Settings instance."""
    # ── YAML ──
    raw_instruments = _load_yaml(INSTRUMENTS_YAML).get("instruments", {})
    raw_risk = _load_yaml(RISK_YAML)

    instruments = {
        sym: InstrumentConfig.from_dict(sym, cfg)
        for sym, cfg in raw_instruments.items()
    }
    risk = RiskConfig.from_dict(raw_risk)

    # ── Env vars ──
    login_str = os.getenv("MT5_LOGIN", "0")
    return Settings(
        instruments=instruments,
        risk=risk,
        mt5_login=int(login_str) if login_str.isdigit() else 0,
        mt5_password=os.getenv("MT5_PASSWORD", ""),
        mt5_server=os.getenv("MT5_SERVER", ""),
        mt5_path=os.getenv("MT5_PATH", ""),
        db_url=os.getenv("DB_URL", "sqlite:///trading.db"),
        environment=os.getenv("ENVIRONMENT", "backtest"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


# ── Singleton ─────────────────────────────────────────────────────────────────
settings: Settings = _build_settings()
