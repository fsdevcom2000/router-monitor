# app/log_stream.py
# WebSocket handler for logs

import asyncio
import logging

log_queue = asyncio.Queue()
connected_log_clients = set()

class WebSocketLogHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        try:
            log_queue.put_nowait(msg)
        except Exception:
            pass

# Create handler
log_handler = WebSocketLogHandler()
log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

# Connect to logger uvicorn/fastapi
logging.getLogger("uvicorn").addHandler(log_handler)
logging.getLogger("uvicorn.access").addHandler(log_handler)
logging.getLogger("uvicorn.error").addHandler(log_handler)
logging.getLogger("fastapi").addHandler(log_handler)

# Another app loger
logging.getLogger("app").addHandler(log_handler)
