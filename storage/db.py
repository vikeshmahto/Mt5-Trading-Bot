"""
storage/db.py
─────────────
Database connection manager.

Supports:
  • SQLite  — default for backtest / local dev.
              DB_URL=sqlite:///trading.db
  • PostgreSQL / Neon — production.
              DB_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require

The module exposes:
  get_engine()       → SQLAlchemy Engine (cached singleton)
  get_session()      → context-manager yielding a Session
  init_db()          → create all tables (idempotent)
  close_engine()     → dispose engine (call on shutdown)

Usage:
    from storage.db import get_session, init_db

    init_db()   # once at startup

    with get_session() as session:
        session.add(some_model_instance)
        session.commit()
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from core.logger import get_logger
from storage.models import Base

log = get_logger(__name__)

# ── Engine singleton ──────────────────────────────────────────────────────────

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_engine(db_url: str | None = None) -> Engine:
    """
    Return the cached SQLAlchemy engine.
    Creates it on the first call.

    Args:
        db_url: Override the URL from settings (useful in tests).
    """
    global _engine, _SessionFactory

    if _engine is not None:
        return _engine

    url = db_url or settings.db_url

    # ── Engine kwargs per dialect ─────────────────────────────────────────────
    kwargs: dict = {}

    if url.startswith("sqlite"):
        # SQLite: allow multi-thread access (needed for backtest parallelism)
        kwargs["connect_args"] = {"check_same_thread": False}
        # Pool class: StaticPool keeps one connection (prevents file locking)
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool

    elif url.startswith("postgresql") or url.startswith("postgres"):
        # Neon / PostgreSQL: connection pool tuned for single-process trading bot
        kwargs["pool_size"]        = 5
        kwargs["max_overflow"]     = 2
        kwargs["pool_pre_ping"]    = True   # detect stale connections
        kwargs["pool_recycle"]     = 300    # recycle every 5 min (Neon idle timeout)
        # Neon requires SSL — included in the URL as ?sslmode=require
        # but we enforce it here too just in case
        if "sslmode" not in url:
            url = url + ("&" if "?" in url else "?") + "sslmode=require"

    log.info(f"Creating DB engine: {_redact_url(url)}")
    _engine = create_engine(url, echo=False, **kwargs)

    # SQLite: enable WAL mode and foreign key enforcement
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _SessionFactory = sessionmaker(bind=_engine, autoflush=True, autocommit=False)
    return _engine


def init_db(db_url: str | None = None) -> None:
    """
    Create all tables defined in storage/models.py.
    Safe to call multiple times (CREATE TABLE IF NOT EXISTS semantics).

    Call this once at application startup before any DB operations.
    """
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    log.info("Database tables initialised.")

    # Quick connectivity check
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    log.info("DB connectivity check: OK")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session as a context manager.
    Automatically commits on success, rolls back on exception.

    Usage:
        with get_session() as session:
            session.add(obj)
            # commit happens automatically on exit
    """
    if _SessionFactory is None:
        get_engine()   # ensures _SessionFactory is set

    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_engine() -> None:
    """Dispose the engine (release all connections). Call on clean shutdown."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
        log.info("DB engine disposed.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _redact_url(url: str) -> str:
    """Hide password in log output."""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        if p.password:
            safe = p._replace(netloc=f"{p.username}:***@{p.hostname}" +
                              (f":{p.port}" if p.port else ""))
            return urlunparse(safe)
    except Exception:
        pass
    return url
