import asyncio
import json
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path

import aiohttp
from aiohttp import web

from dashboard import Dashboard

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_FILE = ROOT / "data" / "bot.json"
PAGES = {"/", "/commands", "/terms", "/privacy", "/vip", "/staff"}
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
        # Basic used to be called Monthly, so the old variable names still work.
        self.vip_plans = {
            "basic": (env("VIP_BASIC_URL") or env("VIP_MONTHLY_URL"), (env("VIP_BASIC_PRICE") or env("VIP_MONTHLY_PRICE") or "$4.99")[:20]),
            "lifetime": (env("VIP_LIFETIME_URL"), env("VIP_LIFETIME_PRICE", "$29.99")[:20]),
            "white": (env("VIP_WHITE_URL"), env("VIP_WHITE_PRICE", "$9.99")[:20]),
            "supreme": (env("VIP_SUPREME_URL"), env("VIP_SUPREME_PRICE", "$19.99")[:20]),
        }
        self.trust_proxy = env("TRUST_PROXY") in ("1", "true", "yes")
        host = env("DASHBOARD_HOST").lower()
        self.dashboard_host = host.removeprefix("https://").removeprefix("http://").strip("/")
        docs = env("DOCS_HOST").lower()
        self.docs_host = docs.removeprefix("https://").removeprefix("http://").strip("/")
        permissions = env("INVITE_PERMISSIONS")
        self.permissions = int(permissions) if permissions.isdigit() else INVITE_PERMISSIONS

    def vip(self):
        """Checkout links come from the owner's payment provider. Only https links are ever sent to the page."""
        def link(url):
            return url if url.startswith("https://") else None
        return {name: {"price": price, "url": link(url)} for name, (url, price) in self.vip_plans.items()}

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
        return {"prefixes": ["!"], "commands": [], "tos": {"sections": [], "updated": None}, "privacy": {"sections": [], "updated": None}}


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


def request_host(request, settings):
    host = request.headers.get("X-Forwarded-Host", "") if settings.trust_proxy else ""
    return (host.split(",")[0].strip() or request.host).split(":")[0].lower()


def on_dashboard_host(request):
    settings = request.app["settings"]
    return bool(settings.dashboard_host) and request_host(request, settings) == settings.dashboard_host


DASH_ID = re.compile(r"/\d{15,21}")
DOCS_DIR = WEB_DIR / "docs"
DOCS_FILE = re.compile(r"[a-z0-9-]+(\.(css|js|json))?")


def on_docs_host(request):
    settings = request.app["settings"]
    return bool(settings.docs_host) and request_host(request, settings) == settings.docs_host


def docs_response(rel):
    """Serve a page of the documentation site. rel is the path inside it, like / or /moderation or /docs.css."""
    name = rel.strip("/") or "index"
    if not DOCS_FILE.fullmatch(name):
        return web.Response(status=404, text="Not found.")
    target = DOCS_DIR / (name if "." in name else name + ".html")
    if not target.is_file():
        return web.Response(status=404, text="That documentation page doesn't exist. Go back to the docs home and search for it.")
    return web.FileResponse(target, headers={"Cache-Control": "no-cache"})


async def api_config(request):
    settings = request.app["settings"]
    if on_dashboard_host(request):
        dashboard_url = "/"
    elif settings.dashboard_host:
        dashboard_url = f"https://{settings.dashboard_host}/"
    else:
        dashboard_url = "/dashboard"
    staff_url = f"https://{settings.dashboard_host}/staff" if settings.dashboard_host and not on_dashboard_host(request) else "/staff"
    docs_url = f"https://{settings.docs_host}/" if settings.docs_host else "/docs/"
    vip = settings.vip()
    for plan, saved in (await request.app["dashboard"].vip_prices(request)).items():
        if plan in vip:
            vip[plan] = {"price": saved["price"] or vip[plan]["price"], "url": saved["url"] or vip[plan]["url"]}
    return json_ok({"name": settings.name, "inviteUrl": settings.invite(), "supportUrl": settings.support_url or None, "dashboardUrl": dashboard_url, "staffUrl": staff_url, "docsUrl": docs_url, "dashboardHost": on_dashboard_host(request), "vip": vip}, 15)


async def api_status(request):
    return json_ok(await get_status(request.app), 5)


async def api_commands(request):
    data = read_bot_data()
    return json_ok({"prefixes": data.get("prefixes", ["!"]), "commands": data.get("commands", [])}, 300)


async def api_tos(request):
    return json_ok(read_bot_data().get("tos", {"sections": [], "updated": None}), 300)


async def api_privacy(request):
    return json_ok(read_bot_data().get("privacy", {"sections": [], "updated": None}), 300)


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
    settings = request.app["settings"]
    if on_docs_host(request):
        return docs_response(path)
    if request.path == "/docs":
        raise web.HTTPFound("/docs/")
    if request.path.startswith("/docs/"):
        return docs_response(request.path[len("/docs"):])
    is_dashboard_path = path == "/dashboard" or path.startswith("/dashboard/")
    if settings.dashboard_host and is_dashboard_path and not on_dashboard_host(request):
        target = path[len("/dashboard"):] or "/"
        raise web.HTTPFound(f"https://{settings.dashboard_host}{target}")
    if settings.dashboard_host and path == "/staff" and not on_dashboard_host(request):
        # Sign-in lives on the dashboard address, so the staff panel does too.
        raise web.HTTPFound(f"https://{settings.dashboard_host}/staff")
    if path in PAGES or is_dashboard_path or (on_dashboard_host(request) and DASH_ID.fullmatch(path)):
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
    app = web.Application(middlewares=[guard, asset_cache], client_max_size=8 * 1024 * 1024)
    app["settings"] = Settings()
    app["status"] = StatusCache()
    app["hits"] = defaultdict(deque)
    app["dashboard"] = Dashboard(app["settings"], env)
    app["dashboard"].add_routes(app)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/commands", api_commands)
    app.router.add_get("/api/tos", api_tos)
    app.router.add_get("/api/privacy", api_privacy)
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
    if not app["dashboard"].enabled:
        print("Dashboard is off: set CLIENT_ID, DASHBOARD_KEY (16+ characters) and BOT_STATUS_URL or BOT_API_URL to turn it on.")
    web.run_app(app, host="0.0.0.0", port=settings.port, print=None)
