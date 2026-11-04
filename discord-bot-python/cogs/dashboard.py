"""Settings API for the website dashboard, plus per-server prefix and command switches.

The website signs people in with Discord and forwards their requests here with a shared key
(DASHBOARD_KEY). Every request is checked again in this file: the user must be the server owner
or hold Administrator or Manage Server in that server, and every value is validated.
"""
import asyncio
import base64
import binascii
import copy
import hmac
import json
import os
import re
import time
import traceback

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands

try:
    from cogs.commands_list import CATEGORY_BY_COG
except ImportError:  # an older commands_list.py on the host
    CATEGORY_BY_COG = {}
try:
    from cogs.vip import LIMITS, PERKS
except ImportError:  # vip.py not uploaded yet: everyone is on the free plan
    LIMITS, PERKS = {"responders": (5, 50), "command_rules": (5, 100), "schedules": (0, 10), "badwords": (25, 100), "level_rewards": (5, 25), "xp_multiplier": (2.0, 5.0), "ignored_channels": (10, 50)}, []
try:
    from cogs.log_tools import CATEGORIES as LOG_CATEGORIES
except ImportError:  # log_tools.py missing or old
    LOG_CATEGORIES = {}
from utils.helpers import ModError, explain_error
from utils.store import JsonStore

DEFAULT_PREFIXES = ("!", "?", ",")
NEVER_MATCHES = "​​ignored​​"
SECTIONS = ("general", "welcome", "logs", "levels", "automod", "community", "commands", "responders", "announcements", "vip")
READ_ONLY = ("overview",)
MAX_BODY = 20_000
MAX_PROFILE_BODY = 7_500_000
IMAGE_LIMITS = {"avatar": 2_000_000, "banner": 3_000_000}
IMAGE_SIGNATURES = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpeg"), (b"GIF87a", "gif"), (b"GIF89a", "gif"))
USER_AGENT = {"User-Agent": "DiscordBot (https://github.com/lebashaca-cmd/Risk, 1.0)"}
SNOWFLAKE = re.compile(r"\d{15,21}")


# What each section needs from other cogs. A missing or outdated file disables only that section.
REQUIREMENTS = {
    "general": [],
    "welcome": [("Welcome", "welcome.py", ["config.data", "config.save"])],
    "logs": [("ServerLogs", "serverlogs.py", ["config", "_save"]), ("LogTools", "log_tools.py", ["cfg", "store.save"])],
    "levels": [("Levels", "levels.py", ["cfg", "settings.save"])],
    "automod": [("AutoMod", "automod.py", ["cfg", "store.save"])],
    "commands": [],
    "responders": [],
    "overview": [],
    "announcements": [("VIP", "vip.py", ["schedules", "is_vip", "limit", "store.save"])],
    "vip": [("VIP", "vip.py", ["info", "limit", "cfg", "store.save"])],
    "community": [
        ("Community", "community.py", ["cfg", "sugg", "settings.save", "suggestions.save"]),
        ("CommunityExtra", "community_extra.py", ["cfg", "store.save"]),
        ("Tickets", "Tickets.py", ["_guild", "_save", "config"]),
    ],
}


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
        self.cooldowns = {}
        self.reply_times = {}

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
        data.setdefault("rules", {})
        data.setdefault("responders", [])
        data.setdefault("activity", [])
        return data

    # VIP lookups that still work when vip.py isn't on the host
    def vip_info(self, guild_id):
        cog = self.bot.get_cog("VIP")
        return cog.info(guild_id) if cog else {"vip": False, "source": None, "until": None, "note": ""}

    def cap(self, guild_id, key):
        free, vip = LIMITS[key]
        return vip if self.vip_info(guild_id)["vip"] else free

    def need_vip(self, guild_id, what):
        if not self.vip_info(guild_id)["vip"]:
            raise ApiError(403, f"{what} is a VIP feature. This server is on the free plan.")

    async def command_allowed(self, ctx):
        if ctx.guild is None or ctx.command is None:
            return True
        config = self.store.data.get(str(ctx.guild.id))
        if not config:
            return True
        root = ctx.command.root_parent or ctx.command
        perms = getattr(ctx.author, "guild_permissions", None)
        staff = bool(perms and (perms.administrator or perms.manage_guild))
        if staff:
            return True
        if root.name in config.get("disabled_commands", []):
            raise ModError(f"`{root.name}` is turned off in this server.")
        rules = config.get("rules", {})
        rule = rules.get(root.name)
        if rule and root.name in list(rules)[: self.cap(ctx.guild.id, "command_rules")]:
            channels = rule.get("channels", [])
            here = {ctx.channel.id, getattr(ctx.channel, "parent_id", None)}
            if channels and not here & set(channels):
                raise ModError(f"`{root.name}` only works in " + ", ".join(f"<#{c}>" for c in channels[:5]) + ".")
            roles = rule.get("roles", [])
            if roles and not {r.id for r in getattr(ctx.author, "roles", [])} & set(roles):
                raise ModError(f"`{root.name}` is limited to certain roles in this server.")
            cooldown = rule.get("cooldown", 0)
            if cooldown:
                key, now = (ctx.guild.id, root.name, ctx.author.id), time.time()
                wait = self.cooldowns.get(key, 0) + cooldown - now
                if wait > 0:
                    raise ModError(f"`{root.name}` is on cooldown here. Try again in {int(wait) + 1}s.")
                if len(self.cooldowns) > 5000:
                    self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now - 3600}
                self.cooldowns[key] = now
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        guild = message.guild
        if guild is None or message.author.bot or not message.content:
            return
        config = self.store.data.get(str(guild.id))
        if not config or not config.get("responders") or message.channel.id in config.get("ignored_channels", []):
            return
        if not isinstance(message.channel, (discord.TextChannel, discord.Thread)) or not message.channel.permissions_for(guild.me).send_messages:
            return
        text = message.content.lower().strip()
        now = time.time()
        for index, item in enumerate(config["responders"][: self.cap(guild.id, "responders")]):
            trigger, mode = item["trigger"].lower(), item.get("match", "contains")
            hit = text == trigger if mode == "exact" else text.startswith(trigger) if mode == "starts" else trigger in text
            key = (guild.id, index, item["trigger"])
            if not hit or self.reply_times.get(key, 0) + 10 > now:
                continue
            self.reply_times[key] = now
            reply = item["reply"].replace("{user}", message.author.display_name).replace("{server}", guild.name)
            kwargs = {"reference": message, "mention_author": False, "allowed_mentions": discord.AllowedMentions.none()}
            try:
                if item.get("embed") and self.vip_info(guild.id)["vip"]:
                    vip = self.bot.get_cog("VIP")
                    color = vip.embed_color(guild.id) if vip else None
                    await message.channel.send(embed=discord.Embed(description=reply, color=color if color is not None else discord.Color.dark_grey()), **kwargs)
                else:
                    await message.channel.send(reply, **kwargs)
            except discord.HTTPException:
                pass
            break

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
            "vip": self.vip_info(guild.id)["vip"],
            "limits": {key: self.cap(guild.id, key) for key in LIMITS},
        }

    def unavailable(self, section):
        """A message if a cog this section depends on is missing or out of date, else None."""
        for cog_name, filename, attributes in REQUIREMENTS[section]:
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                return f"{filename} isn't loaded on the bot host. Upload the latest bot files and restart the bot."
            for path in attributes:
                target = cog
                for part in path.split("."):
                    target = getattr(target, part, None)
                    if target is None:
                        return f"{filename} on the bot host is out of date. Upload the latest bot files and restart the bot."
        if section == "logs" and not LOG_CATEGORIES:
            return "log_tools.py on the bot host is out of date. Upload the latest bot files and restart the bot."
        return None

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
            ignored = pick_channels(guild, body["ignoredChannels"], "Ignored channels")
            if len(ignored) > self.cap(guild.id, "ignored_channels"):
                raise ApiError(403, f"Free servers can ignore {LIMITS['ignored_channels'][0]} channels. VIP raises that to {LIMITS['ignored_channels'][1]}.")
            config["ignored_channels"] = ignored
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
            multiplier = as_float(body["multiplier"], "XP multiplier", 0.5, 5)
            if multiplier > self.cap(guild.id, "xp_multiplier") and multiplier != config["multiplier"]:
                raise ApiError(403, f"Free servers can set the XP multiplier up to {LIMITS['xp_multiplier'][0]:g}x. VIP goes up to {LIMITS['xp_multiplier'][1]:g}x.")
            config["multiplier"] = multiplier
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
            allowed = self.cap(guild.id, "level_rewards")
            for item in as_list(body["rewards"], "Level rewards", LIMITS["level_rewards"][1]):
                if not isinstance(item, dict):
                    raise ApiError(400, "Each reward needs a level and a role.")
                level = as_int(item.get("level"), "Reward level", 1, 1000)
                role = pick_role(guild, item.get("role"), "Reward role", assignable=True)
                if role is None:
                    raise ApiError(400, "Pick a role for each reward.")
                rewards[str(level)] = role
            if len(rewards) > allowed:
                raise ApiError(403, f"Free servers can have {LIMITS['level_rewards'][0]} level rewards. VIP allows {LIMITS['level_rewards'][1]}.")
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
            for word in as_list(body["badWords"], "Blocked words", LIMITS["badwords"][1]):
                word = as_text(word, "A blocked word", 40).lower()
                if not 2 <= len(word) <= 40:
                    raise ApiError(400, "Each blocked word needs 2 to 40 characters.")
                if word not in words:
                    words.append(word)
            if len(words) > self.cap(guild.id, "badwords"):
                raise ApiError(403, f"Free servers can block {LIMITS['badwords'][0]} words. VIP allows {LIMITS['badwords'][1]}.")
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

    # Commands: per-command rules (who can use it, where, and how often)
    def read_commands(self, guild):
        config = self.cfg(guild.id)
        rules = [
            {"command": name, "roles": [str(r) for r in rule.get("roles", [])], "channels": [str(c) for c in rule.get("channels", [])], "cooldown": rule.get("cooldown", 0)}
            for name, rule in config["rules"].items()
        ]
        return {"rules": rules}

    def write_commands(self, guild, body):
        valid = {c.name for c in self.bot.commands}
        rules = {}
        for item in as_list(body.get("rules", []), "Command rules", LIMITS["command_rules"][1]):
            if not isinstance(item, dict):
                raise ApiError(400, "Each rule needs a command.")
            name = item.get("command")
            if name not in valid or name == "dashboard":
                raise ApiError(400, f"`{str(name)[:30]}` isn't a command that can have rules.")
            if name in rules:
                raise ApiError(400, f"`{name}` has two rules. Combine them into one.")
            rule = {
                "roles": pick_roles(guild, item.get("roles", []), "Allowed roles", 20),
                "channels": pick_channels(guild, item.get("channels", []), "Allowed channels", 20),
                "cooldown": as_int(item.get("cooldown", 0), "Cooldown", 0, 3600),
            }
            if rule["roles"] or rule["channels"] or rule["cooldown"]:
                rules[name] = rule
        if len(rules) > self.cap(guild.id, "command_rules"):
            raise ApiError(403, f"Free servers can have rules for {LIMITS['command_rules'][0]} commands. VIP allows {LIMITS['command_rules'][1]}.")
        self.cfg(guild.id)["rules"] = rules
        self.store.save()

    # Auto-replies
    def read_responders(self, guild):
        return {"items": [dict(item) for item in self.cfg(guild.id)["responders"]]}

    def write_responders(self, guild, body):
        items = []
        for item in as_list(body.get("items", []), "Auto-replies", LIMITS["responders"][1]):
            if not isinstance(item, dict):
                raise ApiError(400, "Each auto-reply needs a trigger and a reply.")
            trigger = as_text(item.get("trigger"), "Trigger", 60, required=True)
            reply = as_text(item.get("reply"), "Reply", 500, required=True)
            match = item.get("match", "contains")
            if match not in ("contains", "exact", "starts"):
                raise ApiError(400, "Match must be contains, exact or starts.")
            embed = as_bool(item.get("embed", False), "Embed")
            if embed:
                self.need_vip(guild.id, "Sending an auto-reply as an embed")
            if any(i["trigger"].lower() == trigger.lower() for i in items):
                raise ApiError(400, f"There are two auto-replies for \"{trigger[:30]}\".")
            items.append({"trigger": trigger, "reply": reply, "match": match, "embed": embed})
        if len(items) > self.cap(guild.id, "responders"):
            raise ApiError(403, f"Free servers can have {LIMITS['responders'][0]} auto-replies. VIP allows {LIMITS['responders'][1]}.")
        self.cfg(guild.id)["responders"] = items
        self.store.save()

    # Announcements (VIP): messages Risk repeats on a timer
    def read_announcements(self, guild):
        cog = self.bot.get_cog("VIP")
        items = [
            {"id": i["id"], "channel": str(i["channel"]), "everyMinutes": i["every"] // 60, "text": i["text"], "on": i.get("on", True)}
            for i in cog.schedules(guild.id)
        ]
        return {"items": items, "locked": not cog.is_vip(guild.id)}

    def write_announcements(self, guild, body):
        cog = self.bot.get_cog("VIP")
        self.need_vip(guild.id, "Scheduled announcements")
        old = {i["id"]: i for i in cog.schedules(guild.id)}
        items, used = [], set()
        for item in as_list(body.get("items", []), "Announcements", LIMITS["schedules"][1]):
            if not isinstance(item, dict):
                raise ApiError(400, "Each announcement needs a channel, a time and a message.")
            channel = pick_channel(guild, item.get("channel"), "Announcement channel")
            if channel is None:
                raise ApiError(400, "Pick a channel for each announcement.")
            minutes = as_int(item.get("everyMinutes"), "Repeat time", 5, 43200)
            text = as_text(item.get("text"), "Announcement", 1500, required=True)
            number = item.get("id")
            previous = old.get(number) if isinstance(number, int) and not isinstance(number, bool) else None
            if previous is None or number in used:
                number = max([*old, *used, 0]) + 1
                previous = None
            used.add(number)
            due = previous["next"] if previous and previous["every"] == minutes * 60 else time.time() + minutes * 60
            items.append({"id": number, "channel": channel, "every": minutes * 60, "text": text, "next": due, "on": as_bool(item.get("on", True), "On")})
        if len(items) > self.cap(guild.id, "schedules"):
            raise ApiError(403, f"VIP servers can have {LIMITS['schedules'][1]} announcements.")
        cog.store.data["schedules"][str(guild.id)] = items
        cog.store.save()

    # VIP status and options
    def read_vip(self, guild):
        info = self.vip_info(guild.id)
        cog = self.bot.get_cog("VIP")
        color = cog.cfg(guild.id).get("color") if cog else None
        return {
            "active": info["vip"], "source": info["source"], "until": info["until"],
            "color": f"#{color:06x}" if isinstance(color, int) else None,
            "perks": list(PERKS),
            "free": {key: low for key, (low, _) in LIMITS.items()},
            "vipLimits": {key: high for key, (_, high) in LIMITS.items()},
            "url": os.getenv("VIP_URL", "").strip() if os.getenv("VIP_URL", "").startswith("https://") else None,
        }

    def write_vip(self, guild, body):
        cog = self.bot.get_cog("VIP")
        if "color" in body:
            value = body["color"]
            if value in (None, ""):
                cog.cfg(guild.id).pop("color", None)
            else:
                self.need_vip(guild.id, "A custom colour")
                text = as_text(value, "Colour", 7).lstrip("#")
                if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
                    raise ApiError(400, "The colour must be a hex value like #5865f2.")
                cog.cfg(guild.id)["color"] = int(text, 16)
        cog.store.save()

    # Overview: read-only numbers, a setup checklist and recent changes
    def read_overview(self, guild):
        humans = sum(1 for m in guild.members if not m.bot)
        config = self.cfg(guild.id)
        values = {}
        for name in ("welcome", "logs", "levels", "automod", "community"):
            if self.unavailable(name) is None:
                try:
                    values[name] = getattr(self, f"read_{name}")(guild)
                except Exception:
                    pass
        w, lg, lv, am, cm = (values.get(k) for k in ("welcome", "logs", "levels", "automod", "community"))
        checklist = [
            ("welcome", "Greet new members", "welcome", bool(w and w["enabled"])),
            ("logs", "Pick a log channel", "logs", bool(lg and lg["channel"])),
            ("automod", "Turn on an auto-moderation rule", "automod", bool(am and (am["antilink"] or am["antiinvite"] or am["antispam"] or am["badWords"]))),
            ("levels", "Set up level rewards", "levels", bool(lv and lv["rewards"])),
            ("autorole", "Give new members a role", "community", bool(cm and cm["autorole"])),
            ("tickets", "Choose a ticket log channel", "community", bool(cm and cm["ticketLogChannel"])),
            ("replies", "Add an auto-reply", "responders", bool(config["responders"])),
            ("rules", "Set a command rule", "commands", bool(config["rules"])),
        ]
        vip = self.bot.get_cog("VIP")
        schedules = len(vip.schedules(guild.id)) if vip else 0
        return {
            "stats": {
                "members": guild.member_count, "people": humans, "bots": (guild.member_count or 0) - humans,
                "textChannels": len(guild.text_channels), "voiceChannels": len(guild.voice_channels), "roles": max(len(guild.roles) - 1, 0),
                "emojis": len(guild.emojis), "boostTier": guild.premium_tier, "boosts": guild.premium_subscription_count or 0,
                "created": int(guild.created_at.timestamp()), "owner": guild.owner.display_name if guild.owner else None,
            },
            "checklist": [{"id": a, "label": b, "section": c, "done": d} for a, b, c, d in checklist],
            "usage": {
                "disabledCommands": len(config["disabled_commands"]), "commandRules": len(config["rules"]),
                "responders": len(config["responders"]), "announcements": schedules,
                "logCategories": len(LOG_CATEGORIES) - len(lg["disabled"]) if lg else None,
            },
            "activity": list(reversed(config["activity"][-10:])),
            "vip": self.vip_info(guild.id)["vip"],
        }

    def record(self, guild, member, section):
        activity = self.cfg(guild.id)["activity"]
        activity.append({"user": str(getattr(member, "display_name", "") or member.id)[:40], "section": section, "at": int(time.time())})
        del activity[:-30]
        self.store.save()

    # The bot's own profile in one server: nickname, avatar, banner and bio (Discord keeps these per server)
    def read_profile(self, guild):
        me = guild.me
        cfg = self.cfg(guild.id)
        avatar = getattr(me, "guild_avatar", None)
        banner = getattr(me, "guild_banner", None)
        return {
            "nick": me.nick or "",
            "bio": cfg.get("bio", ""),
            "avatar": avatar.replace(size=256).url if avatar else None,
            "banner": banner.replace(size=512).url if banner else None,
            "botName": self.bot.user.name if self.bot.user else "Risk",
            "defaultAvatar": self.bot.user.display_avatar.replace(size=256).url if self.bot.user else None,
        }

    @staticmethod
    def decode_image(value, name):
        """Bytes from a data URL, after checking the size and the file's real type."""
        if not isinstance(value, str) or not value.startswith("data:image/") or ";base64," not in value:
            raise ApiError(400, f"The {name} must be a PNG, JPG or GIF image.")
        try:
            raw = base64.b64decode(value.split(";base64,", 1)[1], validate=True)
        except (binascii.Error, ValueError):
            raise ApiError(400, f"The {name} image couldn't be read.")
        if len(raw) > IMAGE_LIMITS[name]:
            raise ApiError(400, f"The {name} must be under {IMAGE_LIMITS[name] // 1_000_000} MB.")
        if not any(raw.startswith(sig) for sig, _ in IMAGE_SIGNATURES):
            raise ApiError(400, f"The {name} must be a PNG, JPG or GIF image.")
        return raw

    async def write_profile(self, guild, body):
        changes = {}
        if "nick" in body:
            nick = as_text(body["nick"], "Nickname", 32)
            changes["nick"] = nick or None
        if "bio" in body:
            changes["bio"] = as_text(body["bio"], "Bio", 190)
        for name in ("avatar", "banner"):
            if name in body:
                changes[name] = None if body[name] is None else self.decode_image(body[name], name)
        if not changes:
            raise ApiError(400, "Nothing to change.")
        edits = dict(changes)
        if "bio" in edits:
            edits["bio"] = edits["bio"] or None
        try:
            await guild.me.edit(**edits, reason="Changed on the Risk dashboard")
        except discord.Forbidden:
            raise ApiError(403, "Discord says I'm not allowed to change my profile here. Give Risk the Change Nickname permission and try again.")
        except discord.HTTPException as error:
            if error.status == 429:
                raise ApiError(429, "Discord limits how often a profile can change. Wait a few minutes and try again.")
            raise ApiError(400, f"Discord refused the change: {str(getattr(error, 'text', '') or error)[:150]}")
        if "bio" in changes:
            self.cfg(guild.id)["bio"] = changes["bio"]
            self.store.save()

    # HTTP entry point (routed from main.py)
    def check_key(self, request):
        expected = os.getenv("DASHBOARD_KEY", "")
        if len(expected) < 16:
            raise ApiError(503, "The dashboard isn't enabled on the bot.")
        given = request.headers.get("X-Dashboard-Key", "")
        if not hmac.compare_digest(given.encode(), expected.encode()):
            raise ApiError(401, "Bad dashboard key.")

    async def read_json(self, request, limit=MAX_BODY):
        raw = await request.content.read(limit + 1)
        if len(raw) > limit:
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
            settings, missing = {}, {}
            for name in (*READ_ONLY, *SECTIONS):
                reason = self.unavailable(name)
                if reason is None:
                    try:
                        settings[name] = getattr(self, f"read_{name}")(guild)
                    except Exception as error:
                        print(f"[dashboard] Couldn't read the {name} settings: {type(error).__name__}: {str(error)[:200]}", flush=True)
                        reason = "These settings couldn't be read. Check the bot's console for details."
                if reason is not None:
                    missing[name] = reason
            return {"guild": self.guild_card(guild), "meta": self.meta(guild), "settings": settings, "unavailable": missing, "profile": self.read_profile(guild)}
        if len(parts) == 3 and method == "PUT" and parts[2] == "profile":
            body = await self.read_json(request, MAX_PROFILE_BODY)
            await self.write_profile(guild, body)
            self.record(guild, member, "profile")
            await self.audit(guild, member, "profile")
            return {"profile": self.read_profile(guild)}
        if len(parts) == 3 and method == "PUT" and parts[2] in SECTIONS:
            body = await self.read_json(request)
            await self.apply(guild, parts[2], body)
            self.record(guild, member, parts[2])
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
        if section in ("general", "commands", "responders"):
            return [self.store.data]
        if section in ("announcements", "vip"):
            return [cog("VIP").store.data, self.store.data]
        if section == "welcome":
            return [cog("Welcome").config.data]
        if section == "logs":
            return [cog("ServerLogs").config, cog("LogTools").store.data]
        if section == "levels":
            return [cog("Levels").settings.data]
        if section == "automod":
            return [cog("AutoMod").store.data]
        return [cog("Community").settings.data, cog("Community").suggestions.data, cog("CommunityExtra").store.data, cog("Tickets").config]

    async def apply(self, guild, section, body):
        reason = self.unavailable(section)
        if reason is not None:
            raise ApiError(503, reason)
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
