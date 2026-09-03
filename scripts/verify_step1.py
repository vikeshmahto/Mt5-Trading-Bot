"""
scripts/verify_step1.py
───────────────────────
Smoke-test for Step 1: verify config loads correctly.

Run from project root:
    python scripts/verify_step1.py
"""

import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from core.logger import get_logger

log = get_logger(__name__, level=settings.log_level)


def main() -> None:
    log.info("=" * 60)
    log.info("STEP 1 — Config + Logger Smoke Test")
    log.info("=" * 60)

    # ── Instruments ──────────────────────────────────────────────
    log.info(f"Active symbols     : {settings.active_symbols}")
    for sym, cfg in settings.instruments.items():
        log.info(f"  [{sym}]")
        log.info(f"    Description    : {cfg.description}")
        log.info(f"    Bias TFs       : {cfg.bias_timeframes}")
        log.info(f"    Setup TFs      : {cfg.setup_timeframes}")
        log.info(f"    Entry TF       : {cfg.entry_timeframe}")
        log.info(f"    Target points  : {cfg.target_points}")
        log.info(f"    Sessions       : {list(cfg.sessions.keys())}")
        for sess_name, sess in cfg.sessions.items():
            log.info(f"      {sess_name}: {sess.start} → {sess.end} UTC")

    # ── Risk ─────────────────────────────────────────────────────
    r = settings.risk
    log.info("")
    log.info("Risk config:")
    log.info(f"  Risk per trade     : {r.position_sizing.risk_per_trade * 100:.1f}%")
    log.info(f"  Max concurrent     : {r.limits.max_concurrent_trades}")
    log.info(f"  Max daily loss     : {r.limits.max_daily_loss * 100:.1f}%")
    log.info(f"  Min confluence     : {r.scoring.min_score_to_trade}")
    log.info(f"  Min R:R            : {r.scoring.min_rr_ratio}")
    log.info(f"  Backtest balance   : ${r.backtest.initial_balance:,.0f}")

    # ── Environment ──────────────────────────────────────────────
    log.info("")
    log.info(f"Environment        : {settings.environment}")
    log.info(f"DB URL             : {settings.db_url}")
    log.info(f"MT5 login          : {settings.mt5_login if settings.mt5_login else '(not set)'}")
    log.info(f"MT5 server         : {settings.mt5_server or '(not set)'}")

    log.info("")
    log.info("✅  Step 1 PASSED — config + logger working correctly.")


if __name__ == "__main__":
    main()
