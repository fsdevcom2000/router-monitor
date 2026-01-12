# app/notifications.py
# Telegram worker for notifications
import os
import asyncio
import logging
import aiohttp
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_ID", "").split(",")

# Remove empty elements
CHAT_IDS = [c.strip() for c in CHAT_IDS if c.strip()]

TELEGRAM_ENABLED = bool(BOT_TOKEN and CHAT_IDS)

if not TELEGRAM_ENABLED:
    logger.warning("Telegram notifications disabled: BOT_TOKEN or CHAT_ID missing.")

_worker_shutdown = asyncio.Event()
_worker_task: asyncio.Task | None = None

SERVER_NAME = "Routers|MikroTik"


#   MESSAGE QUEUE

_message_queue = asyncio.Queue()
_worker_started = False


async def telegram_worker():
    logger.info("Telegram worker started")

    while not _worker_shutdown.is_set():
        try:
            text = await asyncio.wait_for(_message_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue  # check shutdown every 1 sec

        await _send_to_all_chats(text)
        _message_queue.task_done()

    logger.info("Telegram worker stopped")

def start_telegram_worker():
    global _worker_task
    if _worker_task is None:
        _worker_task = asyncio.create_task(telegram_worker())

async def stop_telegram_worker():
    _worker_shutdown.set()

    # Wait for all messages to be sent
    await _message_queue.join()

    # Wait for background task to complete
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except Exception:
            pass


async def send_telegram(text: str):
    """Public function - simply puts a message in a queue."""
    if not TELEGRAM_ENABLED:
        return False

    await _message_queue.put(text)
    return True


#   RETRY + MULTI-CHAT LOGIC

async def _send_to_all_chats(text: str):
    """Sends a message to all chats with retry."""
    for chat_id in CHAT_IDS:
        await _send_with_retry(chat_id, text)


async def _send_with_retry(chat_id: str, text: str):
    """Sending with retry mechanics."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    delays = [1, 3, 5]  # backoff

    for attempt, delay in enumerate(delays, start=1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload, timeout=10) as resp:

                    if resp.status == 200:
                        return True

                    # Telegram API error
                    try:
                        err = await resp.json()
                    except Exception:
                        err = await resp.text()

                    logger.error(
                        "Telegram API error (attempt %s, chat %s): %s",
                        attempt, chat_id, err
                    )

        except aiohttp.ClientConnectionError:
            logger.error("Telegram connection error (attempt %s)", attempt)

        except asyncio.TimeoutError:
            logger.error("Telegram timeout (attempt %s)", attempt)

        except Exception as e:
            logger.exception("Unexpected Telegram error: %s", e)

        # Retry
        await asyncio.sleep(delay)

    logger.error("Failed to send Telegram message after retries: %s", text)
    return False


#   MESSAGE FORMATTING

def fmt_down(name):
    return (f"*{SERVER_NAME}*\n\n"
            f"❌ *Device DOWN*\n\n"
            f"`{name}` is offline.")

def fmt_up(name):
    return (f"*{SERVER_NAME}*\n\n"
            f"✅ *Device UP*\n\n"
            f"`{name}` is online.")

def fmt_reconnect_alert(name, count):
    return (f"*{SERVER_NAME}*\n\n"
            f"⚠️ *High reconnect rate*\n\n"
            f"`{name}`: {count} reconnects.")
