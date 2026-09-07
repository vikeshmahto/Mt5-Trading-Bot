import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
from app.logging_setup import ws_queues
import MetaTrader5 as mt5

router = APIRouter()

@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    
    # Register a queue for this connection
    queue = asyncio.Queue()
    ws_queues.append(queue)
    
    async def send_ticks():
        """Periodically sends the latest tick price for each symbol."""
        while True:
            try:
                tick = mt5.symbol_info_tick("XAUUSD")
                if tick:
                    await websocket.send_json({
                        "type": "tick",
                        "data": {
                            "symbol": "XAUUSD",
                            "bid": tick.bid,
                            "ask": tick.ask,
                            "time": datetime.utcfromtimestamp(tick.time).isoformat()
                        }
                    })
            except Exception:
                pass
            await asyncio.sleep(1)
            
    try:
        tick_task = asyncio.create_task(send_ticks())
        
        while True:
            # Drain the queue and send any pending log/position messages
            try:
                msg = queue.get_nowait()
                await websocket.send_json(msg)
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.1)
                
    except WebSocketDisconnect:
        pass
    finally:
        tick_task.cancel()
        ws_queues.remove(queue)
