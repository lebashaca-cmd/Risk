"""Game servers: track who is online, watch a server, and manage it from Discord.

`!gameserver add` saves a server (Minecraft Java or Bedrock, any Steam/Source game such as CS2, Rust, ARK, Garry's Mod or
Valheim, or Terraria with TShock). Risk checks each one every minute, remembers who joined and left, and can post a feed.
Servers with RCON can be managed from chat, and a Pterodactyl panel adds restart and world reset.
Also here: `!fortnite` player stats (needs FORTNITE_API_KEY).
"""
import asyncio
import os
import re
import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

from utils import gamenet
from utils.gamenet import GameError
from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

GAMES = {
    "minecraft": ("Minecraft (Java)", 25565),
    "bedrock": ("Minecraft (Bedrock)", 19132),
    "source": ("Steam game (CS2, Rust, ARK, Garry's Mod, Valheim...)", 27015),
    "terraria": ("Terraria (TShock)", 7878),
}
ALIASES = {"java": "minecraft", "mc": "minecraft", "mcpe": "bedrock", "steam": "source", "cs2": "source", "csgo": "source", "rust": "source", "ark": "source",
           "gmod": "source", "valheim": "source", "tf2": "source", "tshock": "terraria"}
NAME_RE = re.compile(r"^[a-z0-9_-]{1,20}$")
MAX_SERVERS = 10
MAX_TRACKED = 2000
SECRETS = ("rcon_password", "token", "panel_key")


def game_key(text):
    key = ALIASES.get(text.lower(), text.lower())
    if key not in GAMES:
        raise ModError("The game must be one of: " + ", ".join(f"`{k}`" for k in GAMES) + ". (`cs2`, `rust`, `ark`, `gmod`, `valheim` and `tf2` count as `source`.)")
    return key


def duration(seconds):
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [f"{days}d" if days else "", f"{hours}h" if hours else "", f"{minutes}m" if minutes or not (days or hours) else ""]
    return " ".join(p for p in parts if p)


class Games(commands.Cog, name="Games"):
    """Game server tracking and management, and Fortnite stats."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("games")
        for key in ("servers", "feed", "players", "state"):
            self.store.data.setdefault(key, {})
        self.busy = set()

    async def cog_load(self):
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, GameError):
            await ctx.reply(str(error), mention_author=False)
            return
        if not await explain_error(ctx, error):
            raise error

    # ------------------------------------------------------------------ helpers
    def servers(self, guild_id):
        return self.store.data["servers"].setdefault(str(guild_id), {})

    def server(self, guild_id, name=None):
        servers = self.servers(guild_id)
        if not servers:
            raise ModError("This server has no game servers yet. Add one with `!gameserver add <name> <game> <address>`.")
        if name is None:
            if len(servers) > 1:
                raise ModError("Which one? " + ", ".join(f"`{n}`" for n in servers))
            name = next(iter(servers))
        name = name.lower()
        if name not in servers:
            raise ModError(f"There is no game server called `{name}`. You have: " + ", ".join(f"`{n}`" for n in servers))
        return name, servers[name]

    def state(self, guild_id, name):
        return self.store.data["state"].get(str(guild_id), {}).get(name, {})

    def forget(self, guild_id, name):
        self.store.data["state"].get(str(guild_id), {}).pop(name, None)
        self.store.data["players"].get(str(guild_id), {}).pop(name, None)

    def new_server(self, game, host, port):
        return {"game": game, "host": host, "port": port, "track": True}

    @staticmethod
    def hide(cfg):
        return {k: v for k, v in cfg.items() if k not in SECRETS}

    async def fresh(self, guild_id, name, cfg):
        """Asks the server right now and keeps the answer, so !status is never stale."""
        status = await gamenet.check(cfg)
        status["checked"] = int(time.time())
        self.apply(guild_id, name, cfg, status)
        return status

    # ------------------------------------------------------------------ the one-minute check
    def apply(self, guild_id, name, cfg, status):
        """Stores a status and works out who joined and left. Returns lines for the feed."""
        gid = str(guild_id)
        previous = self.store.data["state"].setdefault(gid, {}).get(name, {})
        now = int(time.time())
        lines = []
        was_online = previous.get("online")
        if was_online is not None and was_online != status["online"]:
            lines.append(("\U0001F7E2 **%s** is online." if status["online"] else "\U0001F534 **%s** went offline.") % name)
        if cfg.get("track", True):
            roster = self.store.data["players"].setdefault(gid, {}).setdefault(name, {})
            before = set(previous.get("players", []))
            here = set(status.get("players", []))
            complete = status.get("complete", False) or not status["online"]
            if previous:  # the first check only records who is already there
                for player in sorted(here - before):
                    lines.append(f"➡️ **{player}** joined **{name}**.")
                if complete:
                    for player in sorted(before - here):
                        lines.append(f"⬅️ **{player}** left **{name}**.")
            for player in here:
                entry = roster.setdefault(player.lower(), {"name": player, "first": now, "seconds": 0, "since": None})
                entry["name"], entry["last"] = player, now
                if entry["since"] is None:
                    entry["since"] = now
            if complete:
                for key, entry in roster.items():
                    if entry["since"] is not None and entry["name"] not in here:
                        entry["seconds"] += max(0, now - entry["since"])
                        entry["since"] = None
            if len(roster) > MAX_TRACKED:
                for key in sorted(roster, key=lambda k: roster[k].get("last", 0))[:len(roster) - MAX_TRACKED]:
                    roster.pop(key)
        keep = {k: status.get(k) for k in ("online", "count", "max", "players", "complete", "version", "motd", "latency", "map", "error", "checked")}
        self.store.data["state"][gid][name] = keep
        return lines

    @tasks.loop(seconds=60)
    async def poll(self):
        jobs = []
        for gid, servers in list(self.store.data["servers"].items()):
            if self.bot.get_guild(int(gid)) is None:
                continue
            for name, cfg in list(servers.items()):
                jobs.append((gid, name, cfg))
        gate = asyncio.Semaphore(8)

        async def one(gid, name, cfg):
            async with gate:
                status = await gamenet.check(cfg)
                status["checked"] = int(time.time())
                return gid, name, self.apply(gid, name, cfg, status)

        feed = {}
        for result in await asyncio.gather(*(one(*job) for job in jobs), return_exceptions=True):
            if isinstance(result, Exception):
                continue
            gid, name, lines = result
            feed.setdefault(gid, []).extend(lines)
        if jobs:
            self.store.save()
        for gid, lines in feed.items():
            channel = self.bot.get_channel(self.store.data["feed"].get(gid) or 0)
            if channel is None or not lines:
                continue
            try:
                await channel.send("\n".join(lines)[:1900], allowed_mentions=NO_MENTIONS)
            except discord.HTTPException:
                pass

    @poll.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ commands: overview and setup
    @commands.group(name="gameserver", aliases=["gs", "games"], invoke_without_command=True)
    @commands.guild_only()
    async def gameserver(self, ctx):
        """Game servers: track who is online and manage the server from Discord. Works with Minecraft (Java and Bedrock), Steam games like CS2, Rust and ARK, and Terraria. Usage: !gameserver add | status | players | seen | top | list"""
        lines = [f"`{ctx.clean_prefix}gameserver add <name> <game> <address>`: save a server. Games: " + ", ".join(f"`{k}`" for k in GAMES),
                 "`status`, `players`, `seen <player>`, `top`, `map`, `skin <player>`, `list`: look at it",
                 "`feed #channel`: post joins, leaves and downtime. `set`: RCON, query port, map link, panel",
                 "`run`, `say`, `kick`, `whitelist`, `save`, `restart`, `reset`: manage it (Manage Server)",
                 f"`{ctx.clean_prefix}fortnite <name>`: Fortnite stats"]
        await ctx.reply(embed=discord.Embed(title="Game servers", description="\n".join(lines), color=discord.Color.blurple()), mention_author=False)

    @gameserver.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def gs_add(self, ctx, name: str, game: str, address: str):
        """Saves a game server. Usage: !gameserver add survival minecraft play.example.com:25565 (games: minecraft, bedrock, source, terraria)"""
        name, key = name.lower(), game_key(game)
        if not NAME_RE.match(name):
            raise ModError("A name is 1 to 20 letters, numbers, `_` or `-`.")
        servers = self.servers(ctx.guild.id)
        if name in servers:
            raise ModError("You already have a game server with that name.")
        if len(servers) >= MAX_SERVERS:
            raise ModError(f"A server can save up to {MAX_SERVERS} game servers.")
        host, port = gamenet.parse_address(address, GAMES[key][1])
        await gamenet.ensure_public(host)
        servers[name] = self.new_server(key, host, port)
        async with ctx.typing():
            status = await self.fresh(ctx.guild.id, name, servers[name])
        self.store.save()
        hint = "It answered, so it is online." if status["online"] else f"It didn't answer yet: {status.get('error')} It's saved anyway."
        extra = ""
        if key == "minecraft":
            extra = f"\nTip: for the full player list, turn on `enable-query=true` in server.properties and run `{ctx.clean_prefix}gameserver set {name} query_port {port}`. For RCON use `rcon_port` and `rcon_password`."
        if key == "terraria":
            extra = f"\nTerraria needs the TShock REST token: `{ctx.clean_prefix}gameserver set {name} token <token>` (better in the dashboard). The address port is the REST port (7878)."
        await ctx.reply(f"Saved **{name}** ({GAMES[key][0]}) at `{host}:{port}`. {hint}{extra}", mention_author=False)

    @gameserver.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def gs_remove(self, ctx, name: str):
        """Forgets a game server and its player history. Usage: !gameserver remove survival"""
        name, _ = self.server(ctx.guild.id, name)
        del self.servers(ctx.guild.id)[name]
        self.forget(ctx.guild.id, name)
        self.store.save()
        await ctx.reply(f"Removed **{name}**.", mention_author=False)

    @gameserver.command(name="list")
    async def gs_list(self, ctx):
        """Lists the saved game servers and whether they are up. Usage: !gameserver list"""
        servers = self.servers(ctx.guild.id)
        if not servers:
            raise ModError("No game servers yet. Add one with `!gameserver add <name> <game> <address>`.")
        rows = []
        for name, cfg in servers.items():
            s = self.state(ctx.guild.id, name)
            mark = "\U0001F7E2" if s.get("online") else "\U0001F534" if s else "⚪"
            rows.append(f"{mark} **{name}**: {GAMES[cfg['game']][0]}, `{cfg['host']}:{cfg['port']}`" + (f", {s.get('count', 0)}/{s.get('max', 0)} online" if s.get("online") else ""))
        await ctx.reply("\n".join(rows), mention_author=False)

    @gameserver.command(name="feed")
    @commands.has_permissions(manage_guild=True)
    async def gs_feed(self, ctx, channel: str):
        """Posts joins, leaves and downtime in a channel. Usage: !gameserver feed #game-feed | off"""
        if channel.lower() == "off":
            self.store.data["feed"].pop(str(ctx.guild.id), None)
            self.store.save()
            await ctx.reply("The feed is off.", mention_author=False)
            return
        target = await commands.TextChannelConverter().convert(ctx, channel)
        if not target.permissions_for(ctx.guild.me).send_messages:
            raise ModError("I can't send messages in that channel.")
        self.store.data["feed"][str(ctx.guild.id)] = target.id
        self.store.save()
        await ctx.reply(f"Joins, leaves and downtime will be posted in {target.mention}. Servers with Query turned on report leaves exactly; others only report joins.", mention_author=False)

    SETTINGS = {
        "query_port": "int", "rcon_port": "int", "rcon_password": "secret", "token": "secret", "map": "url", "panel_url": "url", "panel_key": "secret",
        "panel_id": "text", "track": "bool",
    }

    @gameserver.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def gs_set(self, ctx, name: str, setting: str, *, value: str):
        """Changes one setting: query_port, rcon_port, rcon_password, token, map, panel_url, panel_key, panel_id, track. Use `off` to clear one. Passwords are better set in the dashboard. Usage: !gameserver set survival rcon_port 25575"""
        name, cfg = self.server(ctx.guild.id, name)
        setting = setting.lower()
        if setting not in self.SETTINGS:
            raise ModError("The setting must be one of: " + ", ".join(f"`{s}`" for s in self.SETTINGS) + ".")
        kind, value = self.SETTINGS[setting], value.strip()
        if kind == "secret":
            try:
                await ctx.message.delete()  # don't leave a password sitting in the channel
            except discord.HTTPException:
                pass
        key = {"map": "map_url"}.get(setting, setting)
        if value.lower() == "off":
            cfg.pop(key, None)
            text = f"Cleared `{setting}`."
        elif kind == "int":
            if not value.isdigit() or not 1 <= int(value) <= 65535:
                raise ModError("That needs a port number between 1 and 65535.")
            cfg[key] = int(value)
            text = f"`{setting}` set to {value}."
        elif kind == "bool":
            cfg[key] = value.lower() in ("on", "true", "yes", "1")
            text = f"Tracking joins and leaves is **{'on' if cfg[key] else 'off'}**."
        elif kind == "url":
            if not re.fullmatch(r"https?://[^\s]{4,200}", value):
                raise ModError("That needs a full link starting with http:// or https://.")
            cfg[key] = value
            text = f"`{setting}` saved."
        else:
            cfg[key] = value[:300]
            text = f"`{setting}` saved." + (" I deleted your message so the secret isn't left in the channel." if kind == "secret" else "")
        self.store.save()
        await ctx.send(text) if kind == "secret" else await ctx.reply(text, mention_author=False)

    # ------------------------------------------------------------------ commands: looking
    @gameserver.command(name="status", aliases=["info"])
    async def gs_status(self, ctx, name: str = None):
        """Shows whether a game server is up, who is on, the version and the ping. Usage: !gameserver status survival"""
        name, cfg = self.server(ctx.guild.id, name)
        async with ctx.typing():
            s = await self.fresh(ctx.guild.id, name, cfg)
        self.store.save()
        if not s["online"]:
            embed = discord.Embed(title=f"\U0001F534 {name} is offline", description=s.get("error", ""), color=discord.Color.red())
        else:
            embed = discord.Embed(title=f"\U0001F7E2 {name} is online", description=(s.get("motd") or "")[:300], color=discord.Color.green())
            embed.add_field(name="Players", value=f"{s['count']}/{s['max']}")
            embed.add_field(name="Version", value=str(s.get("version") or "?")[:40])
            embed.add_field(name="Ping", value=f"{s['latency']} ms")
            if s.get("map"):
                embed.add_field(name="World", value=str(s["map"])[:60])
            if s["players"]:
                shown = ", ".join(s["players"][:30])
                embed.add_field(name="Online now" + ("" if s.get("complete") else " (some)"), value=shown[:1000], inline=False)
        embed.set_footer(text=f"{GAMES[cfg['game']][0]} • {cfg['host']}:{cfg['port']}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @gameserver.command(name="players", aliases=["online"])
    async def gs_players(self, ctx, name: str = None):
        """Lists who is on a game server right now. Usage: !gameserver players survival"""
        name, cfg = self.server(ctx.guild.id, name)
        async with ctx.typing():
            s = await self.fresh(ctx.guild.id, name, cfg)
        self.store.save()
        if not s["online"]:
            raise ModError(f"**{name}** is offline.")
        if not s["players"]:
            note = " (the server doesn't say who)" if s["count"] and cfg["game"] != "terraria" else ""
            await ctx.reply(f"Nobody is on **{name}** right now." if not s["count"] else f"**{s['count']}** online{note}.", mention_author=False)
            return
        roster = self.store.data["players"].get(str(ctx.guild.id), {}).get(name, {})
        lines = []
        for player in sorted(s["players"], key=str.lower):
            since = roster.get(player.lower(), {}).get("since")
            lines.append(f"• **{player}**" + (f" (on for {duration(time.time() - since)})" if since else ""))
        partial = "" if s.get("complete") else f"\n\nThe server only shares some names ({len(s['players'])} of {s['count']}). Turn on Query for the full list: `{ctx.clean_prefix}gameserver set {name} query_port <port>`."
        await ctx.reply(f"**{name}**: {s['count']}/{s['max']}\n" + "\n".join(lines[:40]) + partial, mention_author=False, allowed_mentions=NO_MENTIONS)

    @gameserver.command(name="seen", aliases=["find"])
    async def gs_seen(self, ctx, player: str):
        """Shows whether a player is online and when they were last seen on this server's game servers. Usage: !gameserver seen Steve"""
        key, found = player.lower(), []
        for name in self.servers(ctx.guild.id):
            entry = self.store.data["players"].get(str(ctx.guild.id), {}).get(name, {}).get(key)
            if entry:
                found.append((name, entry))
        if not found:
            raise ModError(f"I haven't seen **{player[:32]}** on any of your game servers. I only know players from the time you added the server.")
        lines = []
        for name, entry in found:
            where = f"online on **{name}** now" if entry["since"] is not None else f"last on **{name}** <t:{entry['last']}:R>"
            lines.append(f"{entry['name']}: {where}. First seen <t:{entry['first']}:D>, total time seen online {duration(entry['seconds'] + (time.time() - entry['since'] if entry['since'] else 0))}.")
        await ctx.reply("\n".join(lines), mention_author=False, allowed_mentions=NO_MENTIONS)

    @gameserver.command(name="top", aliases=["playtime"])
    async def gs_top(self, ctx, name: str = None):
        """Shows who has spent the most time on a game server. Usage: !gameserver top survival"""
        name, _ = self.server(ctx.guild.id, name)
        roster = self.store.data["players"].get(str(ctx.guild.id), {}).get(name, {})
        now = time.time()
        ranked = sorted(((e["seconds"] + (now - e["since"] if e["since"] else 0), e["name"]) for e in roster.values()), reverse=True)[:10]
        if not ranked:
            raise ModError("I haven't tracked anyone on that server yet.")
        await ctx.reply(f"**Most time on {name}** (since tracking began)\n" + "\n".join(f"{i}. **{n}**: {duration(s)}" for i, (s, n) in enumerate(ranked, 1)), mention_author=False, allowed_mentions=NO_MENTIONS)

    @gameserver.command(name="map", aliases=["world"])
    async def gs_map(self, ctx, name: str = None):
        """Shows the world name and the link to the live map (Dynmap or BlueMap) if one is set. Usage: !gameserver map survival"""
        name, cfg = self.server(ctx.guild.id, name)
        s = self.state(ctx.guild.id, name)
        if cfg.get("map_url"):
            await ctx.reply(embed=discord.Embed(title=f"{name}: world map", description=f"[Open the live map]({cfg['map_url']})" + (f"\nWorld: **{s['map']}**" if s.get("map") else ""), color=discord.Color.green()), mention_author=False)
            return
        text = f"World: **{s['map']}**. " if s.get("map") else ""
        raise ModError(f"{text}There is no map link yet. Risk can't draw a world itself, but if your server runs Dynmap or BlueMap, save its link: `{ctx.clean_prefix}gameserver set {name} map https://map.example.com`.")

    @gameserver.command(name="skin")
    async def gs_skin(self, ctx, player: str):
        """Shows a Minecraft player's skin. Usage: !gameserver skin Steve"""
        if not re.fullmatch(r"[A-Za-z0-9_]{1,16}", player):
            raise ModError("Minecraft names are 1 to 16 letters, numbers or `_`.")
        embed = discord.Embed(title=player, color=discord.Color.green())
        embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{player}/128")
        embed.set_image(url=f"https://mc-heads.net/body/{player}/256")
        await ctx.reply(embed=embed, mention_author=False)

    # ------------------------------------------------------------------ commands: managing
    async def rcon(self, cfg, command):
        if cfg["game"] == "terraria":
            if not cfg.get("token"):
                raise ModError("This Terraria server has no REST token yet.")
            data = await gamenet.tshock(cfg["host"], cfg["port"], cfg["token"], "/v2/server/rawcmd", cmd=command)
            return "\n".join(str(x) for x in data.get("response", [])) if isinstance(data.get("response"), list) else str(data.get("response", "Done."))
        if not cfg.get("rcon_port") or not cfg.get("rcon_password"):
            raise ModError("This server has no RCON yet. Turn it on in the game, then save `rcon_port` and `rcon_password` with `!gameserver set` or in the dashboard.")
        async with gamenet.Rcon(cfg["host"], cfg["rcon_port"], cfg["rcon_password"]) as rcon:
            return await rcon.run(command)

    @gameserver.command(name="run", aliases=["rcon", "cmd"])
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.guild)
    async def gs_run(self, ctx, name: str, *, command: str):
        """Runs a console command on the game server through RCON. Usage: !gameserver run survival time set day"""
        name, cfg = self.server(ctx.guild.id, name)
        command = command.strip().lstrip("/")
        if len(command) > 400 or "\n" in command:
            raise ModError("Keep it to one line under 400 characters.")
        async with ctx.typing():
            output = await self.rcon(cfg, command)
        await ctx.reply(f"`{command[:100]}` on **{name}**:\n```\n{(output or 'Done (no output).')[:1700]}\n```", mention_author=False, allowed_mentions=NO_MENTIONS)

    @gameserver.command(name="say", aliases=["broadcast"])
    @commands.has_permissions(manage_guild=True)
    async def gs_say(self, ctx, name: str, *, message: str):
        """Sends a message to everyone in the game. Usage: !gameserver say survival Restarting in 5 minutes"""
        name, cfg = self.server(ctx.guild.id, name)
        if cfg["game"] == "terraria":
            await gamenet.tshock(cfg["host"], cfg["port"], cfg.get("token", ""), "/v2/server/broadcast", msg=message[:200])
        else:
            await self.rcon(cfg, f"say {message[:200]}")
        await ctx.reply(f"Sent to **{name}**.", mention_author=False)

    @gameserver.command(name="kick")
    @commands.has_permissions(manage_guild=True)
    async def gs_kick(self, ctx, name: str, player: str, *, reason: str = "Kicked from Discord"):
        """Kicks a player from the game server. Usage: !gameserver kick survival Steve griefing"""
        name, cfg = self.server(ctx.guild.id, name)
        if not re.fullmatch(r"[A-Za-z0-9_ .-]{1,32}", player):
            raise ModError("That isn't a valid player name.")
        text = await self.rcon(cfg, f"/kick {player}" if cfg["game"] == "terraria" else f"kick {player} {reason[:100]}")
        await ctx.reply(f"Kick sent for **{player}**." + (f"\n```\n{text[:500]}\n```" if text else ""), mention_author=False, allowed_mentions=NO_MENTIONS)

    @gameserver.command(name="whitelist")
    @commands.has_permissions(manage_guild=True)
    async def gs_whitelist(self, ctx, name: str, action: str, player: str = ""):
        """Minecraft whitelist. Usage: !gameserver whitelist survival add Steve | remove Steve | list"""
        name, cfg = self.server(ctx.guild.id, name)
        if cfg["game"] not in ("minecraft", "source"):
            raise ModError("That is only for Minecraft Java servers.")
        action = action.lower()
        if action not in ("add", "remove", "list"):
            raise ModError("Use `add`, `remove` or `list`.")
        if action != "list" and not re.fullmatch(r"[A-Za-z0-9_]{1,16}", player):
            raise ModError("Give a Minecraft name (1 to 16 letters, numbers or `_`).")
        text = await self.rcon(cfg, "whitelist list" if action == "list" else f"whitelist {action} {player}")
        await ctx.reply(f"```\n{text[:1500] or 'Done.'}\n```", mention_author=False)

    @gameserver.command(name="save")
    @commands.has_permissions(manage_guild=True)
    async def gs_save(self, ctx, name: str):
        """Saves the world to disk. Usage: !gameserver save survival"""
        name, cfg = self.server(ctx.guild.id, name)
        text = await self.rcon(cfg, "/save" if cfg["game"] == "terraria" else "save-all")
        await ctx.reply(f"Saving **{name}**." + (f"\n```\n{text[:300]}\n```" if text else ""), mention_author=False)

    def panel_ready(self, cfg):
        return all(cfg.get(k) for k in ("panel_url", "panel_key", "panel_id"))

    @gameserver.command(name="restart")
    @commands.has_permissions(manage_guild=True)
    async def gs_restart(self, ctx, name: str, confirm: str = ""):
        """Restarts the game server. With a panel it restarts properly; otherwise it stops the server over RCON and your host has to start it again. Usage: !gameserver restart survival confirm"""
        name, cfg = self.server(ctx.guild.id, name)
        if confirm.lower() != "confirm":
            raise ModError(f"This kicks everyone for a moment. Run `{ctx.clean_prefix}gameserver restart {name} confirm` to do it.")
        if self.panel_ready(cfg):
            await gamenet.panel(cfg["panel_url"], cfg["panel_key"], cfg["panel_id"], "POST", "/power", {"signal": "restart"})
            await ctx.reply(f"Restart sent to the panel for **{name}**.", mention_author=False)
            return
        await self.rcon(cfg, "/exit" if cfg["game"] == "terraria" else "stop")
        await ctx.reply(f"**{name}** was told to stop. Without a panel I can't start it again, so it only comes back if your host restarts it automatically.", mention_author=False)

    @gameserver.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def gs_reset(self, ctx, name: str, confirm: str = ""):
        """Resets a Minecraft world: stops the server, deletes the world folders and starts it again. Needs the Pterodactyl panel settings. This cannot be undone. Usage: !gameserver reset survival reset-survival"""
        name, cfg = self.server(ctx.guild.id, name)
        if cfg["game"] != "minecraft":
            raise ModError("World reset is only for Minecraft Java servers.")
        if not self.panel_ready(cfg):
            raise ModError(f"A reset needs file access, so it needs your Pterodactyl panel: `panel_url`, `panel_key` (a client API key) and `panel_id` (the server's id) in the dashboard or with `{ctx.clean_prefix}gameserver set`.")
        level = re.sub(r"[^A-Za-z0-9_.-]", "", str(self.state(ctx.guild.id, name).get("map") or "world")) or "world"
        phrase = f"reset-{name}"
        if confirm != phrase:
            raise ModError(f"**This deletes the world `{level}` (and `{level}_nether`, `{level}_the_end`) on **{name}** forever.** Make a backup first. To go ahead, run `{ctx.clean_prefix}gameserver reset {name} {phrase}`.")
        if ctx.guild.id in self.busy:
            raise ModError("A reset is already running.")
        self.busy.add(ctx.guild.id)
        try:
            message = await ctx.reply(f"Stopping **{name}**...", mention_author=False)
            args = (cfg["panel_url"], cfg["panel_key"], cfg["panel_id"])
            await gamenet.panel(*args, "POST", "/power", {"signal": "stop"})
            await asyncio.sleep(15)
            await message.edit(content=f"Deleting the world `{level}`...")
            await gamenet.panel(*args, "POST", "/files/delete", {"root": "/", "files": [level, f"{level}_nether", f"{level}_the_end"]})
            await gamenet.panel(*args, "POST", "/power", {"signal": "start"})
            await message.edit(content=f"Done. **{name}** is starting with a brand new world. It can take a minute to come back.")
        finally:
            self.busy.discard(ctx.guild.id)

    # ------------------------------------------------------------------ fortnite
    @commands.command(name="fortnite", aliases=["fn"])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def fortnite(self, ctx, name: str, platform: str = "epic"):
        """Shows a player's Fortnite Battle Royale stats: wins, kills, K/D and more. Usage: !fortnite Ninja | !fortnite SomeName psn"""
        key = os.getenv("FORTNITE_API_KEY", "").strip()
        if not key:
            raise ModError("Fortnite stats aren't set up on this bot yet. The owner needs a free API key from dash.fortnite-api.com in `FORTNITE_API_KEY`.")
        kind = {"epic": "epic", "pc": "epic", "psn": "psn", "playstation": "psn", "ps": "psn", "xbl": "xbl", "xbox": "xbl"}.get(platform.lower())
        if kind is None:
            raise ModError("The platform is `epic`, `psn` or `xbl`.")
        try:
            async with ctx.typing():
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get("https://fortnite-api.com/v2/stats/br/v2", params={"name": name[:40], "accountType": kind}, headers={"Authorization": key}) as response:
                        data = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise ModError("I couldn't reach the Fortnite stats service. Try again in a moment.")
        if data.get("status") == 404:
            raise ModError("I couldn't find that player. Check the spelling and the platform (`epic`, `psn`, `xbl`).")
        if data.get("status") == 403:
            raise ModError("That player's stats are private.")
        if data.get("status") != 200 or not data.get("data"):
            raise ModError("The stats service didn't give me anything for that player.")
        info = data["data"]
        overall = (info.get("stats", {}).get("all") or {}).get("overall") or {}
        embed = discord.Embed(title=f"{info['account']['name']}: Fortnite", color=discord.Color.purple())
        for label, field in (("Wins", "wins"), ("Kills", "kills"), ("K/D", "kd"), ("Win rate", "winRate"), ("Matches", "matches"), ("Top 10", "top10"), ("Deaths", "deaths")):
            value = overall.get(field)
            if value is not None:
                embed.add_field(name=label, value=f"{value:g}" + ("%" if field == "winRate" else "") if isinstance(value, (int, float)) else str(value))
        if overall.get("minutesPlayed"):
            embed.add_field(name="Time played", value=duration(overall["minutesPlayed"] * 60))
        level = (info.get("battlePass") or {}).get("level")
        if level:
            embed.set_footer(text=f"Battle Pass level {level}")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Games(bot))
