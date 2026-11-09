"""The owner's remote control, used by the Windows control panel (the .exe) and by the website's staff panel.

Two things live here:

1. A signed HTTP API at /owner/... on the bot's web server. It only answers requests signed with
   OWNER_PANEL_KEY, a secret that exists only on the bot's host and on the owner's computer. The key itself is
   never sent: each request carries an HMAC of the method, path, time, a one-time number and the body, so
   someone watching the traffic can't reuse or forge a request. Requests older than 30 seconds are refused and
   a number can only be used once. A wrong signature is answered after a short delay. (There is no lockout on
   purpose: a lockout would let a stranger shut the owner out by sending bad requests.)

2. Global switches that apply to every server: commands turned off, blocked users and maintenance mode.
   The owner is never affected by them, so they can always be undone.

Without OWNER_PANEL_KEY (at least 32 characters) the API answers 503 and nothing here can be reached.
"""
import asyncio
import base64
import hashlib
import hmac
import io
import json
import os
import re
import sys
import time
import threading
import traceback
import zipfile
from pathlib import Path
from collections import deque

import discord
from aiohttp import web
from discord.ext import commands, tasks

from cogs.staff import env_ids
from utils.helpers import ModError, Silent, ping
from utils import store as store_module
from utils.store import JsonStore

WINDOW = 30
MIN_KEY = 32
LOG_LINES = 300
ACTIVITY = {"playing": discord.ActivityType.playing, "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening, "competing": discord.ActivityType.competing}
KINDS = (*ACTIVITY, "streaming", "custom")
STATUS = {"online": discord.Status.online, "idle": discord.Status.idle, "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}
MAX_ROTATION = 10
MIN_INTERVAL = 30
PRESENCE_VARS = re.compile(r"\{(servers|members|commands|ping|prefix|uptime|vip)\}")
EMPTY_PRESENCE = {"kind": "", "text": "", "status": "online", "url": "", "rotate": False, "interval": 120, "items": []}


class ApiErr(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Tee:
    """Passes console output through and keeps the last lines so the control panel can show them."""

    def __init__(self, target, lines):
        self.target = target
        self.lines = lines
        self.buffer = ""

    def write(self, text):
        self.target.write(text)
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.lines.append(line[:300])
        return len(text)

    def flush(self):
        self.target.flush()

    def __getattr__(self, name):
        return getattr(self.target, name)


def memory_mb():
    """The bot's memory use, read from the operating system when it offers it."""
    try:
        with open("/proc/self/status") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024)
    except OSError:
        pass
    return None


def sign(key, method, path, stamp, nonce, body):
    message = "\n".join((method.upper(), path, stamp, nonce, hashlib.sha256(body).hexdigest()))
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def snowflake(value, what):
    text = str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    if not text.isdigit() or not 15 <= len(text) <= 21:
        raise ApiErr(400, f"{what} isn't valid.")
    return int(text)


class OwnerControl(commands.Cog, name="OwnerControl"):
    """Remote control for the bot's owner."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("owner_control")
        for key, empty in (("disabled", []), ("blacklist", {}), ("maintenance", {"on": False, "message": ""}), ("presence", dict(EMPTY_PRESENCE))):
            self.store.data.setdefault(key, empty)
        for key, value in EMPTY_PRESENCE.items():
            self.store.data["presence"].setdefault(key, value)
        self.step = 0
        self.last_rotation = time.time()
        self.started = time.time()
        self.nonces = {}
        self.lines = deque(maxlen=LOG_LINES)
        self.tee = []

    # ------------------------------------------------------------------ loading
    async def cog_load(self):
        self.bot.add_check(self.global_check)
        if not isinstance(sys.stdout, Tee):
            for name in ("stdout", "stderr"):
                tee = Tee(getattr(sys, name), self.lines)
                setattr(sys, name, tee)
                self.tee.append((name, tee))
        await self.apply_presence()
        self.rotator.start()

    async def cog_unload(self):
        self.rotator.cancel()
        self.bot.remove_check(self.global_check)
        for name, tee in self.tee:
            if getattr(sys, name) is tee:
                setattr(sys, name, tee.target)

    # ------------------------------------------------------------------ the global switches
    async def is_owner_id(self, user_id):
        if user_id in env_ids("OWNER_IDS"):
            return True
        try:
            return await self.bot.is_owner(discord.Object(id=user_id))
        except Exception:
            return False

    async def global_check(self, ctx):
        if await self.is_owner_id(ctx.author.id):
            return True
        data = self.store.data
        if str(ctx.author.id) in data["blacklist"]:
            raise Silent()
        if data["maintenance"]["on"]:
            raise ModError(data["maintenance"]["message"] or "Risk is down for maintenance. Please try again soon.")
        root = ctx.command.root_parent or ctx.command if ctx.command else None
        if root is not None and root.name in data["disabled"]:
            raise ModError(f"`{root.name}` is turned off right now.")
        return True

    def fill(self, text):
        """Swaps {servers}, {members}, {commands}, {ping}, {prefix}, {uptime} and {vip} for live numbers."""
        guilds = list(self.bot.guilds)
        vip = self.bot.get_cog("VIP")
        values = {
            "servers": len(guilds), "members": sum(g.member_count or 0 for g in guilds), "commands": len(self.bot.commands),
            "ping": ping(self.bot) if ping(self.bot) is not None else "?", "prefix": "!", "uptime": f"{int((time.time() - self.started) // 3600)}h",
            "vip": sum(1 for g in guilds if vip is not None and getattr(vip, "tier_key", lambda _: None)(g.id)),
        }
        return PRESENCE_VARS.sub(lambda m: str(values[m.group(1)]), text)[:128]

    def make_activity(self, kind, text, url):
        text = self.fill(text)
        if not kind or not text:
            return None
        if kind == "custom":
            return discord.CustomActivity(name=text)
        if kind == "streaming":
            return discord.Streaming(name=text, url=url)
        return discord.Activity(type=ACTIVITY[kind], name=text)

    async def apply_presence(self):
        p = self.store.data["presence"]
        try:
            item = {"kind": p["kind"], "text": p["text"]}
            if p["rotate"] and p["items"]:
                item = p["items"][self.step % len(p["items"])]
            await self.bot.change_presence(activity=self.make_activity(item["kind"], item["text"], p["url"]), status=STATUS.get(p["status"], discord.Status.online))
        except Exception:
            traceback.print_exc()

    @tasks.loop(seconds=MIN_INTERVAL)
    async def rotator(self):
        p = self.store.data["presence"]
        now = time.time()
        # Rotating swaps the message every `interval` seconds. Plain statuses with variables are refreshed every few minutes.
        if p["rotate"] and p["items"] and now - self.last_rotation >= p["interval"]:
            self.step += 1
            self.last_rotation = now
            await self.apply_presence()
        elif PRESENCE_VARS.search(p["text"]) and now - self.last_rotation >= 300:
            self.last_rotation = now
            await self.apply_presence()

    @rotator.before_loop
    async def before_rotator(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ what the panels read
    async def owner_uid(self):
        ids = sorted(env_ids("OWNER_IDS"))
        if ids:
            return ids[0]
        info = await self.bot.application_info()
        team = getattr(info, "team", None)
        return team.owner_id if team else info.owner.id

    def staff(self):
        staff = self.bot.get_cog("Staff")
        if staff is None:
            raise ApiErr(503, "The staff cog isn't loaded. Upload cogs/staff.py and restart the bot.")
        return staff

    def note(self, actor, action, detail=""):
        staff = self.bot.get_cog("Staff")
        if staff is not None:
            staff.note(actor, action, detail)

    def status(self):
        guilds = list(self.bot.guilds)
        p = self.store.data["presence"]
        return {
            "name": self.bot.user.name if self.bot.user else None, "id": str(self.bot.user.id) if self.bot.user else None,
            "uptime": int(time.time() - self.started), "latencyMs": ping(self.bot),
            "servers": len(guilds), "members": sum(g.member_count or 0 for g in guilds), "commands": len(self.bot.commands),
            "cogs": sorted(self.bot.cogs), "failed": {k: str(v)[:200] for k, v in getattr(self.bot, "load_errors", {}).items()},
            "python": sys.version.split()[0], "discord": discord.__version__,
            "maintenance": dict(self.store.data["maintenance"]), "disabled": len(self.store.data["disabled"]),
            "blocked": len(self.store.data["blacklist"]), "presence": dict(p),
            "memoryMb": memory_mb(), "threads": threading.active_count(), "usage": self.page_usage(),
            "voice": len(self.bot.voice_clients),
        }

    def page_usage(self):
        page = self.bot.get_cog("StatusPage")
        return page.usage() if page else None

    def command_list(self):
        off = set(self.store.data["disabled"])
        rows = [{"name": c.name, "category": c.cog_name or "Other", "description": (c.help or "").split("\n")[0][:140], "off": c.name in off} for c in self.bot.commands]
        return sorted(rows, key=lambda r: (r["category"], r["name"]))

    def blocked_list(self):
        return [{"id": uid, "reason": e.get("reason", ""), "at": e.get("at")} for uid, e in self.store.data["blacklist"].items()]

    def guild_detail(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise ApiErr(404, "Risk isn't in that server.")
        vip = self.bot.get_cog("VIP")
        info = vip.info(guild.id) if vip else {"vip": False, "until": None, "source": None}
        me = guild.me
        return {
            "id": str(guild.id), "name": guild.name, "members": guild.member_count or 0, "owner": str(guild.owner_id),
            "created": int(guild.created_at.timestamp()), "boosts": guild.premium_subscription_count or 0,
            "vip": info["vip"], "tier": vip.tier_name(guild.id) if vip and info["vip"] else None, "until": info["until"],
            "channels": [{"id": str(c.id), "name": c.name} for c in guild.text_channels if me and c.permissions_for(me).send_messages][:150],
        }

    # ------------------------------------------------------------------ the actions
    async def set_command(self, actor, body):
        name = str(body.get("name", "")).strip().lower()
        command = self.bot.get_command(name)
        if command is None or command.parent is not None:
            raise ApiErr(404, "That isn't a command.")
        off = body.get("off") is True
        disabled = self.store.data["disabled"]
        if off and command.name not in disabled:
            disabled.append(command.name)
        elif not off and command.name in disabled:
            disabled.remove(command.name)
        self.store.save()
        self.note(actor, "command off" if off else "command on", command.name)
        return {"name": command.name, "off": off, "disabled": len(disabled)}

    async def set_blocked(self, actor, body, add):
        uid = snowflake(body.get("user_id"), "User id")
        if await self.is_owner_id(uid):
            raise ApiErr(400, "You can't block an owner.")
        if add:
            self.store.data["blacklist"][str(uid)] = {"reason": str(body.get("reason", ""))[:200], "at": int(time.time())}
        elif self.store.data["blacklist"].pop(str(uid), None) is None:
            raise ApiErr(404, "That person isn't blocked.")
        self.store.save()
        self.note(actor, "user block" if add else "user unblock", str(uid))
        return {"id": str(uid), "blocked": len(self.store.data["blacklist"])}

    async def set_maintenance(self, actor, body):
        self.store.data["maintenance"] = {"on": body.get("on") is True, "message": str(body.get("message", ""))[:300]}
        self.store.save()
        self.note(actor, "maintenance", "on" if body.get("on") is True else "off")
        return dict(self.store.data["maintenance"])

    async def set_presence(self, actor, body):
        kind, status = body.get("kind", ""), body.get("status", "online")
        text = str(body.get("text", "")).strip()[:128]
        url = str(body.get("url", "") or "").strip()
        if kind not in ("", *KINDS) or status not in STATUS:
            raise ApiErr(400, "Kind must be playing, watching, listening, competing, streaming, custom or empty. Status must be online, idle, dnd or invisible.")
        if kind == "streaming" and not re.fullmatch(r"https://(www\.)?(twitch\.tv|youtube\.com|youtu\.be)/\S+", url):
            raise ApiErr(400, "Streaming needs a Twitch or YouTube link starting with https://.")
        rotate = body.get("rotate") is True
        items = []
        for item in body.get("items", []) or []:
            if not isinstance(item, dict) or item.get("kind") not in KINDS:
                raise ApiErr(400, "Each rotating message needs a valid activity kind.")
            t = str(item.get("text", "")).strip()[:128]
            if t:
                items.append({"kind": item["kind"], "text": t})
        if len(items) > MAX_ROTATION:
            raise ApiErr(400, f"Rotate between at most {MAX_ROTATION} messages.")
        if rotate and not items:
            raise ApiErr(400, "Add at least one message to rotate through, or turn rotation off.")
        try:
            interval = int(body.get("interval", 120))
        except (TypeError, ValueError):
            raise ApiErr(400, "The interval must be a number of seconds.")
        if not MIN_INTERVAL <= interval <= 86400:
            raise ApiErr(400, f"The interval must be between {MIN_INTERVAL} seconds and one day.")
        if any(i["kind"] == "streaming" for i in items) and not url:
            raise ApiErr(400, "A streaming message needs the stream link.")
        self.store.data["presence"] = {"kind": kind, "text": text, "status": status, "url": url, "rotate": rotate, "interval": interval, "items": items}
        self.step = 0
        self.last_rotation = time.time()
        self.store.save()
        await self.apply_presence()
        self.note(actor, "presence", f"{kind} {text}".strip() or ("rotating" if rotate else "cleared"))
        return dict(self.store.data["presence"])

    async def app_profile(self):
        """What Discord shows on the bot's profile: the About Me text and the Add to server link."""
        try:
            data = await self.bot.http.request(discord.http.Route("GET", "/applications/@me"))
        except Exception as error:
            raise ApiErr(502, f"Discord wouldn't tell us: {str(error)[:150]}")
        return {"description": data.get("description", ""), "installUrl": data.get("custom_install_url") or "", "tags": data.get("tags", []), "inviteLink": f"https://discord.com/oauth2/authorize?client_id={data.get('id', self.bot.user.id if self.bot.user else '')}&scope=bot+applications.commands&permissions=8"}

    async def set_app_profile(self, actor, body):
        change = {}
        if "description" in body:
            description = str(body["description"]).strip()
            if len(description) > 400:
                raise ApiErr(400, "The About Me text can be up to 400 characters.")
            change["description"] = description
        if "installUrl" in body:
            url = str(body["installUrl"]).strip()
            if url and (not url.startswith("https://") or len(url) > 500 or any(c.isspace() for c in url)):
                raise ApiErr(400, "The install link must start with https:// and have no spaces.")
            change["custom_install_url"] = url or None
        if "tags" in body:
            tags = [str(t).strip()[:20] for t in body["tags"] if str(t).strip()] if isinstance(body["tags"], list) else None
            if tags is None or len(tags) > 5:
                raise ApiErr(400, "Send up to 5 tags.")
            change["tags"] = tags
        if not change:
            raise ApiErr(400, "Nothing to change.")
        try:
            await self.bot.http.request(discord.http.Route("PATCH", "/applications/@me"), json=change)
        except Exception as error:
            raise ApiErr(502, f"Discord refused the change: {str(error)[:150]}")
        self.note(actor, "bot profile", ", ".join(change))
        return await self.app_profile()

    async def say(self, actor, body):
        channel = self.bot.get_channel(snowflake(body.get("channel_id"), "Channel id"))
        text = str(body.get("text", "")).strip()
        if not isinstance(channel, discord.abc.Messageable) or not text or len(text) > 2000:
            raise ApiErr(400, "Pick a channel Risk can see and write 1 to 2000 characters.")
        try:
            sent = await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as error:
            raise ApiErr(400, f"Discord refused: {error.text or error.status}")
        self.note(actor, "say", f"#{getattr(channel, 'name', channel.id)}")
        return {"id": str(sent.id)}

    async def leave(self, actor, body):
        guild = self.bot.get_guild(snowflake(body.get("guild_id"), "Server id"))
        if guild is None:
            raise ApiErr(404, "Risk isn't in that server.")
        name = guild.name
        await guild.leave()
        self.note(actor, "left server", f"{name} ({guild.id})")
        return {"left": name}

    async def reload(self, actor, body):
        name = str(body.get("cog", "")).strip().lower()
        if not name.isidentifier() or name == "owner_control":
            raise ApiErr(400, "Name a cog file, like levels. owner_control can't reload itself.")
        try:
            if f"cogs.{name}" in self.bot.extensions:
                await self.bot.reload_extension(f"cogs.{name}")
            else:
                await self.bot.load_extension(f"cogs.{name}")
        except Exception as error:
            raise ApiErr(400, f"{name} failed to load: {str(error)[:200]}")
        self.note(actor, "reload", name)
        return {"cog": name, "commands": len(self.bot.commands)}

    # ------------------------------------------------------------------ the status page
    def page(self):
        page = self.bot.get_cog("StatusPage")
        if page is None:
            raise ApiErr(503, "The status page isn't loaded. Upload cogs/status_page.py and restart the bot.")
        return page

    def page_call(self, actor, what, body):
        """Runs a status page change and turns its errors into API errors."""
        page = self.page()
        try:
            if what == "buttons":
                out = {"buttons": page.set_buttons(body.get("buttons"))}
            elif what == "notice":
                out = page.set_notice(body)
            elif what == "incident/add":
                out = page.add_incident(body)
            elif what == "incident/resolve":
                out = page.resolve_incident(str(body.get("id", "")), body.get("text", ""))
            elif what == "incident/remove":
                out = page.remove_incident(str(body.get("id", "")))
            else:
                raise ApiErr(404, "No such action.")
        except Exception as error:
            if type(error).__name__ == "PageError":
                raise ApiErr(error.status, error.message)
            raise
        self.note(actor, "status page " + what)
        return out

    async def broadcast(self, actor, body):
        text = str(body.get("text", "")).strip()
        if not 1 <= len(text) <= 1500:
            raise ApiErr(400, "Write 1 to 1500 characters.")
        vip = self.bot.get_cog("VIP")
        banned = self.bot.get_cog("Staff").store.data["banned"] if self.bot.get_cog("Staff") else {}
        targets = [g for g in self.bot.guilds if str(g.id) not in banned and (body.get("only_vip") is not True or (vip and vip.info(g.id)["vip"]))]
        self.note(actor, "broadcast", f"{len(targets)} servers: {text[:60]}")

        async def run():
            sent = failed = 0
            for guild in targets:
                me = guild.me
                channel = guild.system_channel if guild.system_channel and me and guild.system_channel.permissions_for(me).send_messages else next((c for c in guild.text_channels if me and c.permissions_for(me).send_messages), None)
                try:
                    if channel is None:
                        raise discord.HTTPException(None, "no channel")
                    await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
                    sent += 1
                except discord.HTTPException:
                    failed += 1
                await asyncio.sleep(0.6)
            print(f"[broadcast] sent to {sent} servers, {failed} failed")

        asyncio.get_running_loop().create_task(run())
        return {"queued": len(targets)}

    async def backup(self, actor):
        folder = store_module.DATA_DIR
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.glob("*.json")):
                archive.write(path, path.name)
        raw = buffer.getvalue()
        if len(raw) > 25 * 1024 * 1024:
            raise ApiErr(413, "The backup is too large to send. Download data/ from your host instead.")
        self.note(actor, "backup", f"{len(raw)} bytes")
        return {"name": time.strftime("risk-data-%Y%m%d-%H%M%S.zip"), "size": len(raw), "data": base64.b64encode(raw).decode()}

    def schedule_exit(self, restart):
        async def go():
            await asyncio.sleep(1)
            await self.bot.close()
            if restart:
                try:
                    os.execv(sys.executable, [sys.executable, *sys.argv])
                except OSError:
                    pass
            os._exit(0)
        asyncio.get_running_loop().create_task(go())

    # ------------------------------------------------------------------ http
    def key(self):
        key = os.getenv("OWNER_PANEL_KEY", "")
        if len(key) < MIN_KEY:
            raise ApiErr(503, f"The owner API is off. Set OWNER_PANEL_KEY (at least {MIN_KEY} characters) on the bot's host.")
        return key

    async def authenticate(self, request, body):
        key = self.key()
        now = time.time()
        stamp, nonce, given = (request.headers.get(h, "") for h in ("X-Owner-Time", "X-Owner-Nonce", "X-Owner-Sig"))
        good = False
        if stamp.isdigit() and 8 <= len(nonce) <= 64 and abs(now - int(stamp)) <= WINDOW and nonce not in self.nonces:
            good = hmac.compare_digest(sign(key, request.method, request.path, stamp, nonce, body), given)
        if not good:
            await asyncio.sleep(0.5)
            raise ApiErr(401, "Not allowed.")
        self.nonces = {n: t for n, t in self.nonces.items() if now - t < WINDOW * 2}
        self.nonces[nonce] = now

    async def handle(self, request):
        try:
            body = await request.read()
            await self.authenticate(request, body)
            parts = [p for p in request.match_info["tail"].split("/") if p]
            data = {}
            if body:
                try:
                    data = json.loads(body)
                except ValueError:
                    raise ApiErr(400, "That wasn't valid JSON.")
                if not isinstance(data, dict):
                    raise ApiErr(400, "Send an object.")
            return web.json_response(await self.route(request.method, parts, data))
        except ApiErr as error:
            return web.json_response({"error": error.message}, status=error.status)
        except Exception as error:
            if type(error).__name__ == "StaffError":
                return web.json_response({"error": error.message}, status=error.status)
            traceback.print_exc()
            return web.json_response({"error": "The bot hit an error. Check its console."}, status=500)

    async def route(self, method, parts, body):
        actor = await self.owner_uid()
        if method == "GET":
            if parts == ["status"]:
                return self.status()
            if parts == ["panel"]:
                return await self.staff().owner_panel(actor)
            if parts == ["commands"]:
                return {"commands": self.command_list()}
            if parts == ["blocked"]:
                return {"blocked": self.blocked_list()}
            if parts == ["logs"]:
                return {"lines": list(self.lines)}
            if parts == ["appprofile"]:
                return await self.app_profile()
            if parts == ["statuspage"]:
                return self.page().editable()
            if parts == ["cogs"]:
                return {"loaded": sorted(self.bot.extensions), "files": sorted(p.stem for p in Path(__file__).parent.glob("*.py") if not p.stem.startswith("_"))}
            if len(parts) == 2 and parts[0] == "guild":
                return self.guild_detail(snowflake(parts[1], "Server id"))
            raise ApiErr(404, "No such page.")
        if method != "POST" or len(parts) < 1:
            raise ApiErr(405, "Use GET to read and POST to change things.")
        action = "/".join(parts)
        staff_actions = {"prices": "set_prices", "vip": "set_vip", "ban": "ban_server", "unban": "unban_server", "roles": "assign_role"}
        if action in staff_actions:
            return await getattr(self.staff(), staff_actions[action])(actor, body)
        if action in ("statuspage/buttons", "statuspage/notice", "incident/add", "incident/resolve", "incident/remove"):
            return self.page_call(actor, action.replace("statuspage/", ""), body)
        if action == "broadcast":
            return await self.broadcast(actor, body)
        if action == "appprofile":
            return await self.set_app_profile(actor, body)
        if action == "backup":
            return await self.backup(actor)
        if action == "commands":
            return await self.set_command(actor, body)
        if action == "blocked/add":
            return await self.set_blocked(actor, body, True)
        if action == "blocked/remove":
            return await self.set_blocked(actor, body, False)
        simple = {"maintenance": self.set_maintenance, "presence": self.set_presence, "say": self.say, "leave": self.leave, "reload": self.reload}
        if action in simple:
            return await simple[action](actor, body)
        if action in ("shutdown", "restart"):
            self.note(actor, action)
            self.schedule_exit(action == "restart")
            return {"ok": True, "message": "Shutting down in a second." if action == "shutdown" else "Restarting in a second."}
        raise ApiErr(404, "No such action.")


async def setup(bot):
    await bot.add_cog(OwnerControl(bot))
