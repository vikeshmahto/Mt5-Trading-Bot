"""
scripts/run_xauusd_journal_backtest.py
──────────────────────────────────────
Backtest XAUUSD (Gold) across the recent 6-month period (March 2026 - September 2026)
and sync the simulated trades into trading_bot.db so they immediately display
in the Trade Journal and Performance views.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backtest.engine import BacktestEngine
from backtest.metrics import calculate_metrics
from config.settings import settings as bot_settings
from backend.app.db.models import TradeModel, LogEntryModel

DB_PATH = ROOT_DIR / "trading_bot.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

START_DATE = "2026-03-01"
END_DATE   = "2026-09-02"
SYMBOL     = "XAUUSD"


def get_session_name(dt: datetime) -> str:
    """Classify UTC timestamp into trading sessions."""
    hour = dt.hour
    if 0 <= hour < 7:
        return "asian"
    elif 7 <= hour < 13:
        return "london"
    elif 13 <= hour < 22:
        return "ny"
    else:
        return "asian"


def format_setup_name(sig_type: str) -> str:
    mapping = {
        "ob_fvg": "OB+FVG confluence",
        "ob_retest": "Order Block",
        "fvg_retest": "Fair Value Gap",
        "sweep_entry": "Liquidity Sweep",
    }
    return mapping.get(sig_type.lower(), sig_type.replace("_", " ").title())


def main():
    print("=" * 76)
    print(f"  QUANT BACKTEST & TRADE JOURNAL SYNC: {SYMBOL}")
    print(f"  Range: {START_DATE} to {END_DATE} (Recent 6 Months)")
    print("=" * 76)

    # 1. Load multi-timeframe cache
    bars_dict: dict[str, pd.DataFrame] = {}
    for tf in ["D1", "H4", "H1", "M15"]:
        p = ROOT_DIR / f"data/cache/{SYMBOL}_{tf}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"Missing parquet file: {p}")
        bars_dict[tf] = pd.read_parquet(p)
        print(f"  Loaded {tf}: {len(bars_dict[tf]):,} bars")

    # 2. Configure engine
    inst_config = bot_settings.get_instrument(SYMBOL)
    risk_config = bot_settings.risk

    engine = BacktestEngine(
        symbol=SYMBOL,
        bars_dict=bars_dict,
        instrument_config=inst_config,
        risk_config=risk_config,
        start_date=START_DATE,
        end_date=END_DATE,
        persist=False,
    )

    print("\n>>> Executing backtest across historical bars...")
    result = engine.run()
    metrics = calculate_metrics(
        trades=result.trades,
        equity_curve=result.equity_curve,
        initial_balance=risk_config.backtest.initial_balance,
    )

    print("\n" + "=" * 76)
    print("  BACKTEST PERFORMANCE RESULTS")
    print("=" * 76)
    print(f"  Total Signals Generated : {result.signals_generated}")
    print(f"  Total Closed Trades     : {metrics.total_trades}")
    print(f"  Wins / Losses           : {metrics.wins} / {metrics.losses}")
    print(f"  Win Rate                : {metrics.win_rate * 100:.1f}%")
    print(f"  Gross Profit            : ${metrics.gross_profit:+,.2f}")
    print(f"  Gross Loss              : ${metrics.gross_loss:+,.2f}")
    print(f"  Net PnL                 : ${metrics.net_pnl:+,.2f}")
    print(f"  Profit Factor           : {metrics.profit_factor:.2f}")
    print(f"  Expectancy (R)          : {metrics.expectancy_r:+.2f}R")
    print(f"  Max Drawdown            : {metrics.max_drawdown_pct * 100:.2f}% (${metrics.max_drawdown_dollars:,.2f})")
    print("=" * 76)

    # 3. Database Sync
    print(f"\n>>> Connecting to database: {DB_PATH}")
    db_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = Session()

    synced_count = 0
    total_points = 0.0

    try:
        for idx, tr in enumerate(result.trades, start=1):
            # Deterministic unique ID for backtest trade
            trade_id = f"bt-{SYMBOL.lower()}-{tr.entry_bar_ts.strftime('%Y%m%d%H%M')}-{idx:02d}"

            # Check if trade already exists
            existing = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if existing:
                continue

            entry_dt = tr.entry_bar_ts.to_pydatetime()
            if entry_dt.tzinfo is not None:
                entry_dt = entry_dt.astimezone(timezone.utc).replace(tzinfo=None)

            exit_dt = tr.exit_bar_ts.to_pydatetime() if tr.exit_bar_ts is not None else None
            if exit_dt and exit_dt.tzinfo is not None:
                exit_dt = exit_dt.astimezone(timezone.utc).replace(tzinfo=None)

            direction_str = tr.direction.lower()
            pnl_r = round(tr.pnl_r, 2) if tr.pnl_r is not None else 0.0

            if pnl_r > 0:
                outcome_str = "win"
                bias_correct_str = "yes"
                mistake_str = "clean"
            elif pnl_r < -0.2:
                outcome_str = "loss"
                bias_correct_str = "no"
                mistake_str = "wrong_bias"
            else:
                outcome_str = "breakeven"
                bias_correct_str = "partial"
                mistake_str = "clean"

            # Points captured calculation
            if tr.exit_price and tr.entry_price:
                if direction_str == "long":
                    points = round(tr.exit_price - tr.entry_price, 2)
                else:
                    points = round(tr.entry_price - tr.exit_price, 2)
            else:
                points = 0.0
            total_points += points

            # Confluence
            sig_type = tr.signal.signal_type.value
            setup_display = format_setup_name(sig_type)
            confluence_str = "triple_stack" if sig_type == "ob_fvg" else ("double" if tr.signal.confluence_score >= 75 else "single")

            # HTF Bias
            d1_bias = tr.signal.d1_bias.bias.value if tr.signal.d1_bias else None
            h4_bias = tr.signal.h4_bias.bias.value if tr.signal.h4_bias else None
            htf_bias_val = d1_bias or h4_bias or ("bullish" if direction_str == "long" else "bearish")
            htf_reason_val = f"D1: {d1_bias or 'N/A'} structure | H4: {h4_bias or 'N/A'}"

            # MAE / MFE estimates
            risk_dist = abs(tr.entry_price - tr.stop_loss)
            reward_dist = abs(tr.take_profit - tr.entry_price)
            mae_val = round(risk_dist * (0.85 if outcome_str == "loss" else 0.35), 2)
            mfe_val = round(reward_dist * (1.0 if outcome_str == "win" else 0.30), 2)

            session_val = get_session_name(entry_dt)

            review_notes_val = (
                f"SMC Backtest Trade #{idx}. Exit Reason: {tr.exit_reason}. "
                f"Realized PnL: ${tr.pnl:+,.2f} ({pnl_r:+.2f}R). Commission: ${tr.commission:.2f}."
            )

            record = TradeModel(
                id=trade_id,
                symbol=SYMBOL,
                direction=direction_str,
                entry_price=round(tr.entry_price, 2),
                exit_price=round(tr.exit_price, 2) if tr.exit_price else None,
                sl=round(tr.stop_loss, 2),
                tp=round(tr.take_profit, 2),
                r_multiple=pnl_r,
                outcome=outcome_str,
                setup_type=setup_display,
                session=session_val,
                opened_at=entry_dt,
                closed_at=exit_dt,
                source="backtest",

                # 1. Context / Bias
                htf_bias=htf_bias_val,
                htf_reason=htf_reason_val,
                bias_correct=bias_correct_str,

                # 2. Setup
                setup_timeframe=tr.signal.setup_timeframe or "M15",
                confluence=confluence_str,
                screenshot_url=None,

                # 3. Execution
                entry_timeframe="M15",
                entry_trigger="clean_retest" if "retest" in sig_type else "sweep_entry",
                sl_logic="structure",
                planned_rr=round(tr.signal.risk_reward, 2),
                risk_pct=1.0,

                # 4. Outcome & Excursion
                points_captured=points,
                mae=mae_val,
                mfe=mfe_val,

                # 5. Process & Psychology
                rule_adherence="followed_rules",
                emotional_state="calm",
                external_factor="normal",

                # 6. Post-trade review
                textbook_comparison=f"Systematic algorithmic execution of {setup_display} on {SYMBOL}.",
                mistake_type=mistake_str,
                review_notes=review_notes_val,
            )

            db.add(record)
            synced_count += 1

        # Add system log entry
        log_entry = LogEntryModel(
            id=f"log-{int(datetime.utcnow().timestamp())}",
            timestamp=datetime.utcnow(),
            level="success",
            message=f"Backtest completed for {SYMBOL} ({START_DATE} to {END_DATE}): {len(result.trades)} trades synced to Journal. Net PnL: ${metrics.net_pnl:+,.2f} ({metrics.expectancy_r:+.2f}R).",
        )
        db.add(log_entry)

        db.commit()
        print(f"\n>>> Successfully synced {synced_count} backtested trades into SQLite trading_bot.db!")
        print(f">>> Total Points Captured across backtest: {total_points:+.2f} pts")

    except Exception as e:
        db.rollback()
        print(f"Error syncing to DB: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
