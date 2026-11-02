"""Discord sign-in and the proxy that lets server managers change Risk's settings.

Flow: /api/auth/login sends the visitor to Discord, /api/auth/callback trades the code for a token,
reads who they are and which servers they manage, then throws the token away. After that the
browser only holds a random session cookie. Settings calls are forwarded to the bot with a shared
key, and the bot checks the person's permissions in that server again.
"""
import asyncio
import hmac
import secrets
import time
from urllib.parse import quote, urlencode, urlsplit

import aiohttp
from aiohttp import web

SESSION_TTL = 6 * 3600
OAUTH_TTL = 600
MAX_SESSIONS = 2000
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8
SECTIONS = {"general", "welcome", "logs", "levels", "automod", "community"}
SESSION_COOKIE = "risk_session"
STATE_COOKIE = "risk_oauth"
PRESENCE_TTL = 20


class Session:
    __slots__ = ("user", "guilds", "expires")

    def __init__(self, user, guilds):
        self.user = user
        self.guilds = guilds
        self.expires = time.time() + SESSION_TTL


class Dashboard:
    def __init__(self, settings, env):
        self.settings = settings
        self.sessions = {}
        self.presence = {}
        self.client_secret = env("DISCORD_CLIENT_SECRET")
        self.key = env("DASHBOARD_KEY")
        self.site_url = env("SITE_URL").rstrip("/")
        self.discord_api = env("DISCORD_API", "https://discord.com/api/v10").rstrip("/")
        explicit = env("BOT_API_URL").rstrip("/")
        if explicit:
            self.bot_api = explicit
        else:
            parts = urlsplit(settings.status_url)
            self.bot_api = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""

    @property
    def enabled(self):
        return bool(self.settings.client_id.isdigit() and self.client_secret and len(self.key) >= 16 and self.bot_api)

    # Helpers
    def origin(self, request):
        if self.settings.dashboard_host:
            if self.settings.trust_proxy or request.scheme == "https":
                return f"https://{self.settings.dashboard_host}"
            return f"http://{request.host}"
        if self.site_url:
            return self.site_url
        proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip() if self.settings.trust_proxy else ""
        host = request.headers.get("X-Forwarded-Host", "").split(",")[0].strip() if self.settings.trust_proxy else ""
        return f"{proto or request.scheme}://{host or request.host}"

    def on_dashboard_host(self, request):
        host = request.headers.get("X-Forwarded-Host", "") if self.settings.trust_proxy else ""
        return (host.split(",")[0].strip() or request.host).split(":")[0].lower() == self.settings.dashboard_host

    def secure(self, request):
        return self.origin(request).startswith("https://")

    def purge(self):
        now = time.time()
        for sid in [s for s, v in self.sessions.items() if v.expires < now]:
            self.sessions.pop(sid, None)
        while len(self.sessions) >= MAX_SESSIONS:
            self.sessions.pop(next(iter(self.sessions)))

    def current(self, request):
        sid = request.cookies.get(SESSION_COOKIE, "")
        session = self.sessions.get(sid)
        if session is None or session.expires < time.time():
            self.sessions.pop(sid, None)
            return None, None
        return sid, session

    def require(self, request):
        if not self.enabled:
            raise web.HTTPServiceUnavailable(reason="The dashboard isn't set up on this site yet.")
        sid, session = self.current(request)
        if session is None:
            raise web.HTTPUnauthorized(reason="Sign in with Discord to continue.")
        return sid, session

    def check_write(self, request):
        """Blocks cross-site form posts: a custom header plus a matching Origin."""
        if request.headers.get("X-Requested-With") != "risk":
            raise web.HTTPForbidden(reason="Missing request header.")
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != self.origin(request):
            raise web.HTTPForbidden(reason="Request came from another site.")

    @staticmethod
    def reply(payload, status=200):
        return web.json_response(payload, status=status, headers={"Cache-Control": "no-store"})

    def set_cookie(self, request, response, name, value, max_age):
        response.set_cookie(name, value, max_age=max_age, httponly=True, secure=self.secure(request), samesite="Lax", path="/")

    # Sign in
    async def login(self, request):
        if not self.enabled:
            raise web.HTTPServiceUnavailable(reason="The dashboard isn't set up on this site yet.")
        host = self.settings.dashboard_host
        if host and not self.on_dashboard_host(request):
            raise web.HTTPFound(f"https://{host}/api/auth/login")
        state = secrets.token_urlsafe(24)
        query = urlencode({
            "client_id": self.settings.client_id,
            "redirect_uri": f"{self.origin(request)}/api/auth/callback",
            "response_type": "code",
            "scope": "identify guilds",
            "state": state,
        })
        response = web.HTTPFound(f"https://discord.com/oauth2/authorize?{query}")
        self.set_cookie(request, response, STATE_COOKIE, state, OAUTH_TTL)
        return response

    async def callback(self, request):
        if not self.enabled:
            raise web.HTTPServiceUnavailable(reason="The dashboard isn't set up on this site yet.")
        expected = request.cookies.get(STATE_COOKIE, "")
        given = request.query.get("state", "")
        code = request.query.get("code", "")
        if request.query.get("error") or not code or not expected or not hmac.compare_digest(expected, given):
            return self.back(request, "denied")
        session = request.app["session"]
        token = None
        try:
            async with session.post(
                f"{self.discord_api}/oauth2/token",
                data={"client_id": self.settings.client_id, "client_secret": self.client_secret, "grant_type": "authorization_code", "code": code, "redirect_uri": f"{self.origin(request)}/api/auth/callback"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return self.back(request, "failed")
                token = (await resp.json()).get("access_token")
            if not isinstance(token, str):
                return self.back(request, "failed")
            headers = {"Authorization": f"Bearer {token}"}
            async with session.get(f"{self.discord_api}/users/@me", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                user = await resp.json() if resp.status == 200 else None
            async with session.get(f"{self.discord_api}/users/@me/guilds", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                guilds = await resp.json() if resp.status == 200 else None
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return self.back(request, "failed")
        finally:
            if token:
                asyncio.create_task(self.revoke(session, token))
        if not isinstance(user, dict) or not isinstance(guilds, list) or not str(user.get("id", "")).isdigit():
            return self.back(request, "failed")

        manageable = {}
        for guild in guilds:
            try:
                perms = int(guild.get("permissions", 0))
            except (TypeError, ValueError):
                continue
            if guild.get("owner") or perms & (ADMINISTRATOR | MANAGE_GUILD):
                gid = str(guild.get("id", ""))
                if gid.isdigit():
                    icon = guild.get("icon")
                    manageable[gid] = {"id": gid, "name": str(guild.get("name", ""))[:100], "icon": f"https://cdn.discordapp.com/icons/{gid}/{icon}.png?size=128" if isinstance(icon, str) and icon.replace("_", "").isalnum() else None}
        avatar = user.get("avatar")
        profile = {
            "id": user["id"],
            "name": str(user.get("global_name") or user.get("username") or "Member")[:60],
            "avatar": f"https://cdn.discordapp.com/avatars/{user['id']}/{avatar}.png?size=64" if isinstance(avatar, str) and avatar.replace("_", "").isalnum() else None,
        }
        self.purge()
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = Session(profile, manageable)
        response = web.HTTPFound("/")
        self.set_cookie(request, response, SESSION_COOKIE, sid, SESSION_TTL)
        response.del_cookie(STATE_COOKIE, path="/")
        return response

    def back(self, request, reason):
        response = web.HTTPFound(f"/?login={reason}")
        response.del_cookie(STATE_COOKIE, path="/")
        return response

    async def revoke(self, session, token):
        try:
            await session.post(
                f"{self.discord_api}/oauth2/token/revoke",
                data={"client_id": self.settings.client_id, "client_secret": self.client_secret, "token": token},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass

    async def logout(self, request):
        self.check_write(request)
        sid, _ = self.current(request)
        self.sessions.pop(sid, None)
        response = self.reply({"ok": True})
        response.del_cookie(SESSION_COOKIE, path="/")
        return response

    # Bot calls
    async def ask_bot(self, request, method, path, user_id=None, body=None):
        headers = {"X-Dashboard-Key": self.key}
        if user_id:
            headers["X-Dashboard-User"] = user_id
        try:
            async with request.app["session"].request(method, f"{self.bot_api}/dash/{path}", headers=headers, json=body, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                try:
                    payload = await resp.json(content_type=None)
                except ValueError:
                    payload = None
                if not isinstance(payload, dict):
                    return 502, {"error": "The bot sent an unexpected answer."}
                return resp.status, payload
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return 502, {"error": "The bot is offline or restarting. Try again in a minute."}

    async def present_ids(self, request, ids):
        """Which of these server ids the bot is in, cached briefly."""
        key = tuple(sorted(ids))
        cached = self.presence.get(key)
        if cached and time.monotonic() - cached[0] < PRESENCE_TTL:
            return cached[1]
        status, payload = await self.ask_bot(request, "POST", "present", body={"ids": list(ids)})
        if status != 200:
            return None
        found = {g["id"] for g in payload.get("guilds", []) if isinstance(g, dict) and isinstance(g.get("id"), str)}
        if len(self.presence) > 200:
            self.presence.clear()
        self.presence[key] = (time.monotonic(), found)
        return found

    def invite_for(self, guild_id):
        base = self.settings.invite()
        if not base:
            return None
        return f"{base}&guild_id={guild_id}&disable_guild_select=true" if "discord.com/oauth2/authorize" in base else base

    async def me(self, request):
        if not self.enabled:
            return self.reply({"enabled": False, "user": None, "guilds": []})
        _, session = self.current(request)
        if session is None:
            return self.reply({"enabled": True, "user": None, "guilds": []})
        ids = list(session.guilds)[:200]
        present = await self.present_ids(request, ids) if ids else set()
        guilds = []
        for gid in ids:
            info = session.guilds[gid]
            guilds.append({**info, "botPresent": None if present is None else gid in present, "invite": None if present is not None and gid in present else self.invite_for(gid)})
        guilds.sort(key=lambda g: (g["botPresent"] is not True, g["name"].lower()))
        return self.reply({"enabled": True, "user": session.user, "guilds": guilds, "botReachable": present is not None})

    async def guild_settings(self, request):
        _, session = self.require(request)
        gid = request.match_info["gid"]
        if gid not in session.guilds:
            raise web.HTTPForbidden(reason="You don't manage that server.")
        status, payload = await self.ask_bot(request, "GET", f"guild/{gid}", session.user["id"])
        return self.reply(payload, status)

    async def save_section(self, request):
        self.check_write(request)
        _, session = self.require(request)
        gid, section = request.match_info["gid"], request.match_info["section"]
        if gid not in session.guilds:
            raise web.HTTPForbidden(reason="You don't manage that server.")
        if section not in SECTIONS:
            raise web.HTTPNotFound(reason="Unknown settings section.")
        if request.content_length is not None and request.content_length > 20_000:
            raise web.HTTPRequestEntityTooLarge(max_size=20_000, actual_size=request.content_length)
        try:
            body = await request.json()
        except ValueError:
            raise web.HTTPBadRequest(reason="The request wasn't valid JSON.")
        if not isinstance(body, dict):
            raise web.HTTPBadRequest(reason="The request must be a JSON object.")
        status, payload = await self.ask_bot(request, "PUT", f"guild/{gid}/{quote(section)}", session.user["id"], body)
        return self.reply(payload, status)

    def add_routes(self, app):
        app.router.add_get("/api/auth/login", self.login)
        app.router.add_get("/api/auth/callback", self.callback)
        app.router.add_get("/api/auth/me", self.me)
        app.router.add_post("/api/auth/logout", self.logout)
        app.router.add_get("/api/dash/guild/{gid:\\d+}", self.guild_settings)
        app.router.add_put("/api/dash/guild/{gid:\\d+}/{section}", self.save_section)
