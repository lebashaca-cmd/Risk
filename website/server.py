import asyncio
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

import aiohttp
from aiohttp import web

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_FILE = ROOT / "data" / "bot.json"
PAGES = {"/", "/commands", "/terms"}
STATUS_TTL = 10
API_LIMIT = (90, 60)

INVITE_PERMISSIONS = (
    (1 << 4)
    | (1 << 1)
    | (1 << 2)
    | (1 << 10)
    | (1 << 11)
    | (1 << 13)
    | (1 << 14)
    | (1 << 15)
    | (1 << 16)
    | (1 << 17)
)


def load_env_file(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        os.environ.setdefault(key.strip(), value)


load_env_file(ROOT / ".env")


def env(name, default=""):
    return (os.getenv(name) or default).strip()


class Settings:
    def __init__(self):
        self.port = int(env("PORT") or env("SERVER_PORT") or 8080)
        self.name = env("SITE_NAME", "Risk")
        self.status_url = env("BOT_STATUS_URL")
        self.client_id = env("CLIENT_ID")
        self.invite_url = env("INVITE_URL")
        self.support_url = env("SUPPORT_URL")
        self.trust_proxy = env("TRUST_PROXY") in ("1", "true", "yes")
        permissions = env("INVITE_PERMISSIONS")
        self.permissions = int(permissions) if permissions.isdigit() else INVITE_PERMISSIONS

    def invite(self):
        if self.invite_url.startswith("https://"):
            return self.invite_url
        if self.client_id.isdigit():
            return (
                "https://discord.com/oauth2/authorize"
                f"?client_id={self.client_id}&permissions={self.permissions}&scope=bot%20applications.commands"
            )
        return None


def read_bot_data():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"prefixes": ["!"], "commands": [], "tos": {"sections": [], "updated": None}}


class StatusCache:
    def __init__(self):
        self.data = None
        self.at = 0.0
        self.lock = asyncio.Lock()


def number_or_none(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(round(value))


ICON_HOST = "https://cdn.discordapp.com/"


def clean_servers(value):
    found = []
    if not isinstance(value, list):
        return found
    for item in value[:30]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        icon = item.get("icon")
        if not (isinstance(icon, str) and icon.startswith(ICON_HOST) and len(icon) < 300):
            icon = None
        found.append({"name": name.strip()[:60], "icon": icon, "members": number_or_none(item.get("members"))})
    return found


async def probe(settings, session):
    now = time.time()
    result = {"state": "unknown", "latencyMs": None, "guilds": None, "servers": [], "checkedAt": int(now)}
    if not settings.status_url:
        return result
    try:
        async with session.get(settings.status_url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=6)) as resp:
            if resp.status != 200:
                result["state"] = "offline"
                return result
            body = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        result["state"] = "offline"
        return result
    if not isinstance(body, dict):
        result["state"] = "offline"
        return result
    result["state"] = "online" if body.get("online") is True else "offline"
    if result["state"] == "online":
        result["latencyMs"] = number_or_none(body.get("latency_ms"))
        result["guilds"] = number_or_none(body.get("guilds"))
        result["servers"] = clean_servers(body.get("servers"))
    return result


async def get_status(app):
    cache = app["status"]
    if cache.data and time.monotonic() - cache.at < STATUS_TTL:
        return cache.data
    async with cache.lock:
        if cache.data and time.monotonic() - cache.at < STATUS_TTL:
            return cache.data
        cache.data = await probe(app["settings"], app["session"])
        cache.at = time.monotonic()
        return cache.data


def client_ip(request, settings):
    if settings.trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.remote or "unknown"


@web.middleware
async def guard(request, handler):
    if request.path.startswith("/api/"):
        limit, window = API_LIMIT
        hits = request.app["hits"]
        ip = client_ip(request, request.app["settings"])
        now = time.monotonic()
        recent = hits[ip]
        while recent and now - recent[0] > window:
            recent.popleft()
        if len(recent) >= limit:
            return web.json_response({"error": "Too many requests. Try again in a minute."}, status=429, headers={"Retry-After": "30"})
        recent.append(now)
        if len(hits) > 5000:
            for key in [k for k, v in hits.items() if not v or now - v[-1] > window]:
                hits.pop(key, None)

    try:
        response = await handler(request)
    except web.HTTPException as exc:
        if request.path.startswith("/api/"):
            response = web.json_response({"error": exc.reason}, status=exc.status)
        else:
            raise
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; "
        "img-src 'self' data: https://cdn.discordapp.com; connect-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com"
    )
    return response


def json_ok(payload, max_age):
    return web.json_response(payload, headers={"Cache-Control": f"public, max-age={max_age}"})


async def api_config(request):
    settings = request.app["settings"]
    return json_ok({"name": settings.name, "inviteUrl": settings.invite(), "supportUrl": settings.support_url or None}, 60)


async def api_status(request):
    return json_ok(await get_status(request.app), 5)


async def api_commands(request):
    data = read_bot_data()
    return json_ok({"prefixes": data.get("prefixes", ["!"]), "commands": data.get("commands", [])}, 300)


async def api_tos(request):
    return json_ok(read_bot_data().get("tos", {"sections": [], "updated": None}), 300)


async def healthz(request):
    return web.json_response({"ok": True})


def page(status=200):
    async def handler(request):
        return web.FileResponse(WEB_DIR / "index.html", status=status, headers={"Cache-Control": "no-cache"})
    return handler


async def fallback(request):
    path = request.path.rstrip("/") or "/"
    if path.startswith("/api/"):
        return web.json_response({"error": "Not found."}, status=404)
    if path in PAGES:
        return await page()(request)
    if Path(path).suffix:
        return web.Response(status=404, text="Not found.")
    return await page(404)(request)


@web.middleware
async def asset_cache(request, handler):
    response = await handler(request)
    if request.path.startswith("/assets/") and response.status == 200:
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


async def on_startup(app):
    app["session"] = aiohttp.ClientSession()


async def on_cleanup(app):
    await app["session"].close()


def make_app():
    app = web.Application(middlewares=[guard, asset_cache])
    app["settings"] = Settings()
    app["status"] = StatusCache()
    app["hits"] = defaultdict(deque)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/commands", api_commands)
    app.router.add_get("/api/tos", api_tos)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/favicon.png", lambda r: web.FileResponse(WEB_DIR / "favicon.png"))
    app.router.add_static("/assets", WEB_DIR / "assets", follow_symlinks=False)
    app.router.add_get("/{tail:.*}", fallback)
    return app


if __name__ == "__main__":
    app = make_app()
    settings = app["settings"]
    print(f"{settings.name} site listening on http://0.0.0.0:{settings.port}")
    if not settings.status_url:
        print("BOT_STATUS_URL is not set, so the status badge will read 'unavailable'.")
    web.run_app(app, host="0.0.0.0", port=settings.port, print=None)
