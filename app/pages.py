# app/main.py
# All endpoints and templates

import asyncio
import secrets
import time
import paramiko
import json

from fastapi import Request, Form
from fastapi import WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from starlette.status import HTTP_302_FOUND

from .db import get_user, verify_password
from .db import list_users, add_user, update_user_role, update_user_password, delete_user, users_count
from .log_stream import log_queue, connected_log_clients
from .state import router_manager
from .state import ROUTER_APIS

# one-time WS tokens
WS_TOKENS = {}
WS_TOKEN_TTL = 30  # seconds


def register_pages(app, templates):

    # --- Main ---
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        if not request.session.get("user"):
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)


        routers = await router_manager.get_routers()
        router_names = list(routers.keys())

        # Checking user rights
        is_admin = request.session.get("role") == "admin"

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "router_names": router_names,
                "is_admin": is_admin
            }
        )

    # --- Auth ---
    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        users = users_count()
        if users == 0:  # If there are no users
            # Show a special form for creating the first user
            return templates.TemplateResponse("first_login.html", {"request": request, "error": None})
        return templates.TemplateResponse("login.html", {"request": request})

    @app.post("/login")
    async def login(request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(None)  # New parameter for confirmation
):
        users = list_users()

        # If this is the first login (no users)
        if not users:
            # Check that the passwords match
            if password_confirm is not None and password != password_confirm:
                return templates.TemplateResponse(
                    "first_login.html",
                    {
                        "request": request,
                        "error": "Passwords do not match!"
                    }
                )

            # Checking the minimum password length (8)
            if len(password) < 8:
                return templates.TemplateResponse(
                    "first_login.html",
                    {
                        "request": request,
                        "error": "Password must be at least 8 characters long!"
                    }
                )

            # Create the first user as admin
            add_user(username, password, "admin")
            request.session["user"] = username
            request.session["role"] = "admin"
            return RedirectResponse("/welcome", status_code=HTTP_302_FOUND)

        # Normal login
        user = get_user(username)
        if not user or not verify_password(password, user["password_hash"]):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

        request.session["user"] = username
        request.session["role"] = user["role"]
        return RedirectResponse("/welcome", status_code=HTTP_302_FOUND)


    # --- Welcome ---
    @app.get("/welcome", response_class=HTMLResponse)
    async def admin(request: Request):
        if not request.session.get("user"):
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        # Check user role
        is_admin = request.session.get("role") == "admin"
        return templates.TemplateResponse("welcome.html",{"request": request, "is_admin": is_admin})


    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

    @app.websocket("/ws/logs")
    async def logs_ws(ws: WebSocket):
        await ws.accept()
        connected_log_clients.add(ws)
        try:
            while True:
                msg = await log_queue.get()
                await ws.send_text(msg)
        except Exception:
            pass
        finally:
            connected_log_clients.remove(ws)

    # --- Logs ---
    @app.get("/admin/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse("logs.html", {"request": request})


    # --- WS-token ---
    @app.get("/ws-token")
    async def ws_token(request: Request):
        user = request.session.get("user")
        if not user:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        _cleanup_tokens()

        token = secrets.token_urlsafe(16)
        WS_TOKENS[token] = (user, time.time())
        return {"token": token}

    # --- Reload routers ---
    @app.post("/admin/reload-routers")
    async def reload_routers(request: Request):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        await router_manager.reload()
        return {"status": "ok"}

    # --- Routers List ---
    @app.get("/admin/routers", response_class=HTMLResponse)
    async def admin_routers(request: Request):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        routers = await router_manager.get_routers()
        return templates.TemplateResponse("admin_routers.html", {"request": request, "routers": routers.values()})

    # --- Add New Router ---
    @app.get("/admin/routers/add", response_class=HTMLResponse)
    async def add_router_page(request: Request):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse("admin_router_form.html", {"request": request, "action": "Add"})

    @app.post("/admin/routers/add")
    async def add_router(request: Request, name: str = Form(...), host: str = Form(...),
                         username: str = Form(...), password: str = Form(...), port: int = Form(8728)):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        await router_manager.add_router(name, host, username, password, port, enabled=1)
        return RedirectResponse("/admin/routers", status_code=HTTP_302_FOUND)

    # --- Edit Router ---
    @app.get("/admin/routers/edit/{name}", response_class=HTMLResponse)
    async def edit_router_page(request: Request, name: str):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        routers = await router_manager.get_routers()
        router = routers.get(name)
        if not router:
            return RedirectResponse("/admin/routers", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse("admin_router_form.html", {"request": request, "router": router, "action": "Edit"})

    @app.post("/admin/routers/edit/{name}")
    async def edit_router(request: Request, name: str, host: str = Form(...),
                          username: str = Form(...), password: str = Form(...), port: int = Form(8728)):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        await router_manager.update_router(name, host, username, password, port)
        return RedirectResponse("/admin/routers", status_code=HTTP_302_FOUND)

    # --- Delete router ---
    @app.post("/admin/routers/delete/{name}")
    async def delete_router(request: Request, name: str):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        await router_manager.delete_router(name)
        return RedirectResponse("/admin/routers", status_code=HTTP_302_FOUND)

    # --- Users List ---
    @app.get("/admin/users", response_class=HTMLResponse)
    async def admin_users(request: Request):
        if request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        users = list_users()
        return templates.TemplateResponse("admin_users.html", {"request": request, "users": users})

    # --- Add New User ---
    @app.get("/admin/users/add", response_class=HTMLResponse)
    async def add_user_page(request: Request):
        if request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse("admin_user_form.html", {"request": request, "action": "Add"})

    @app.post("/admin/users/add")
    async def add_user_post(
            request: Request,
            username: str = Form(...),
            password: str = Form(...),
            role: str = Form("viewer")
    ):
        if request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        add_user(username, password, role)
        return RedirectResponse("/admin/users", status_code=HTTP_302_FOUND)

    # --- Edit User ---
    @app.get("/admin/users/edit/{username}", response_class=HTMLResponse)
    async def edit_user_page(request: Request, username: str):
        if request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        user = get_user(username)
        if not user:
            return RedirectResponse("/admin/users", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse(
            "admin_user_form.html",
            {"request": request, "user": user, "action": "Edit"}
        )

    @app.post("/admin/users/edit/{username}")
    async def edit_user_post(
            request: Request,
            username: str,
            password: str = Form(""),
            role: str = Form(...)
    ):
        if request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        if password:
            update_user_password(username, password)
        update_user_role(username, role)
        return RedirectResponse("/admin/users", status_code=HTTP_302_FOUND)

    # --- Delete User ---
    @app.post("/admin/users/delete/{username}")
    async def delete_user_post(request: Request, username: str):
        if request.session.get("role") != "admin":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        if users_count() > 1:
            delete_user(username)
        return RedirectResponse("/admin/users", status_code=HTTP_302_FOUND)

    # --- Terminal ---
    @app.get("/router/{name}/terminal")
    async def router_terminal(name: str, request: Request):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse(
            "router_terminal.html",
            {"request": request, "router_name": name}
        )


    @app.websocket("/ws/ssh/{router}")
    async def ssh_terminal(ws: WebSocket, router: str):
        await ws.accept()

        r = await router_manager.get_router(router)
        if not r:
            await ws.send_text("Router not found\n")
            return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=r.host,
            port=22,
            username=r.username,
            password=r.password,
            timeout=5,
            allow_agent=False,
            look_for_keys=False
        )

        chan = ssh.invoke_shell(term='vt100')
        chan.settimeout(0.1)

        # IMPORTANT: MikroTik will not show a banner without CRLF
        chan.send("\r\n")

        # IMPORTANT: MikroTik is waiting for window-change
        chan.resize_pty(width=120, height=40)

        async def reader():
            while True:
                try:
                    data = chan.recv(1024)
                    if not data:
                        break
                    await ws.send_text(data.decode("utf-8", errors="ignore"))
                except Exception:
                    await asyncio.sleep(0.01)

        asyncio.create_task(reader())

        try:
            while True:
                try:
                    data = await ws.receive_text()
                except Exception:
                    break

                # Xterm.js send \r — MikroTik need \r\n
                if data == "\r":
                    chan.send("\r\n")
                else:
                    chan.send(data)
        finally:
            try:
                chan.close()
            except:
                pass
            try:
                ssh.close()
            except:
                pass


    # --- Router Log ---
    @app.get("/router/{name}/log")
    async def router_terminal(name: str, request: Request):
        if not request.session.get("user") or request.session.get("role") != "admin":
            return RedirectResponse("/login", status_code=HTTP_302_FOUND)
        return templates.TemplateResponse(
            "router_log.html",
            {"request": request, "router_name": name}
        )


    @app.websocket("/ws/log/{router}")
    async def ws_log(ws: WebSocket, router: str):
        await ws.accept()

        api = ROUTER_APIS.get(router)
        if not api:
            await ws.send_text(json.dumps({"error": "Router API not connected"}))
            await ws.close()
            return

        try:
            logs = api.get_logs(100)  # if you need more lines, just increase
            for line in logs:
                await ws.send_text(json.dumps(line))

        except Exception as e:
            await ws.send_text(json.dumps({"error": str(e)}))

        finally:
            await ws.close()


    # --- 404 Page Not Found ---
    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exc: Exception):
        """404 Error Handler"""
        # Checking if the client wants JSON or HTML
        accept_header = request.headers.get("accept", "")

        if "application/json" in accept_header:
            # Returning JSON for API requests
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found", "path": request.url.path}
            )
        else:
            # Returning an HTML page to the browser
            return templates.TemplateResponse(
                "404.html",
                {
                    "request": request,
                    "error": f"Page not found: {request.url.path}"
                },
                status_code=404
            )

    # --- Handling all other exceptions ---
    @app.exception_handler(500)
    async def server_error_exception_handler(request: Request, exc: Exception):
        """500 Error Handler"""
        accept_header = request.headers.get("accept", "")

        if "application/json" in accept_header:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
        else:
            return templates.TemplateResponse(
                "500.html",
                {
                    "request": request,
                    "error": "Internal server error. Please try again later."
                },
                status_code=500
            )


    def _cleanup_tokens():
        now = time.time()
        for t, (_, ts) in list(WS_TOKENS.items()):
            if now - ts > WS_TOKEN_TTL:
                WS_TOKENS.pop(t, None)

