import sqlite3

conn = sqlite3.connect("trading_bot.db")
c = conn.cursor()
c.execute("UPDATE trades SET direction = 'long' WHERE LOWER(direction) LIKE '%bull%' OR LOWER(direction) = 'buy'")
c.execute("UPDATE trades SET direction = 'short' WHERE LOWER(direction) LIKE '%bear%' OR LOWER(direction) = 'sell'")
conn.commit()

c.execute("SELECT COUNT(*), direction FROM trades GROUP BY direction")
print("Trades breakdown by direction:", c.fetchall())

c.execute("SELECT COUNT(*) FROM trades")
print("Total trades in database:", c.fetchone()[0])
conn.close()
