"""Settings API for the website dashboard, plus per-server prefix and command switches.

The website signs people in with Discord and forwards their requests here with a shared key
(DASHBOARD_KEY). Every request is checked again in this file: the user must be the server owner
or hold Administrator or Manage Server in that server, and every value is validated.
"""
import asyncio
import copy
import hmac
import json
import os
import re
import traceback

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands

from cogs.commands_list import CATEGORY_BY_COG
from cogs.log_tools import CATEGORIES as LOG_CATEGORIES
from utils.helpers import ModError, explain_error
from utils.store import JsonStore

DEFAULT_PREFIXES = ("!", "?", ",")
NEVER_MATCHES = "​​ignored​​"
SECTIONS = ("general", "welcome", "logs", "levels", "automod", "community")
MAX_BODY = 20_000
USER_AGENT = {"User-Agent": "DiscordBot (https://github.com/lebashaca-cmd/Risk, 1.0)"}
SNOWFLAKE = re.compile(r"\d{15,21}")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# Validation helpers
def as_bool(value, name):
    if not isinstance(value, bool):
        raise ApiError(400, f"{name} must be on or off.")
    return value


def as_int(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ApiError(400, f"{name} must be a whole number.")
    if not low <= value <= high:
        raise ApiError(400, f"{name} must be between {low} and {high}.")
    return int(value)


def as_float(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, f"{name} must be a number.")
    if not low <= value <= high:
        raise ApiError(400, f"{name} must be between {low:g} and {high:g}.")
    return round(float(value), 2)


def as_text(value, name, limit, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(400, f"{name} must be text.")
    value = value.strip()
    if required and not value:
        raise ApiError(400, f"{name} can't be empty.")
    if len(value) > limit:
        raise ApiError(400, f"{name} can be up to {limit} characters.")
    return value


def as_snowflake(value, name):
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not SNOWFLAKE.fullmatch(value):
        raise ApiError(400, f"{name} isn't valid.")
    return int(value)


def as_list(value, name, limit):
    if not isinstance(value, list):
        raise ApiError(400, f"{name} must be a list.")
    if len(value) > limit:
        raise ApiError(400, f"{name} can have up to {limit} items.")
    return value


def pick_channel(guild, value, name, need_send=True):
    """A text channel id (or None) from the request. Checks the channel exists and the bot can post."""
    if value in (None, ""):
        return None
    channel = guild.get_channel(as_snowflake(value, name))
    if not isinstance(channel, discord.TextChannel):
        raise ApiError(400, f"{name} must be a text channel in this server.")
    if need_send and not channel.permissions_for(guild.me).send_messages:
        raise ApiError(400, f"I can't send messages in #{channel.name}. Give me access or pick another channel.")
    return channel.id


def pick_channels(guild, values, name, limit=50):
    found = []
    for value in as_list(values, name, limit):
        channel = pick_channel(guild, value, name, need_send=False)
        if channel is not None and channel not in found:
            found.append(channel)
    return found


def pick_role(guild, value, name, assignable=False):
    if value in (None, ""):
        return None
    role = guild.get_role(as_snowflake(value, name))
    if role is None:
        raise ApiError(400, f"{name} isn't a role in this server.")
    if assignable and (role.is_default() or role.managed or role >= guild.me.top_role):
        raise ApiError(400, f"I can't hand out @{role.name}. Move my role above it, and avoid @everyone and bot roles.")
    return role.id


def pick_roles(guild, values, name, limit=50):
    found = []
    for value in as_list(values, name, limit):
        role = pick_role(guild, value, name)
        if role is not None and role not in found:
            found.append(role)
    return found


class Dashboard(commands.Cog):
    """Per-server prefix, command switches and the website dashboard's settings API."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("dashboard")

    async def cog_load(self):
        self.bot.add_check(self.command_allowed)

    def cog_unload(self):
        self.bot.remove_check(self.command_allowed)

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Per-server prefix and command switches
    def cfg(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {})
        data.setdefault("prefix", None)
        data.setdefault("disabled_commands", [])
        data.setdefault("ignored_channels", [])
        return data

    async def command_allowed(self, ctx):
        if ctx.guild is None or ctx.command is None:
            return True
        config = self.store.data.get(str(ctx.guild.id))
        if not config:
            return True
        root = ctx.command.root_parent or ctx.command
        if root.name in config.get("disabled_commands", []):
            perms = getattr(ctx.author, "guild_permissions", None)
            if not (perms and (perms.administrator or perms.manage_guild)):
                raise ModError(f"`{root.name}` is turned off in this server.")
        return True

    def prefixes_for(self, message):
        base = list(DEFAULT_PREFIXES)
        if message.guild is None:
            return base
        config = self.store.data.get(str(message.guild.id))
        if not config:
            return base
        perms = getattr(message.author, "guild_permissions", None)
        staff = bool(perms and (perms.administrator or perms.manage_guild))
        if message.channel.id in config.get("ignored_channels", []) and not staff:
            return [NEVER_MATCHES]
        custom = config.get("prefix")
        return ([custom] if custom else []) + base

    @commands.command(name="prefix")
    @commands.guild_only()
    async def prefix(self, ctx, new: str = None):
        """Shows or changes this server's extra prefix (the defaults ! ? , always work). Usage: !prefix $"""
        config = self.cfg(ctx.guild.id)
        if new is None:
            custom = config["prefix"]
            await ctx.reply(f"Prefixes: `!` `?` `,`" + (f" and `{custom}`" if custom else "") + ". Staff can change the extra one with `!prefix <new>` or `!prefix reset`.", mention_author=False)
            return
        if not ctx.author.guild_permissions.manage_guild:
            raise commands.MissingPermissions(["manage_guild"])
        if new.lower() == "reset":
            config["prefix"] = None
            self.store.save()
            await ctx.reply("The extra prefix was removed.", mention_author=False)
            return
        if not 1 <= len(new) <= 3 or any(c in new for c in "`@#*_~|\\") or new in DEFAULT_PREFIXES:
            await ctx.reply("Use 1 to 3 characters that aren't a default prefix or markdown symbol.", mention_author=False)
            return
        config["prefix"] = new
        self.store.save()
        await ctx.reply(f"The extra prefix is now `{new}`. The defaults still work.", mention_author=False)

    @commands.command(name="dashboard", aliases=["settings"])
    @commands.guild_only()
    async def dashboard(self, ctx):
        """Shows the link to the website dashboard where staff change Risk's settings. Usage: !dashboard"""
        url = os.getenv("DASHBOARD_URL", "").strip()
        if not url.startswith("https://"):
            await ctx.reply("The dashboard link isn't set up yet.", mention_author=False)
            return
        await ctx.reply(f"Staff with Manage Server can change settings here: {url}", mention_author=False)

    # Helpers for the API
    def feature_cogs(self):
        names = ("Welcome", "ServerLogs", "LogTools", "Levels", "AutoMod", "Community", "CommunityExtra", "Tickets")
        return {name: self.bot.get_cog(name) for name in names}

    def guild_card(self, guild):
        return {"id": str(guild.id), "name": guild.name, "icon": guild.icon.replace(size=128, format="png").url if guild.icon else None, "members": guild.member_count}

    async def authorize(self, guild, user_id):
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                member = None
        if member is None:
            raise ApiError(403, "You aren't in that server.")
        perms = member.guild_permissions
        if not (member.id == guild.owner_id or perms.administrator or perms.manage_guild):
            raise ApiError(403, "You need Manage Server in that server.")
        return member

    def meta(self, guild):
        me = guild.me
        channels = [
            {"id": str(c.id), "name": c.name, "category": c.category.name if c.category else None, "canSend": c.permissions_for(me).send_messages}
            for c in sorted(guild.text_channels, key=lambda c: (c.category.position if c.category else -1, c.position))
        ]
        roles = [
            {"id": str(r.id), "name": r.name, "color": f"#{r.color.value:06x}" if r.color.value else None, "assignable": not (r.is_default() or r.managed or r >= me.top_role)}
            for r in sorted(guild.roles, key=lambda r: -r.position) if not r.is_default()
        ]
        cmds = sorted(
            ({"name": c.name, "category": CATEGORY_BY_COG.get(c.cog_name or "", "Other")} for c in self.bot.commands if c.name != "dashboard"),
            key=lambda c: (c["category"], c["name"]),
        )
        return {
            "channels": channels,
            "roles": roles,
            "commands": cmds,
            "logCategories": [{"id": key, "label": label} for key, (label, _) in LOG_CATEGORIES.items()],
            "defaultPrefixes": list(DEFAULT_PREFIXES),
        }

    # Sections: each pair reads the current settings and applies a validated update.
    def read_general(self, guild):
        config = self.cfg(guild.id)
        return {"prefix": config["prefix"], "disabledCommands": list(config["disabled_commands"]), "ignoredChannels": [str(c) for c in config["ignored_channels"]]}

    def write_general(self, guild, body):
        config = self.cfg(guild.id)
        if "prefix" in body:
            prefix = body["prefix"]
            if prefix in (None, ""):
                config["prefix"] = None
            else:
                prefix = as_text(prefix, "Prefix", 3)
                if not prefix or any(c.isspace() or c in "`@#*_~|\\" for c in prefix) or prefix in DEFAULT_PREFIXES:
                    raise ApiError(400, "The prefix must be 1 to 3 characters, no spaces or markdown symbols, and not one of ! ? ,")
                config["prefix"] = prefix
        if "disabledCommands" in body:
            valid = {c.name for c in self.bot.commands}
            names = []
            for name in as_list(body["disabledCommands"], "Disabled commands", 300):
                if name not in valid or name == "dashboard":
                    raise ApiError(400, f"`{str(name)[:30]}` isn't a command that can be switched off.")
                if name not in names:
                    names.append(name)
            config["disabled_commands"] = names
        if "ignoredChannels" in body:
            config["ignored_channels"] = pick_channels(guild, body["ignoredChannels"], "Ignored channels")
        self.store.save()

    def read_welcome(self, guild):
        entry = self.bot.get_cog("Welcome").config.data.get(str(guild.id), {})
        return {
            "enabled": bool(entry.get("channel") and entry.get("text")),
            "channel": str(entry["channel"]) if entry.get("channel") else None,
            "text": entry.get("text", ""),
            "leaveEnabled": bool(entry.get("leave_channel") and entry.get("leave_text")),
            "leaveChannel": str(entry["leave_channel"]) if entry.get("leave_channel") else None,
            "leaveText": entry.get("leave_text", ""),
        }

    def write_welcome(self, guild, body):
        cog = self.bot.get_cog("Welcome")
        current = self.read_welcome(guild)
        merged = {**current, **{k: v for k, v in body.items() if k in current}}
        entry = dict(cog.config.data.get(str(guild.id), {}))
        for prefix, on, chan, text, label in (("", "enabled", "channel", "text", "Welcome"), ("leave_", "leaveEnabled", "leaveChannel", "leaveText", "Leave")):
            if as_bool(merged[on], f"{label} messages"):
                channel = pick_channel(guild, merged[chan], f"{label} channel")
                message = as_text(merged[text], f"{label} message", 1500, required=True)
                if channel is None:
                    raise ApiError(400, f"Pick a channel for the {label.lower()} message.")
                entry[prefix + "channel"], entry[prefix + "text"] = channel, message
            else:
                entry.pop(prefix + "channel", None)
                entry.pop(prefix + "text", None)
        if entry:
            cog.config.data[str(guild.id)] = entry
        else:
            cog.config.data.pop(str(guild.id), None)
        cog.config.save()

    def read_logs(self, guild):
        serverlogs, tools = self.bot.get_cog("ServerLogs"), self.bot.get_cog("LogTools")
        config = tools.cfg(guild.id)
        channel = serverlogs.config.get(str(guild.id))
        return {
            "channel": str(channel) if channel else None,
            "disabled": [c for c in config["off"] if c in LOG_CATEGORIES],
            "routes": {k: str(v) for k, v in config["routes"].items() if k in LOG_CATEGORIES},
            "ignoredChannels": [str(c) for c in config["ignored"]],
        }

    def write_logs(self, guild, body):
        serverlogs, tools = self.bot.get_cog("ServerLogs"), self.bot.get_cog("LogTools")
        config = tools.cfg(guild.id)
        if "channel" in body:
            channel = pick_channel(guild, body["channel"], "Log channel")
            if channel is None:
                serverlogs.config.pop(str(guild.id), None)
            else:
                serverlogs.config[str(guild.id)] = channel
            serverlogs._save()
        if "disabled" in body:
            config["off"] = [c for c in dict.fromkeys(as_list(body["disabled"], "Switched off logs", 30)) if c in LOG_CATEGORIES]
        if "routes" in body:
            routes = body["routes"]
            if not isinstance(routes, dict):
                raise ApiError(400, "Log routes must be a list of categories.")
            clean = {}
            for category, value in routes.items():
                if category not in LOG_CATEGORIES:
                    raise ApiError(400, "Unknown log category.")
                channel = pick_channel(guild, value, "Log route")
                if channel is not None:
                    clean[category] = channel
            config["routes"] = clean
        if "ignoredChannels" in body:
            config["ignored"] = pick_channels(guild, body["ignoredChannels"], "Ignored channels")
        tools.store.save()

    def read_levels(self, guild):
        config = self.bot.get_cog("Levels").cfg(guild.id)
        return {
            "announce": config["channel"] if config["channel"] in ("same", "off") else str(config["channel"]),
            "message": config["message"] or "",
            "multiplier": config["multiplier"],
            "cooldown": config["cooldown"],
            "mode": config["mode"],
            "noxpChannels": [str(c) for c in config["noxp_channels"]],
            "noxpRoles": [str(r) for r in config["noxp_roles"]],
            "rewards": sorted(({"level": int(level), "role": str(role)} for level, role in config["rewards"].items()), key=lambda r: r["level"]),
        }

    def write_levels(self, guild, body):
        cog = self.bot.get_cog("Levels")
        config = cog.cfg(guild.id)
        if "announce" in body:
            value = body["announce"]
            config["channel"] = value if value in ("same", "off") else pick_channel(guild, value, "Level-up channel")
            if config["channel"] is None:
                config["channel"] = "same"
        if "message" in body:
            text = as_text(body["message"], "Level-up message", 500)
            config["message"] = text or None
        if "multiplier" in body:
            config["multiplier"] = as_float(body["multiplier"], "XP multiplier", 0.5, 5)
        if "cooldown" in body:
            config["cooldown"] = as_int(body["cooldown"], "XP cooldown", 10, 600)
        if "mode" in body:
            if body["mode"] not in ("stack", "replace"):
                raise ApiError(400, "Reward mode must be stack or replace.")
            config["mode"] = body["mode"]
        if "noxpChannels" in body:
            config["noxp_channels"] = pick_channels(guild, body["noxpChannels"], "No-XP channels")
        if "noxpRoles" in body:
            config["noxp_roles"] = pick_roles(guild, body["noxpRoles"], "No-XP roles")
        if "rewards" in body:
            rewards = {}
            for item in as_list(body["rewards"], "Level rewards", 25):
                if not isinstance(item, dict):
                    raise ApiError(400, "Each reward needs a level and a role.")
                level = as_int(item.get("level"), "Reward level", 1, 1000)
                role = pick_role(guild, item.get("role"), "Reward role", assignable=True)
                if role is None:
                    raise ApiError(400, "Pick a role for each reward.")
                rewards[str(level)] = role
            config["rewards"] = rewards
        cog.settings.save()

    def read_automod(self, guild):
        config = self.bot.get_cog("AutoMod").cfg(guild.id)
        return {
            "antilink": config["antilink"], "antiinvite": config["antiinvite"], "antispam": config["antispam"],
            "maxMentions": config["maxmentions"], "badWords": list(config["badwords"]),
            "ignoreChannels": [str(c) for c in config["ignore_channels"]], "ignoreRoles": [str(r) for r in config["ignore_roles"]],
        }

    def write_automod(self, guild, body):
        cog = self.bot.get_cog("AutoMod")
        config = cog.cfg(guild.id)
        for key, name in (("antilink", "Link blocking"), ("antiinvite", "Invite blocking"), ("antispam", "Spam protection")):
            if key in body:
                config[key] = as_bool(body[key], name)
        if "maxMentions" in body:
            config["maxmentions"] = as_int(body["maxMentions"], "Mention limit", 0, 50)
        if "badWords" in body:
            words = []
            for word in as_list(body["badWords"], "Blocked words", 100):
                word = as_text(word, "A blocked word", 40).lower()
                if not 2 <= len(word) <= 40:
                    raise ApiError(400, "Each blocked word needs 2 to 40 characters.")
                if word not in words:
                    words.append(word)
            config["badwords"] = words
        if "ignoreChannels" in body:
            config["ignore_channels"] = pick_channels(guild, body["ignoreChannels"], "Ignored channels")
        if "ignoreRoles" in body:
            config["ignore_roles"] = pick_roles(guild, body["ignoreRoles"], "Ignored roles")
        cog.store.save()

    def read_community(self, guild):
        community, extra, tickets = self.bot.get_cog("Community"), self.bot.get_cog("CommunityExtra"), self.bot.get_cog("Tickets")
        settings, extras = community.cfg(guild.id), extra.cfg(guild.id)
        text = lambda value: str(value) if value else None
        return {
            "autorole": text(settings["autorole"]),
            "suggestionChannel": text(community.sugg(guild.id)["channel"]),
            "starboardChannel": text(settings["starboard"]["channel"]),
            "starboardThreshold": settings["starboard"]["threshold"],
            "birthdayChannel": text(extras["birthday_channel"]),
            "reportChannel": text(extras["report_channel"]),
            "countingChannel": text(extras["counting"]["channel"]),
            "ticketLogChannel": text(tickets._guild(guild.id).get("log_channel")),
            "rules": extras["rules"],
        }

    def write_community(self, guild, body):
        community, extra, tickets = self.bot.get_cog("Community"), self.bot.get_cog("CommunityExtra"), self.bot.get_cog("Tickets")
        settings, extras = community.cfg(guild.id), extra.cfg(guild.id)
        if "autorole" in body:
            settings["autorole"] = pick_role(guild, body["autorole"], "Auto role", assignable=True)
        if "suggestionChannel" in body:
            community.sugg(guild.id)["channel"] = pick_channel(guild, body["suggestionChannel"], "Suggestion channel")
        if "starboardChannel" in body:
            settings["starboard"]["channel"] = pick_channel(guild, body["starboardChannel"], "Starboard channel")
        if "starboardThreshold" in body:
            settings["starboard"]["threshold"] = as_int(body["starboardThreshold"], "Star threshold", 1, 25)
        if "birthdayChannel" in body:
            extras["birthday_channel"] = pick_channel(guild, body["birthdayChannel"], "Birthday channel")
        if "reportChannel" in body:
            extras["report_channel"] = pick_channel(guild, body["reportChannel"], "Report channel")
        if "countingChannel" in body:
            channel = pick_channel(guild, body["countingChannel"], "Counting channel")
            if channel != extras["counting"]["channel"]:
                extras["counting"].update(channel=channel, number=0, last=None)
        if "ticketLogChannel" in body:
            tickets._guild(guild.id)["log_channel"] = pick_channel(guild, body["ticketLogChannel"], "Ticket log channel")
            tickets._save()
        if "rules" in body:
            extras["rules"] = as_text(body["rules"], "Rules", 1500)
        community.settings.save()
        community.suggestions.save()
        extra.store.save()

    # HTTP entry point (routed from main.py)
    def check_key(self, request):
        expected = os.getenv("DASHBOARD_KEY", "")
        if len(expected) < 16:
            raise ApiError(503, "The dashboard isn't enabled on the bot.")
        given = request.headers.get("X-Dashboard-Key", "")
        if not hmac.compare_digest(given.encode(), expected.encode()):
            raise ApiError(401, "Bad dashboard key.")

    async def read_json(self, request):
        raw = await request.content.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ApiError(413, "That request is too large.")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise ApiError(400, "The request wasn't valid JSON.")
        if not isinstance(body, dict):
            raise ApiError(400, "The request must be a JSON object.")
        return body

    async def handle(self, request):
        try:
            self.check_key(request)
            if not self.bot.is_ready():
                raise ApiError(503, "The bot is starting up. Try again in a minute.")
            parts = [p for p in request.match_info["tail"].split("/") if p]
            payload = await self.route(request, request.method, parts)
            return web.json_response(payload)
        except ApiError as error:
            return web.json_response({"error": error.message}, status=error.status)
        except Exception:
            traceback.print_exc()
            return web.json_response({"error": "The bot hit an error while handling that. Check the bot's console for the details."}, status=500)

    async def route(self, request, method, parts):
        if parts == ["oauth"] and method == "POST":
            return await self.oauth(await self.read_json(request))

        if parts == ["present"] and method == "POST":
            body = await self.read_json(request)
            ids = [as_snowflake(i, "Server id") for i in as_list(body.get("ids", []), "Server ids", 200)]
            return {"guilds": [self.guild_card(g) for g in (self.bot.get_guild(i) for i in ids) if g is not None]}

        if len(parts) < 2 or parts[0] != "guild":
            raise ApiError(404, "Not found.")
        guild = self.bot.get_guild(as_snowflake(parts[1], "Server id"))
        if guild is None:
            raise ApiError(404, "Risk isn't in that server.")
        user_id = as_snowflake(request.headers.get("X-Dashboard-User", ""), "User id")
        member = await self.authorize(guild, user_id)

        if len(parts) == 2 and method == "GET":
            return {
                "guild": self.guild_card(guild),
                "meta": self.meta(guild),
                "settings": {name: getattr(self, f"read_{name}")(guild) for name in SECTIONS},
            }
        if len(parts) == 3 and method == "PUT" and parts[2] in SECTIONS:
            body = await self.read_json(request)
            await self.apply(guild, parts[2], body)
            await self.audit(guild, member, parts[2])
            return {"settings": getattr(self, f"read_{parts[2]}")(guild)}
        raise ApiError(404, "Not found.")

    # Sign-in: the site hands over Discord's login code and the bot talks to Discord from its own address.
    @staticmethod
    def sign_in_reason(status, raw, step):
        try:
            body = json.loads(raw)
        except ValueError:
            body = None
        error = body.get("error") if isinstance(body, dict) else None
        detail = str(body.get("error_description", "")) if isinstance(body, dict) else ""
        if body is None and status in (403, 429, 503):
            return "blocked"
        if status == 429:
            return "busy"
        if step == "token exchange":
            if status == 401 or error == "invalid_client":
                return "secret"
            if error == "invalid_grant":
                return "redirect" if "redirect_uri" in detail else "expired"
        return "failed"

    async def oauth(self, body):
        secret = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
        if not secret:
            raise ApiError(503, "The bot has no DISCORD_CLIENT_SECRET set.")
        code = as_text(body.get("code"), "Code", 300, required=True)
        redirect = as_text(body.get("redirect_uri"), "Redirect address", 300, required=True)
        if not redirect.endswith("/api/auth/callback"):
            raise ApiError(400, "That redirect address isn't valid.")
        api = os.getenv("DISCORD_API", "https://discord.com/api/v10").rstrip("/")
        client_id = str(self.bot.application_id or (self.bot.user.id if self.bot.user else ""))
        timeout = aiohttp.ClientTimeout(total=10)
        token = None
        try:
            async with aiohttp.ClientSession(headers=USER_AGENT, timeout=timeout) as http:
                try:
                    async with http.post(f"{api}/oauth2/token", data={"client_id": client_id, "client_secret": secret, "grant_type": "authorization_code", "code": code, "redirect_uri": redirect}) as resp:
                        text = await resp.text()
                        if resp.status != 200:
                            print(f"[dashboard] Discord token exchange answered {resp.status}: {text[:300]!r}", flush=True)
                            return {"ok": False, "reason": self.sign_in_reason(resp.status, text[:300], "token exchange")}
                        payload = json.loads(text)
                        token = payload.get("access_token") if isinstance(payload, dict) else None
                    if not isinstance(token, str):
                        return {"ok": False, "reason": "failed"}
                    auth = {"Authorization": f"Bearer {token}"}
                    results = {}
                    for key, path in (("user", "/users/@me"), ("guilds", "/users/@me/guilds")):
                        async with http.get(f"{api}{path}", headers=auth) as resp:
                            text = await resp.text()
                            if resp.status != 200:
                                print(f"[dashboard] Discord {key} lookup answered {resp.status}: {text[:300]!r}", flush=True)
                                return {"ok": False, "reason": self.sign_in_reason(resp.status, text[:300], key)}
                            results[key] = json.loads(text)
                    return {"ok": True, **results}
                finally:
                    if token:
                        try:
                            await http.post(f"{api}/oauth2/token/revoke", data={"client_id": client_id, "client_secret": secret, "token": token})
                        except (aiohttp.ClientError, asyncio.TimeoutError):
                            pass
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            print(f"[dashboard] Couldn't reach Discord: {type(error).__name__}: {str(error)[:200]}", flush=True)
            return {"ok": False, "reason": "unreachable"}

    def stores_for(self, section):
        """The live dicts a section writes to, so a failed update can be rolled back."""
        cog = self.bot.get_cog
        mapping = {
            "general": [self.store.data],
            "welcome": [cog("Welcome").config.data],
            "logs": [cog("ServerLogs").config, cog("LogTools").store.data],
            "levels": [cog("Levels").settings.data],
            "automod": [cog("AutoMod").store.data],
            "community": [cog("Community").settings.data, cog("Community").suggestions.data, cog("CommunityExtra").store.data, cog("Tickets").config],
        }
        return mapping[section]

    async def apply(self, guild, section, body):
        for name in {"general": [], "welcome": ["Welcome"], "logs": ["ServerLogs", "LogTools"], "levels": ["Levels"], "automod": ["AutoMod"], "community": ["Community", "CommunityExtra", "Tickets"]}[section]:
            if self.bot.get_cog(name) is None:
                raise ApiError(503, f"The {name} feature isn't loaded on the bot.")
        stores = self.stores_for(section)
        snapshots = [copy.deepcopy(d) for d in stores]
        try:
            getattr(self, f"write_{section}")(guild, body)
        except Exception:
            for live, saved in zip(stores, snapshots):
                live.clear()
                live.update(saved)
            raise

    async def audit(self, guild, member, section):
        logs = self.bot.get_cog("ServerLogs")
        if logs is None:
            return
        try:
            await logs.send(guild, "Dashboard Updated", discord.Color.blurple(), description=f"{member.mention} changed the **{section}** settings on the website dashboard.", user=member)
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Dashboard(bot))
