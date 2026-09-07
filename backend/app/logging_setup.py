import logging
import uuid
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models import LogEntryModel
from app.schemas.log_entry import LogEntry
import asyncio

# A list of async queues to push log entries to for active websocket connections
ws_queues = []

def get_logger():
    # Setup basic python logger
    logger = logging.getLogger("smc_bot")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

logger = get_logger()

async def broadcast_log(entry: LogEntry):
    for q in ws_queues:
        await q.put({"type": "log", "data": entry.model_dump(by_alias=True)})

def log_system_event(level: str, message: str):
    """
    level: 'info', 'warning', 'error', 'success'
    Logs to python logger, saves to DB, and pushes to WS.
    """
    # Python logger
    if level == 'info' or level == 'success':
        logger.info(message)
    elif level == 'warning':
        logger.warning(message)
    elif level == 'error':
        logger.error(message)
        
    entry_id = str(uuid.uuid4())
    ts = datetime.utcnow()
    
    # Save to DB
    db = SessionLocal()
    try:
        db_log = LogEntryModel(id=entry_id, timestamp=ts, level=level, message=message)
        db.add(db_log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save log to DB: {e}")
    finally:
        db.close()
        
    # Create schema and broadcast
    entry = LogEntry(id=entry_id, timestamp=ts, level=level, message=message)
    
    # Run broadcast in background
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_log(entry))
    except RuntimeError:
        pass # Not in an async loop (e.g. during startup)
