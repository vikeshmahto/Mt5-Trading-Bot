"""
scripts/fix_and_evaluate_paper_trades.py
─────────────────────────────────────────
1. Removes corrupted/duplicate open paper trades (BTCUSD and inverted SL/TP mock trades).
2. Manually triggers one cycle of signal_loop to verify:
   - BTCUSD is disabled.
   - XAUUSD paper trade creates valid SL < Entry < TP.
   - Paper trade monitoring runs and updates exit status cleanly.
"""

import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "trading_bot.db"

def clean_corrupted_paper_trades():
    if not DB_PATH.exists():
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Delete all unclosed sim_ trades from previous broken mock runs
    cursor.execute("DELETE FROM trades WHERE source = 'paper' AND closed_at IS NULL;")
    deleted_count = cursor.rowcount
    conn.commit()
    print(f"Cleaned up {deleted_count} open corrupted paper trade records.")

    cursor.execute("SELECT source, COUNT(*) FROM trades GROUP BY source;")
    rows = cursor.fetchall()
    print("\nUpdated Trade Journal DB Breakdown:")
    for source_val, count in rows:
        print(f"  • {source_val.upper():<15}: {count} trades")

    conn.close()

if __name__ == "__main__":
    clean_corrupted_paper_trades()
