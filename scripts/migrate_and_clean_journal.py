"""
scripts/migrate_and_clean_journal.py
──────────────────────────────────────
Migrates trading_bot.db SQLite database:
1. Adds `source` column if missing.
2. Tags existing trades:
   - 'bt-*' -> 'backtest'
   - 'manual-*' -> 'manual_note'
   - 'sim_*' / others -> 'paper'
3. Displays updated trade breakdown by source.
"""

import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "trading_bot.db"

def migrate():
    if not DB_PATH.exists():
        print(f"Database file not found at {DB_PATH}")
        return

    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check trades table columns
    cursor.execute("PRAGMA table_info(trades);")
    columns = [row[1] for row in cursor.fetchall()]

    if "source" not in columns:
        print("Adding missing 'source' column to 'trades' table...")
        cursor.execute("ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'paper';")
        conn.commit()
        print("Column 'source' added successfully.")
    else:
        print("'source' column already exists.")

    # Check config table columns
    cursor.execute("PRAGMA table_info(config);")
    config_cols = [row[1] for row in cursor.fetchall()]

    if "paper_trading_start_date" not in config_cols:
        print("Adding missing 'paper_trading_start_date' column to 'config' table...")
        cursor.execute("ALTER TABLE config ADD COLUMN paper_trading_start_date TEXT DEFAULT '2026-09-08T17:30:00Z';")
        conn.commit()
        print("Column 'paper_trading_start_date' added successfully.")

    # Data Hygiene Tagging
    cursor.execute("UPDATE trades SET source = 'backtest' WHERE id LIKE 'bt-%';")
    cursor.execute("UPDATE trades SET source = 'manual_note' WHERE id LIKE 'manual-%';")
    cursor.execute("UPDATE trades SET source = 'paper' WHERE id LIKE 'sim_%' OR source IS NULL OR source = '';")
    conn.commit()

    # Summary report
    cursor.execute("SELECT source, COUNT(*) FROM trades GROUP BY source;")
    rows = cursor.fetchall()
    
    print("\n==========================================")
    print("      TRADE JOURNAL SOURCE BREAKDOWN      ")
    print("==========================================")
    for source_val, count in rows:
        print(f"  • {source_val.upper():<15}: {count} trades")
    print("==========================================\n")

    conn.close()

if __name__ == "__main__":
    migrate()
