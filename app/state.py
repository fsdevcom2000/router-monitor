import asyncio
import logging
from typing import Dict, Set, Tuple
from starlette.websockets import WebSocket

from .router_manager import RouterManager
from .notifications import send_telegram, fmt_down, fmt_up, fmt_reconnect_alert

logger = logging.getLogger(__name__)

ROUTER_APIS: Dict[str, object] = {}
STATUS_CACHE: Dict[str, dict] = {}
CACHE_INTERVAL = 5
TIMEOUT_PER_ROUTER = 5

_cache_lock = asyncio.Lock()
connected_websockets: Set[WebSocket] = set()
router_manager = RouterManager()

# --- Telegram notifications ------------------------
# name -> "up" / "down"
ROUTER_STATE = {}
# name -> how many times in a row was it down
ROUTER_DOWN_STREAK = {}
# name -> last sent reconnects alert
ROUTER_RECONNECT_ALERT = {}
# ---------------------------------------------------



async def _fetch_router_status(name: str) -> Tuple[str, dict]:
    api = ROUTER_APIS.get(name)

    if not api:
        try:
            api = await router_manager.get_api(name)
        except Exception as e:
            logger.warning("get_api(%s) failed: %s", name, e)
            return name, {"status": "No"}

        if api:
            ROUTER_APIS[name] = api
        else:
            return name, {"status": "No"}

    try:
        status = await asyncio.wait_for(
            asyncio.to_thread(api.get_status),
            timeout=TIMEOUT_PER_ROUTER,
        )

        if isinstance(status, dict) and "error" in status:
            logger.warning("Router %s returned error status: %s", name, status)
            return name, {"status": "No"}

        return name, status

    except asyncio.TimeoutError:
        logger.warning("Timeout getting status from router %s", name)
        return name, {"status": "No"}

    except Exception as e:
        logger.exception("Error getting status from router %s: %s", name, e)
        try:
            api.close()
        except Exception:
            pass
        ROUTER_APIS.pop(name, None)
        return name, {"status": "No"}



async def update_status_periodically(shutdown_event: asyncio.Event):
    try:
        while not shutdown_event.is_set():
            try:
                routers = await router_manager.get_routers()
            except Exception as e:
                logger.exception("Error getting routers list: %s", e)
                await asyncio.sleep(CACHE_INTERVAL)
                continue

            logger.debug("Polling routers: %s", routers)

            tasks = [
                _fetch_router_status(name)
                for name in routers
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            snapshot: Dict[str, dict] = {}

            for name, result in zip(routers, results):
                # name is the key from routers (router name)
                if isinstance(result, Exception):
                    logger.exception("Task for router %s failed: %s", name, result)
                    status = {"status": "No"}
                    snapshot[name] = status

                    # === TELEGRAM NOTIFICATIONS FOR EXCEPTIONS ===
                    curr_status = "down"
                    prev_status = ROUTER_STATE.get(name)

                    # increase streak drops
                    ROUTER_DOWN_STREAK[name] = ROUTER_DOWN_STREAK.get(name, 0) + 1

                    # DOWN - only if 3 times in a row
                    if ROUTER_DOWN_STREAK[name] == 3:
                        await send_telegram(fmt_down(name))

                    # Save current state
                    ROUTER_STATE[name] = curr_status

                    # there are no reconnects here, skip it
                    continue

                # normal result
                r_name, status = result
                snapshot[r_name] = status

                # === TELEGRAM NOTIFICATIONS ===

                curr_status = "up" if status.get("status") == "Yes" else "down"
                prev_status = ROUTER_STATE.get(r_name)

                # --- DOWN streak logic ---
                if curr_status == "down":
                    ROUTER_DOWN_STREAK[r_name] = ROUTER_DOWN_STREAK.get(r_name, 0) + 1
                else:
                    ROUTER_DOWN_STREAK[r_name] = 0

                # DOWN only if 3 checks in a row
                if curr_status == "down" and ROUTER_DOWN_STREAK[r_name] == 3:
                    await send_telegram(fmt_down(r_name))

                # UP event (only if previously down)
                if curr_status == "up" and prev_status == "down":
                    await send_telegram(fmt_up(r_name))

                # Save state
                ROUTER_STATE[r_name] = curr_status

                # --- Reconnect alert ---
                reconnects = status.get("reconnects")
                if isinstance(reconnects, int):
                    last_alert = ROUTER_RECONNECT_ALERT.get(r_name, 0)

                    # send an alert every +10 reconnects
                    if reconnects >= last_alert + 10:
                        await send_telegram(fmt_reconnect_alert(r_name, reconnects))
                        ROUTER_RECONNECT_ALERT[r_name] = reconnects

            async with _cache_lock:
                STATUS_CACHE.update(snapshot)

            logger.debug("Snapshot to send: %s", snapshot)

            if connected_websockets:
                dead = set()
                for ws in connected_websockets:
                    try:
                        await ws.send_json(snapshot)
                    except Exception:
                        dead.add(ws)

                connected_websockets.difference_update(dead)

            await asyncio.sleep(CACHE_INTERVAL)

    except asyncio.CancelledError:
        logger.info("update_status_periodically cancelled")
        raise
