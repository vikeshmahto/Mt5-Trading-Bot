import requests
import json
import time
from datetime import datetime

WEBHOOK_URL = "http://localhost:8000/api/internal/push"

def push_event(event_type, data):
    payload = {
        "event_type": event_type,
        "data": data
    }
    response = requests.post(WEBHOOK_URL, json=payload)
    print(f"Pushed {event_type} - Response: {response.status_code}")

print("Simulating heartbeat...")
push_event("heartbeat", {
    "timestamp": datetime.now().isoformat(),
    "extra_info": {
        "active_symbols": ["XAUUSD"]
    }
})

time.sleep(1)

ticket_id = 999888777
entry_time = datetime.now().isoformat()

print("Simulating trade_opened...")
push_event("trade_opened", {
    "symbol": "XAUUSD",
    "ticket": ticket_id,
    "entry_time": entry_time,
    "signal_type": "breakout"
})

print("Wait 3 seconds to observe the 'Active Open Trades' table...")
time.sleep(3)

print("Simulating trade_closed (winning trade!)...")
push_event("trade_closed", {
    "symbol": "XAUUSD",
    "ticket": ticket_id,
    "entry_time": entry_time,
    "pnl_usd": 210.75,
    "exit_reason": "Trailing_Stop",
    "signal_type": "breakout"
})

print("Simulation complete. Trade should have moved to 'Trade History'.")
