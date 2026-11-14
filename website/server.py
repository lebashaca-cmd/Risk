import asyncio
import html
import json
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web

import legal
from dashboard import Dashboard

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_FILE = ROOT / "data" / "bot.json"
PAGES = {"/", "/commands", "/terms", "/privacy", "/accessibility", "/data-deletion", "/vip", "/staff", "/status"}
SITEMAP_PAGES = ["/", "/commands", "/vip", "/status", "/terms", "/privacy", "/accessibility", "/data-deletion"]
META = {
    "/": ("Risk: tickets, logs and moderation for Discord", "Risk is a Discord bot for ticket channels, server logs, welcome messages, AI answers and TikTok, YouTube, GitHub and Spotify lookups."),
    "/commands": ("Commands · Risk", "Every Risk command with what it does and how to use it, grouped by what it's for."),
    "/terms": ("Terms of Service · Risk", "The rules for using the Risk Discord bot and its website."),
    "/privacy": ("Privacy Policy · Risk", "What Risk saves, why, how cookies and tracking work on this site, and your choices."),
    "/accessibility": ("Accessibility statement · Risk", "How the Risk website supports keyboard, screen reader and low-vision use, and how to report a problem."),
    "/data-deletion": ("Delete my data · Risk", "Ask Risk to delete what it has saved about you, or to send you a copy."),
    "/vip": ("VIP · Risk", "Risk VIP plans, what each one includes and how to get one."),
    "/staff": ("Staff · Risk", "Risk staff panel."),
    "/status": ("Status · Risk", "Live status of the Risk Discord bot."),
}
DEFAULT_IMAGE = "/assets/og.png"
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
        self.contact_email = env("CONTACT_EMAIL")
        self.security_contact = env("SECURITY_CONTACT")
        self.deletion_webhook = env("DELETION_WEBHOOK_URL")
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
            response = exc
    return secure(response)


SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
    "Content-Security-Policy": (
        "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'self'; form-action 'self'; "
        "img-src 'self' data: https://cdn.discordapp.com; connect-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com"
    ),
}


def secure(response):
    """Every response, including errors, redirects and static files, carries the same protective headers."""
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
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


async def api_status_page(request):
    """Live state from the probe, plus what the bot says about buttons, notices, incidents, usage and uptime."""
    status = await get_status(request.app)
    page = await request.app["dashboard"].status_page(request)
    return json_ok({"status": status, "page": page}, 10)


async def api_commands(request):
    data = read_bot_data()
    return json_ok({"prefixes": data.get("prefixes", ["!"]), "commands": data.get("commands", [])}, 300)


async def api_tos(request):
    return json_ok(read_bot_data().get("tos", {"sections": [], "updated": None}), 300)


async def api_privacy(request):
    return json_ok(read_bot_data().get("privacy", {"sections": [], "updated": None}), 300)


async def healthz(request):
    return web.json_response({"ok": True})


def site_origin(request):
    settings = request.app["settings"]
    host = request.headers.get("X-Forwarded-Host", "").split(",")[0].strip() if settings.trust_proxy else ""
    scheme = "https" if settings.trust_proxy or request.secure else "http"
    return f"{scheme}://{host or request.host}"


def prerendered(request, path):
    settings = request.app["settings"]
    data = read_bot_data()
    if path == "/privacy":
        return legal.document("Privacy Policy", data.get("privacy", {}))
    if path == "/terms":
        return legal.document("Terms of Service", data.get("tos", {}))
    if path == "/accessibility":
        return legal.accessibility(settings)
    if path == "/data-deletion":
        return legal.deletion_form(settings)
    return None


def render_shell(request, status=200, main=None, path=None):
    """The page shell with this page's own title, description, canonical address and share image filled in."""
    path = path or (request.path.rstrip("/") or "/")
    origin = site_origin(request)
    title, desc = META.get(path, ("Dashboard · Risk", "Manage Risk in your Discord server.") if path.startswith("/dashboard") or DASH_ID.fullmatch(path) else META["/"])
    if on_dashboard_host(request) and (path == "/" or DASH_ID.fullmatch(path)):
        title, desc = "Dashboard · Risk", "Manage Risk in your Discord server."
    if status == 404:
        title = "Page not found · Risk"
    body = prerendered(request, path) if main is None else main
    noscript = (
        '<noscript><div class="container page"><h1>Risk</h1><p class="lede">This site needs JavaScript to show the command list and live status. '
        "Type !commands in your Discord server to see everything Risk can do.</p></div></noscript>"
    )
    text = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    values = {
        "TITLE": html.escape(title, quote=True),
        "DESC": html.escape(desc, quote=True),
        "URL": html.escape(origin + path, quote=True),
        "IMAGE": html.escape(origin + DEFAULT_IMAGE, quote=True),
        "YEAR": str(time.gmtime().tm_year),
        "MAIN": body if body else noscript,
        "PRERENDER_ATTR": " data-prerendered" if body else "",
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return web.Response(text=text, status=status, content_type="text/html", charset="utf-8", headers={"Cache-Control": "no-cache"})


def page(status=200):
    async def handler(request):
        return render_shell(request, status)
    return handler


def text_response(body, content_type="text/plain", max_age=3600):
    return web.Response(text=body, content_type=content_type, charset="utf-8", headers={"Cache-Control": f"public, max-age={max_age}"})


async def robots(request):
    origin = site_origin(request)
    if on_dashboard_host(request):
        return text_response("User-agent: *\nDisallow: /\n")
    if on_docs_host(request):
        return text_response(f"User-agent: *\nAllow: /\n\nSitemap: {origin}/sitemap.xml\n")
    return text_response(
        "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /dashboard\nDisallow: /staff\n\n"
        f"Sitemap: {origin}/sitemap.xml\n"
    )


def docs_slugs():
    return sorted(f.stem for f in DOCS_DIR.glob("*.html"))


async def sitemap(request):
    origin = site_origin(request)
    if on_dashboard_host(request):
        raise web.HTTPNotFound()
    if on_docs_host(request):
        urls = [origin + ("/" if slug == "index" else f"/{slug}") for slug in docs_slugs()]
    else:
        urls = [origin + p for p in SITEMAP_PAGES] + [origin + ("/docs/" if slug == "index" else f"/docs/{slug}") for slug in docs_slugs()]
    today = time.strftime("%Y-%m-%d", time.gmtime())
    items = "".join(f"<url><loc>{html.escape(u)}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>\n'
    return text_response(xml, "application/xml")


async def security_txt(request):
    settings = request.app["settings"]
    origin = site_origin(request)
    contacts = []
    for item in re.split(r"[,\s]+", settings.security_contact):
        if item.startswith("https://") or item.startswith("mailto:"):
            contacts.append(item)
        elif "@" in item:
            contacts.append("mailto:" + item)
    if not contacts and settings.contact_email:
        contacts.append("mailto:" + settings.contact_email)
    if not contacts and settings.support_url.startswith("https://"):
        contacts.append(settings.support_url)
    if not contacts:
        contacts.append(origin + "/accessibility#contact")
    expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 365 * 86400 - 3600))
    lines = [f"Contact: {c}" for c in contacts] + [
        f"Expires: {expires}",
        "Preferred-Languages: en",
        f"Canonical: {origin}/.well-known/security.txt",
        f"Policy: {origin}/privacy",
    ]
    return text_response("\n".join(lines) + "\n", max_age=86400)


async def notify_deletion(request, entry):
    settings = request.app["settings"]
    url = settings.deletion_webhook
    if not re.fullmatch(r"https://(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+", url or ""):
        return False
    kinds = {"delete": "delete my data", "export": "send me a copy", "both": "copy, then delete"}
    lines = [
        f"**Data request {entry['reference']}**: {kinds[entry['kind']]}",
        f"User ID: `{entry['user_id']}`",
    ]
    if entry["server_id"]:
        lines.append(f"Server ID: `{entry['server_id']}`")
    if entry["reach"]:
        lines.append("Reach them at: " + entry["reach"].replace("`", "'"))
    if entry["details"]:
        lines.append("Note: " + entry["details"].replace("`", "'"))
    try:
        async with request.app["session"].post(url, json={"content": "\n".join(lines)[:1900], "allowed_mentions": {"parse": []}}, timeout=aiohttp.ClientTimeout(total=8)) as reply:
            return reply.status < 300
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def data_deletion_post(request):
    settings = request.app["settings"]
    origin_header = request.headers.get("Origin")
    if origin_header and urlsplit(origin_header).netloc.lower() != urlsplit(site_origin(request)).netloc.lower():
        return web.Response(status=403, text="That request didn't come from this site.")
    ip = client_ip(request, settings)
    if request.app["deletions"].limited(ip):
        return render_shell(request, 429, main=legal.deletion_form(settings, "You've sent several requests in the last hour. Wait a while and try again, or use the support server."), path="/data-deletion")
    try:
        form = await request.post()
    except (ValueError, web.HTTPException):
        form = {}
    entry, error = legal.parse_request(form)
    if error == "silent":
        return render_shell(request, 200, main=legal.confirmation("DEL-" + "0" * 8, settings), path="/data-deletion")
    if error:
        values = {k: str(form.get(k) or "")[:500] for k in ("kind", "user_id", "server_id", "reach", "details")}
        return render_shell(request, 400, main=legal.deletion_form(settings, error, values), path="/data-deletion")
    saved = request.app["deletions"].add(entry)
    sent = await notify_deletion(request, entry)
    print(f"[data-deletion] {entry['reference']} {entry['kind']} user={entry['user_id']} saved={saved} webhook={sent}")
    if not saved and not sent:
        return render_shell(request, 503, main=legal.deletion_form(settings, "We couldn't record that request. Please try again later or use the support server."), path="/data-deletion")
    return render_shell(request, 200, main=legal.confirmation(entry["reference"], settings), path="/data-deletion")


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
    app["deletions"] = legal.DeletionStore(ROOT / "data" / "deletion-requests.json")
    app["dashboard"] = Dashboard(app["settings"], env)
    app["dashboard"].add_routes(app)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/status-page", api_status_page)
    app.router.add_get("/api/commands", api_commands)
    app.router.add_get("/api/tos", api_tos)
    app.router.add_get("/api/privacy", api_privacy)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/robots.txt", robots)
    app.router.add_get("/sitemap.xml", sitemap)
    app.router.add_get("/.well-known/security.txt", security_txt)
    app.router.add_get("/security.txt", lambda r: web.HTTPFound("/.well-known/security.txt"))
    app.router.add_post("/data-deletion", data_deletion_post)
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
