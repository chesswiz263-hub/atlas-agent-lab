"""ATLAS hosted research beta.

Same-origin, password-gated experimental science endpoints. Not a multi-user
public SaaS gateway. Does not alter the original atlas.api implementation.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
SESSION_COOKIE = "atlas_beta_session"
SESSION_SECONDS = 12 * 3600
MAX_BODY_BYTES = 32_768
LOGIN_HTML = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>ATLAS — Research access</title>
<style>body{font:16px system-ui;background:#0d1218;color:#edf2f2;min-height:90vh;display:grid;place-items:center}
main{background:#182129;max-width:380px;width:calc(100% - 60px);padding:30px;border:1px solid #33424a;border-radius:17px}
input,button{box-sizing:border-box;width:100%;padding:13px;border-radius:9px;font:inherit;margin-top:12px}
input{background:#0d1218;border:1px solid #617078;color:white}button{background:#a4eadf;border:0;color:#172026;font-weight:700;cursor:pointer}
small{color:#a3bac1}#error{color:#ffb2af;min-height:1.6em}</style></head>
<body><main><h1>ATLAS Research</h1><p>Private research beta</p><small>Enter your access password. Research calls are limited; scientific outputs require independent review.</small>
<form id='f'><label for='password'>Access password</label><input id='password' type='password' minlength='16' autocomplete='current-password' required>
<button type='submit'>Unlock research</button></form><p id='error' role='alert'></p></main>
<script>document.getElementById('f').addEventListener('submit',async e=>{e.preventDefault();const error=document.getElementById('error');error.textContent='';
try{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({password:document.getElementById('password').value})});
if(!r.ok){error.textContent='Access denied or temporarily limited.';return;}location.assign('/static/atlas-chat.html');}
catch{error.textContent='Connection unavailable.';}});</script></body></html>"""

class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


def create_app() -> FastAPI:
    password = os.getenv("ATLAS_BETA_PASSWORD", "")
    secret = os.getenv("ATLAS_COOKIE_SECRET", "")
    if len(password) < 16 or len(secret) < 32:
        raise RuntimeError("Set ATLAS_BETA_PASSWORD (>=16 characters) and ATLAS_COOKIE_SECRET (>=32 characters) in host environment")
    static = BASE / "static"
    if not (static / "atlas-chat.html").is_file() or not (static / "atlas-chat.js").is_file() or not (static / "atlas-chat.css").is_file():
        raise RuntimeError("Missing static/atlas-chat.html, atlas-chat.js, or atlas-chat.css. Run prepare_atlas_hosted_beta.py")

    from atlas.api import create_app as create_atlas_app
    original = create_atlas_app()
    app = FastAPI(title="ATLAS Research Beta", docs_url=None, redoc_url=None, openapi_url=None)
    for route in original.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/science/"):
            app.router.routes.append(route)
    required = {"/api/science/decompose", "/api/science/workflow"}
    loaded = {r.path for r in app.routes if isinstance(r, APIRoute)}
    if not required.issubset(loaded):
        raise RuntimeError("Scientific workflow routes missing; verify the v1.9 backend installation")

    # Single-worker best-effort throttling. This is NOT durable / multi-user rate limiting.
    login_attempts: dict[str, deque] = defaultdict(deque)
    request_windows: dict[str, deque] = defaultdict(deque)
    concurrency = asyncio.Semaphore(2)

    def in_window(buckets: dict[str, deque], key: str, *, window: int, limit: int) -> bool:
        now = time.monotonic()
        d = buckets[key]
        while d and d[0] <= now - window:
            d.popleft()
        if len(d) >= limit:
            return False
        d.append(now)
        return True

    def sign_session() -> str:
        payload = f"{int(time.time())}.{secrets.token_hex(16)}"
        digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{digest}"

    def validate_session(token: str | None) -> bool:
        if not token or len(token) > 200:
            return False
        try:
            time_string, nonce, digest = token.split(".")
            age = time.time() - int(time_string)
            if not 0 <= age <= SESSION_SECONDS or len(nonce) != 32 or len(digest) != 64:
                return False
            candidate = hmac.new(secret.encode(), f"{time_string}.{nonce}".encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(digest, candidate)
        except (ValueError, TypeError):
            return False

    def csrf_for(token: str) -> str:
        return hmac.new(secret.encode(), ("csrf:" + token).encode(), hashlib.sha256).hexdigest()

    @app.middleware("http")
    async def protect_api(request: Request, call_next):
        if not request.url.path.startswith("/api/science/"):
            return await call_next(request)
        token = request.cookies.get(SESSION_COOKIE)
        if not validate_session(token):
            return JSONResponse({"detail": "Sign in at /login"}, status_code=401)
        if request.method != "POST":
            return JSONResponse({"detail": "Method not allowed"}, status_code=405)
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            host = request.headers.get("host", "").split(":")[0].lower()
            if parsed.scheme != "https" or parsed.hostname != host:
                # Local tests may use TestClient on http://testserver.
                if not (os.getenv("ATLAS_ALLOW_HTTP_LOCAL_TEST") == "1" and parsed.scheme == "http" and parsed.hostname == host):
                    return JSONResponse({"detail": "Origin rejected"}, status_code=403)
        csrf = request.headers.get("x-atlas-csrf", "")
        if not hmac.compare_digest(csrf, csrf_for(token)):
            return JSONResponse({"detail": "CSRF validation failed"}, status_code=403)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        # Default public beta does not permit paid model calls. The server operator
        # may explicitly enable a provider after implementing durable user quotas.
        import json
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("provider", "demo") != "demo":
                return JSONResponse({"detail": "Paid synthesis is disabled for the hosted beta"}, status_code=403)
        except (ValueError, TypeError):
            return JSONResponse({"detail": "Invalid JSON"}, status_code=400)
        key = hashlib.sha256(token.encode()).hexdigest()
        if not in_window(request_windows, key, window=3600, limit=40):
            return JSONResponse({"detail": "Research quota reached; try again later"}, status_code=429)
        # No unbounded concurrency; this protects host resources rather than guaranteeing budgets.
        if concurrency.locked():
            return JSONResponse({"detail": "Research engine busy; retry"}, status_code=503)
        try:
            async with concurrency:
                return await asyncio.wait_for(call_next(request), timeout=90)
        except asyncio.TimeoutError:
            return JSONResponse({"detail": "Research timed out"}, status_code=504)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "mode": "private_beta"}

    @app.get("/")
    def home(request: Request):
        return RedirectResponse("/static/atlas-chat.html" if validate_session(request.cookies.get(SESSION_COOKIE)) else "/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page():
        return HTMLResponse(LOGIN_HTML, headers={"Cache-Control": "no-store"})

    @app.post("/auth/login")
    async def login(request: Request, credentials: LoginRequest):
        ip = str(request.client.host if request.client else "unknown")
        if not in_window(login_attempts, ip, window=900, limit=8):
            raise HTTPException(429, "Too many login attempts")
        if not hmac.compare_digest(credentials.password.encode(), password.encode()):
            raise HTTPException(401, "Invalid credentials")
        token = sign_session()
        response = JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
        response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=True,
                            samesite="lax", max_age=SESSION_SECONDS, path="/")
        return response

    @app.get("/auth/session")
    def session(request: Request):
        token = request.cookies.get(SESSION_COOKIE)
        if not validate_session(token):
            return JSONResponse({"detail": "Sign in at /login"}, status_code=401,
                                headers={"Cache-Control": "no-store"})
        return JSONResponse({"csrf": csrf_for(token), "mode": "private_beta"},
                            headers={"Cache-Control": "no-store"})

    @app.post("/auth/logout")
    def logout():
        response = JSONResponse({"status": "ok"})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    app.mount("/static", StaticFiles(directory=str(static), check_dir=True), name="static")
    return app


app = create_app()
