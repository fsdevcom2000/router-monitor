# app/router_manager.py
import asyncio
from typing import Dict, Optional

from .crypto import decrypt_password, encrypt_password
from .db import get_routers, get_connection
from .mikrotik import RouterAPI
from .models import Router


class RouterManager:
    __slots__ = ("_routers", "_lock")
    def __init__(self):
        self._routers: Dict[str, Router] = {}
        self._lock = asyncio.Lock()

    # =========================
    # Lifecycle
    # =========================

    async def load(self) -> None:
        """
        Load routers from DB into memory.
        DB is synchronous -> run in thread.
        """
        rows = await asyncio.to_thread(get_routers)

        routers: Dict[str, Router] = {}
        for r in rows:
            routers[r["name"]] = Router(
                name=r["name"],
                host=r["host"],
                username=r["username"],
                password=decrypt_password(r["password"]),
                port=r.get("port", 8728),
                enabled=r.get("enabled", 1),
            )

        async with self._lock:
            self._routers = routers

    async def reload(self) -> None:
        await self.load()

    async def shutdown(self) -> None:
        """
        Graceful shutdown hook.
        """
        async with self._lock:
            self._routers.clear()

    # =========================
    # Read access (in-memory)
    # =========================

    async def get_routers(self) -> Dict[str, Router]:
        async with self._lock:
            return dict(self._routers)

    async def get_router(self, name: str) -> Optional[Router]:
        async with self._lock:
            return self._routers.get(name)

    # =========================
    # Router API factory
    # =========================

    async def get_api(self, name: str) -> Optional[RouterAPI]:
        """
        Returns RouterAPI instance or None.
        Lock is held only to read router data.
        """
        async with self._lock:
            router = self._routers.get(name)

        if not router or not router.enabled:
            return None

        return RouterAPI(
            host=router.host,
            username=router.username,
            password=router.password,
            port=router.port,
        )

    # =========================
    # CRUD (DB)
    # =========================

    async def add_router(
        self,
        name: str,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
        enabled: int = 1,
    ) -> None:
        await asyncio.to_thread(
            self._add_router_sync,
            name,
            host,
            username,
            password,
            port,
            enabled,
        )
        await self.reload()

    async def update_router(
        self,
        name: str,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
        enabled: int = 1,
    ) -> None:
        await asyncio.to_thread(
            self._update_router_sync,
            name,
            host,
            username,
            password,
            port,
            enabled,
        )
        await self.reload()

    async def delete_router(self, name: str) -> None:
        await asyncio.to_thread(self._delete_router_sync, name)
        await self.reload()

    # =========================
    # Sync DB helpers
    # =========================

    def _add_router_sync(
        self,
        name: str,
        host: str,
        username: str,
        password: str,
        port: int,
        enabled: int,
    ) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO routers (name, host, username, password, port, enabled)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    host,
                    username,
                    encrypt_password(password),
                    port,
                    enabled,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _update_router_sync(
        self,
        name: str,
        host: str,
        username: str,
        password: str,
        port: int,
        enabled: int,
    ) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE routers
                SET host=?, username=?, password=?, port=?, enabled=?
                WHERE name=?
                """,
                (
                    host,
                    username,
                    encrypt_password(password),
                    port,
                    enabled,
                    name,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _delete_router_sync(self, name: str) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM routers WHERE name=?", (name,))
            conn.commit()
        finally:
            conn.close()

    async def get_ip(self, name: str) -> Optional[str]:
        async with self._lock:
            router = self._routers.get(name)
            if not router:
                return None
            return router.host


