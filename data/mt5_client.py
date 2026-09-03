"""
data/mt5_client.py
──────────────────
Thin wrapper around the MetaTrader5 package.

Responsibilities:
  - connect()    → initialize + login to the terminal
  - disconnect() → shutdown cleanly
  - is_connected() → health-check
  - Context-manager support (with MT5Client() as client:)

All other modules import this and call connect() / disconnect().
No business logic lives here.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import MetaTrader5 as mt5

from config.settings import settings
from core.logger import get_logger

log = get_logger(__name__)


class MT5ConnectionError(RuntimeError):
    """Raised when the terminal cannot be reached or login fails."""


class MT5Client:
    """
    Manages a single MT5 terminal connection.

    Usage (explicit):
        client = MT5Client()
        client.connect()
        # ... use mt5.* calls ...
        client.disconnect()

    Usage (context manager — preferred):
        with MT5Client() as client:
            # ... use mt5.* calls ...
    """

    def __init__(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
        timeout_ms: int = 60_000,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.login = login or settings.mt5_login
        self.password = password or settings.mt5_password
        self.server = server or settings.mt5_server
        self.path = path or settings.mt5_path
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.retry_delay = retry_delay
        self._connected = False

    # ── Public API ───────────────────────────────────────────────────────────

    def connect(self) -> None:
        """
        Initialize the MT5 terminal and log in.
        Retries up to self.retries times on failure.
        Raises MT5ConnectionError on final failure.
        """
        for attempt in range(1, self.retries + 1):
            log.info(
                f"MT5 connect attempt {attempt}/{self.retries} → "
                f"login={self.login}, server={self.server}"
            )
            try:
                self._initialize_and_login()
                self._connected = True
                info = mt5.terminal_info()
                account = mt5.account_info()
                log.info(
                    f"Connected ✓ | terminal={info.name if info else 'N/A'} | "
                    f"account={account.login if account else 'N/A'} | "
                    f"balance=${account.balance:,.2f}" if account else "Connected ✓"
                )
                return
            except MT5ConnectionError as exc:
                log.warning(f"Attempt {attempt} failed: {exc}")
                if attempt < self.retries:
                    log.info(f"Retrying in {self.retry_delay}s …")
                    time.sleep(self.retry_delay)

        raise MT5ConnectionError(
            f"Could not connect to MT5 after {self.retries} attempts. "
            f"Last error: {mt5.last_error()}"
        )

    def disconnect(self) -> None:
        """Cleanly shut down the MT5 connection."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            log.info("MT5 disconnected.")

    def is_connected(self) -> bool:
        """Return True if the terminal is currently reachable."""
        if not self._connected:
            return False
        info = mt5.terminal_info()
        return info is not None and info.connected

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self) -> "MT5Client":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.disconnect()
        return False   # don't suppress exceptions

    # ── Private helpers ──────────────────────────────────────────────────────

    def _initialize_and_login(self) -> None:
        """One attempt: mt5.initialize() then mt5.login()."""
        init_kwargs: dict = {"timeout": self.timeout_ms}
        if self.path:
            terminal_path = Path(self.path)
            if not terminal_path.exists():
                raise MT5ConnectionError(
                    f"MT5 terminal executable not found: {self.path}"
                )
            init_kwargs["path"] = str(terminal_path)

        ok = mt5.initialize(**init_kwargs)
        if not ok:
            raise MT5ConnectionError(
                f"mt5.initialize() failed: {mt5.last_error()}"
            )

        # If login details provided, authenticate
        if self.login and self.password and self.server:
            ok = mt5.login(
                login=self.login,
                password=self.password,
                server=self.server,
                timeout=self.timeout_ms,
            )
            if not ok:
                mt5.shutdown()
                raise MT5ConnectionError(
                    f"mt5.login() failed for login={self.login}: {mt5.last_error()}"
                )
