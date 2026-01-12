# app/main.py
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List
from collections.abc import AsyncIterator

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.websockets import WebSocketDisconnect

from .state import update_status_periodically, connected_websockets, router_manager
from .pages import WS_TOKENS, register_pages
from .db import init_db
from .notifications import start_telegram_worker, stop_telegram_worker


# --- Paths ---
APP_DIR = Path(__file__).resolve().parent

# --- Typed app state ---
class AppState:
    shutdown_event: asyncio.Event
    background_tasks: List[asyncio.Task]

# --- Typed FastAPI ---
class App(FastAPI):
    state: AppState

# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: App) -> AsyncIterator[None]:
    # ===== STARTUP =====
    app.state.shutdown_event = asyncio.Event()
    app.state.background_tasks = []

    init_db()
    await router_manager.load()

    task = asyncio.create_task(
        update_status_periodically(app.state.shutdown_event)
    )
    app.state.background_tasks.append(task)
    # start Telegram worker
    start_telegram_worker()

    try:
        yield
    finally:
        # ===== SHUTDOWN =====
        app.state.shutdown_event.set()

        for ws in list(connected_websockets):
            try:
                await ws.close(code=1001)
            except Exception as e:
                print(f"WS close error: {e}")

        connected_websockets.clear()

        for task in app.state.background_tasks:
            task.cancel()

        await asyncio.gather(*app.state.background_tasks, return_exceptions=True)
        await router_manager.shutdown()
        # stop telegram worker
        await stop_telegram_worker()


# --- App instance ---

app = App(lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-secret-change-me"),
    same_site="lax",
)

templates = Jinja2Templates(directory=APP_DIR / "templates")

app.mount(
    "/static",
    StaticFiles(directory=APP_DIR / "static"),
    name="static",
)

register_pages(app, templates)


# --- WebSocket ---

@app.websocket("/ws/status")
async def ws_status(ws: WebSocket):
    token = ws.query_params.get("token")
    entry = WS_TOKENS.pop(token, None)

    if not entry:
        await ws.close(code=1008)
        return

    user, _ = entry  # validated

    await ws.accept()
    connected_websockets.add(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_websockets.discard(ws)

