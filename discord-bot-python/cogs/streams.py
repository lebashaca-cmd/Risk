"""Stream alerts: Risk says when someone starts and stops streaming.

Sources (all free):
- Discord Go Live (screen share in a voice channel). Works with no extra setup.
- Discord "Streaming" status (a linked Twitch or YouTube account). Needs the Presence intent: turn it on in the
  Developer Portal (Bot, Privileged Gateway Intents) and set STREAM_PRESENCE=1 on the bot host.
- Twitch channels by name (`!twitchadd`). Needs a free Twitch app: set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET.
- TikTok accounts by name (`!tiktokadd`). TikTok has no public API, so this reads the same page data the website uses.
  It needs no keys but is unofficial: TikTok can change it or block a host, and `!tiktoktest` shows what Risk sees.
"""
import asyncio
import os
import re
import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

TWITCH_POLL = 60
MAX_TWITCH = 100
MAX_TIKTOK = 25
TIKTOK_POLL = 90
TIKTOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class Streams(commands.Cog):
    """Stream start and end alerts, who is live, and stream stats."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("streams")
        for key in ("guilds", "stats", "twitch_live", "tiktok_live"):
            self.store.data.setdefault(key, {})
        self.live = {}  # (guild id, user id, source) -> {"start": ts, "title": str}
        self.token = None
        self.token_until = 0
        self.tiktok_seen = {}

    async def cog_load(self):
        self.twitch_loop.start()
        self.tiktok_loop.start()

    def cog_unload(self):
        self.twitch_loop.cancel()
        self.tiktok_loop.cancel()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def cfg(self, guild_id):
        data = self.store.data["guilds"].setdefault(str(guild_id), {})
        data.setdefault("channel", None)
        data.setdefault("role", None)
        data.setdefault("twitch", [])
        data.setdefault("tiktok", [])
        return data

    # Recording and announcing
    def record(self, guild_id, user_key, seconds):
        stats = self.store.data["stats"].setdefault(str(guild_id), {}).setdefault(str(user_key), {"count": 0, "seconds": 0, "longest": 0, "last": 0})
        stats["count"] += 1
        stats["seconds"] += int(seconds)
        stats["longest"] = max(stats["longest"], int(seconds))
        stats["last"] = int(time.time())
        self.store.save()

    async def announce(self, guild, embed, ping=False):
        config = self.cfg(guild.id)
        channel = guild.get_channel(config["channel"]) if config["channel"] else None
        if not isinstance(channel, discord.TextChannel) or not channel.permissions_for(guild.me).send_messages:
            return
        role = guild.get_role(config["role"]) if ping and config["role"] else None
        try:
            if role and role.mentionable:
                await channel.send(role.mention, embed=embed, allowed_mentions=discord.AllowedMentions(roles=[role]))
            else:
                await channel.send(embed=embed, allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            pass

    @staticmethod
    def cover(url):
        """A live cover URL with a changing suffix so Discord doesn't show a stale picture."""
        return f"{url}{'&' if '?' in url else '?'}t={int(time.time() // 60)}" if isinstance(url, str) and url.startswith("https://") else None

    async def started(self, member, source, title, where=None, link=None, image=None):
        key = (member.guild.id, member.id, source)
        if key in self.live:
            return
        self.live[key] = {"start": time.time(), "title": title}
        embed = discord.Embed(title=f"{member.display_name} is live", url=link if isinstance(link, str) and link.startswith("https://") else None, description=(title or "")[:300] or None, color=discord.Color.from_rgb(145, 70, 255))
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="Where", value=where or source)
        if link:
            embed.add_field(name="Watch", value=f"[Open the stream]({link})")
        if self.cover(image):
            embed.set_image(url=self.cover(image))
        await self.announce(member.guild, embed, ping=True)

    async def ended(self, member, source, where=None):
        info = self.live.pop((member.guild.id, member.id, source), None)
        if info is None:
            return
        length = time.time() - info["start"]
        self.record(member.guild.id, member.id, length)
        embed = discord.Embed(title=f"{member.display_name} stopped streaming", description=f"Streamed for **{duration(length)}**.", color=discord.Color.dark_grey())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Where", value=where or source)
        await self.announce(member.guild, embed)

    # Source 1: Discord Go Live
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        was = bool(before.channel and before.self_stream)
        now = bool(after.channel and after.self_stream)
        if now and not was:
            await self.started(member, "Go Live", None, f"Go Live in {after.channel.name}", link=f"https://discord.com/channels/{member.guild.id}/{after.channel.id}")
        elif was and not now:
            await self.ended(member, "Go Live", f"Go Live in {before.channel.name}")

    # Source 2: the Streaming status (needs the Presence intent)
    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        member = after
        if member.bot:
            return
        old = next((a for a in before.activities if isinstance(a, discord.Streaming)), None)
        new = next((a for a in after.activities if isinstance(a, discord.Streaming)), None)
        if new and not old:
            image = None
            match = re.match(r"https://(?:www\.)?twitch\.tv/([A-Za-z0-9_]{3,25})/?$", new.url or "")
            if match:
                image = f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{match.group(1).lower()}-640x360.jpg"
            await self.started(member, new.platform or "Streaming", new.name or None, new.platform or "Streaming", link=new.url, image=image)
        elif old and not new:
            await self.ended(member, old.platform or "Streaming", old.platform or "Streaming")

    # Source 3: Twitch
    @property
    def twitch_ready(self):
        return bool(os.getenv("TWITCH_CLIENT_ID") and os.getenv("TWITCH_CLIENT_SECRET"))

    async def twitch_token(self, session):
        if self.token and self.token_until > time.time() + 60:
            return self.token
        async with session.post("https://id.twitch.tv/oauth2/token", data={
            "client_id": os.getenv("TWITCH_CLIENT_ID"), "client_secret": os.getenv("TWITCH_CLIENT_SECRET"), "grant_type": "client_credentials",
        }) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Twitch token request answered {resp.status}")
            data = await resp.json()
        self.token = data["access_token"]
        self.token_until = time.time() + int(data.get("expires_in", 3600))
        return self.token

    async def twitch_streams(self, logins):
        """{login: stream data} for the channels that are live right now."""
        found = {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            token = await self.twitch_token(session)
            headers = {"Client-Id": os.getenv("TWITCH_CLIENT_ID"), "Authorization": f"Bearer {token}"}
            logins = sorted(logins)
            for i in range(0, len(logins), 100):
                params = [("user_login", name) for name in logins[i:i + 100]]
                async with session.get("https://api.twitch.tv/helix/streams", params=params, headers=headers) as resp:
                    if resp.status == 401:
                        self.token = None
                        raise RuntimeError("Twitch rejected the token")
                    if resp.status != 200:
                        raise RuntimeError(f"Twitch answered {resp.status}")
                    for item in (await resp.json()).get("data", []):
                        found[item["user_login"].lower()] = item
        return found

    def twitch_embed(self, name, item):
        embed = discord.Embed(title=f"{item['user_name']} is live", url=f"https://twitch.tv/{name}", description=item.get("title", "")[:300] or None, color=discord.Color.from_rgb(145, 70, 255))
        embed.set_author(name="Twitch")
        embed.add_field(name="Watch", value=f"[twitch.tv/{name}](https://twitch.tv/{name})")
        if item.get("game_name"):
            embed.add_field(name="Playing", value=item["game_name"])
        embed.add_field(name="Viewers", value=str(item.get("viewer_count", 0)))
        thumb = item.get("thumbnail_url", "").replace("{width}", "640").replace("{height}", "360")
        if self.cover(thumb):
            embed.set_image(url=self.cover(thumb))
        return embed

    async def twitch_check(self):
        wanted = {name for cfg in self.store.data["guilds"].values() for name in cfg.get("twitch", [])}
        if not wanted:
            return
        live = await self.twitch_streams(wanted)
        for gid, cfg in list(self.store.data["guilds"].items()):
            guild = self.bot.get_guild(int(gid))
            if guild is None:
                continue
            state = self.store.data["twitch_live"].setdefault(gid, {})
            for name in cfg.get("twitch", []):
                item = live.get(name)
                if item and name not in state:
                    started = datetime.fromisoformat(item["started_at"].replace("Z", "+00:00")).timestamp()
                    state[name] = {"start": started, "name": item["user_name"]}
                    embed = self.twitch_embed(name, item)
                    await self.announce(guild, embed, ping=True)
                    self.store.save()
                elif not item and name in state:
                    info = state.pop(name)
                    length = time.time() - info["start"]
                    self.record(guild.id, f"twitch:{name}", length)
                    embed = discord.Embed(title=f"{info['name']} went offline on Twitch", url=f"https://twitch.tv/{name}", description=f"Streamed for **{duration(length)}**.", color=discord.Color.dark_grey())
                    await self.announce(guild, embed)
                    self.store.save()

    @tasks.loop(seconds=TWITCH_POLL)
    async def twitch_loop(self):
        if not self.twitch_ready:
            return
        try:
            await self.twitch_check()
        except (RuntimeError, aiohttp.ClientError, KeyError, ValueError) as error:
            print(f"[streams] Twitch check failed: {error}")

    @twitch_loop.before_loop
    async def before_twitch(self):
        await self.bot.wait_until_ready()

    # Source 4: TikTok (unofficial)
    @staticmethod
    def parse_tiktok(payload):
        """True or False when the answer is clear, None when it can't be read."""
        if not isinstance(payload, dict):
            return None
        user = (payload.get("data") or {}).get("user")
        if not isinstance(user, dict) or "status" not in user:
            return None
        return user["status"] == 2

    @staticmethod
    def tiktok_extras(payload):
        """Best-effort cover and title for a live TikTok room. Missing pieces are fine."""
        data = (payload or {}).get("data") or {}
        room = data.get("liveRoom") if isinstance(data.get("liveRoom"), dict) else {}
        user = data.get("user") if isinstance(data.get("user"), dict) else {}
        cover = room.get("coverUrl") or user.get("roomCover")
        if not cover:
            urls = ((room.get("cover") or {}).get("url_list") if isinstance(room.get("cover"), dict) else None) or []
            cover = urls[0] if urls else None
        cover = cover or user.get("avatarLarger")
        return {"cover": cover if isinstance(cover, str) and cover.startswith("https://") else None, "title": str(room.get("title") or "")[:300]}

    async def tiktok_live(self, session, name):
        url = "https://www.tiktok.com/api-live/user/room/"
        async with session.get(url, params={"aid": 1988, "uniqueId": name, "sourceType": 54}, headers=TIKTOK_HEADERS) as resp:
            if resp.status != 200:
                raise RuntimeError(f"TikTok answered {resp.status}")
            try:
                payload = await resp.json(content_type=None)
            except ValueError:
                raise RuntimeError("TikTok answered with something that isn't data (the host may be blocked)")
        self.tiktok_seen[name] = self.tiktok_extras(payload)
        return self.parse_tiktok(payload)

    def tiktok_embed(self, name):
        extras = self.tiktok_seen.get(name, {})
        embed = discord.Embed(title=f"{name} is live", url=f"https://www.tiktok.com/@{name}/live", description=extras.get("title") or None, color=discord.Color.from_rgb(254, 44, 85))
        embed.set_author(name="TikTok")
        embed.add_field(name="Watch", value=f"[tiktok.com/@{name}](https://www.tiktok.com/@{name}/live)")
        if extras.get("cover"):
            embed.set_image(url=extras["cover"])
        return embed

    async def tiktok_check(self):
        wanted = sorted({name for cfg in self.store.data["guilds"].values() for name in cfg.get("tiktok", [])})
        if not wanted:
            return
        results = {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            for name in wanted:
                try:
                    results[name] = await self.tiktok_live(session, name)
                except (RuntimeError, aiohttp.ClientError) as error:
                    print(f"[streams] TikTok check for {name} failed: {error}")
                await asyncio.sleep(1.5)
        for gid, cfg in list(self.store.data["guilds"].items()):
            guild = self.bot.get_guild(int(gid))
            if guild is None:
                continue
            state = self.store.data["tiktok_live"].setdefault(gid, {})
            for name in cfg.get("tiktok", []):
                live = results.get(name)
                if live is True and name not in state:
                    state[name] = {"start": time.time()}
                    embed = self.tiktok_embed(name)
                    await self.announce(guild, embed, ping=True)
                    self.store.save()
                elif live is False and name in state:
                    length = time.time() - state.pop(name)["start"]
                    self.record(guild.id, f"tiktok:{name}", length)
                    embed = discord.Embed(title=f"{name} ended their TikTok live", url=f"https://www.tiktok.com/@{name}", description=f"Live for about **{duration(length)}** (counted from when I noticed).", color=discord.Color.dark_grey())
                    await self.announce(guild, embed)
                    self.store.save()

    @tasks.loop(seconds=TIKTOK_POLL)
    async def tiktok_loop(self):
        try:
            await self.tiktok_check()
        except Exception as error:  # never let this loop die
            print(f"[streams] TikTok loop error: {error}")

    @tiktok_loop.before_loop
    async def before_tiktok(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def tiktok_name(text):
        text = text.strip().rsplit("/", 1)[-1] if "tiktok.com" in text and "@" not in text else text.strip()
        name = text.split("@")[-1].split("/")[0].split("?")[0].lower()
        return name if 2 <= len(name) <= 24 and name.replace("_", "").replace(".", "").isalnum() else None

    @commands.command(name="tiktokadd")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def tiktokadd(self, ctx, account: str):
        """Watches a TikTok account and posts when it goes live and ends. Usage: !tiktokadd @name"""
        name = self.tiktok_name(account)
        if not name:
            raise ModError("Give the TikTok username, like `@name`.")
        config = self.cfg(ctx.guild.id)
        if not config["channel"]:
            raise ModError("Pick an alert channel first with `streamalerts #channel`.")
        if name in config["tiktok"]:
            raise ModError("I'm already watching that account.")
        if len(config["tiktok"]) >= MAX_TIKTOK:
            raise ModError(f"This server watches {MAX_TIKTOK} TikTok accounts already.")
        config["tiktok"].append(name)
        self.store.save()
        await ctx.reply(f"Watching **@{name}** on TikTok. I check every {TIKTOK_POLL} seconds. TikTok has no official API, so run `tiktoktest {name}` while they're live to make sure it works on this host.", mention_author=False)

    @commands.command(name="tiktokremove")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def tiktokremove(self, ctx, account: str):
        """Stops watching a TikTok account. Usage: !tiktokremove @name"""
        name = self.tiktok_name(account)
        config = self.cfg(ctx.guild.id)
        if name not in config["tiktok"]:
            raise ModError("I'm not watching that account.")
        config["tiktok"].remove(name)
        self.store.data["tiktok_live"].get(str(ctx.guild.id), {}).pop(name, None)
        self.store.save()
        await ctx.reply("Stopped watching it.", mention_author=False)

    @commands.command(name="tiktoklist")
    @commands.guild_only()
    async def tiktoklist(self, ctx):
        """Lists the TikTok accounts this server watches. Usage: !tiktoklist"""
        names = self.cfg(ctx.guild.id)["tiktok"]
        await ctx.reply(", ".join(f"[@{n}](https://www.tiktok.com/@{n})" for n in names) or "No TikTok accounts are watched. Add one with `tiktokadd`.", mention_author=False, suppress_embeds=True)

    @commands.command(name="tiktoktest")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def tiktoktest(self, ctx, account: str):
        """Checks one TikTok account right now and says what Risk sees. Usage: !tiktoktest @name"""
        name = self.tiktok_name(account)
        if not name:
            raise ModError("Give the TikTok username, like `@name`.")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            try:
                live = await self.tiktok_live(session, name)
            except (RuntimeError, aiohttp.ClientError) as error:
                raise ModError(f"TikTok check failed: {str(error)[:150]}. Alerts for TikTok won't work from this host.")
        if live is None:
            raise ModError("TikTok answered, but not in a form I understand. TikTok may have changed it, or the account doesn't exist.")
        if live:
            await ctx.reply(f"**@{name}** is live right now. This is what an alert looks like:", embed=self.tiktok_embed(name), mention_author=False)
        else:
            await ctx.reply(f"**@{name}** is not live right now.", mention_author=False)

    @commands.command(name="twitchtest")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def twitchtest(self, ctx, login: str):
        """Checks one Twitch channel right now and shows what the alert looks like. Usage: !twitchtest shroud"""
        if not self.twitch_ready:
            raise ModError("Twitch checks need `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` set on the bot host.")
        login = login.strip().lower().rsplit("/", 1)[-1]
        if not login.replace("_", "").isalnum() or not 3 <= len(login) <= 25:
            raise ModError("Give the channel name, like `shroud`.")
        try:
            found = await self.twitch_streams([login])
        except (RuntimeError, aiohttp.ClientError) as error:
            raise ModError(f"Twitch check failed: {str(error)[:150]}")
        if login in found:
            await ctx.reply(f"**{login}** is live right now. This is what an alert looks like:", embed=self.twitch_embed(login, found[login]), mention_author=False)
        else:
            await ctx.reply(f"**{login}** is not live right now.", mention_author=False)

    @commands.command(name="streamtest")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 15, commands.BucketType.guild)
    async def streamtest(self, ctx):
        """Posts a sample 'is live' and 'stopped' alert in the alert channel. Usage: !streamtest"""
        config = self.cfg(ctx.guild.id)
        channel = ctx.guild.get_channel(config["channel"]) if config["channel"] else None
        if not isinstance(channel, discord.TextChannel):
            raise ModError("Pick an alert channel first with `streamalerts #channel`.")
        if not channel.permissions_for(ctx.guild.me).send_messages or not channel.permissions_for(ctx.guild.me).embed_links:
            raise ModError(f"I can't send embeds in {channel.mention}.")
        member = ctx.author
        live = discord.Embed(title=f"{member.display_name} is live", url="https://www.twitch.tv/", description="Sample stream title", color=discord.Color.from_rgb(145, 70, 255))
        live.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        live.add_field(name="Where", value="Test")
        live.add_field(name="Watch", value="[Open the stream](https://www.twitch.tv/)")
        live.set_footer(text="This is a test alert")
        done = discord.Embed(title=f"{member.display_name} stopped streaming", description="Streamed for **1h 24m**.", color=discord.Color.dark_grey())
        done.set_footer(text="This is a test alert")
        await channel.send(embed=live, allowed_mentions=NO_MENTIONS)
        await channel.send(embed=done, allowed_mentions=NO_MENTIONS)
        await ctx.reply(f"Sent a sample alert to {channel.mention}.", mention_author=False)

    # Commands
    @commands.group(name="streamalerts", aliases=["streamalert"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def streamalerts(self, ctx, channel: discord.TextChannel = None):
        """Sets the channel for stream start and end alerts. Usage: !streamalerts #streams (or !streamalerts off)"""
        config = self.cfg(ctx.guild.id)
        if channel is None:
            now = f"<#{config['channel']}>" if config["channel"] else "off"
            raise ModError(f"Stream alerts are {now}. Use `streamalerts #channel` to pick a channel or `streamalerts off` to stop them.")
        if not channel.permissions_for(ctx.guild.me).send_messages or not channel.permissions_for(ctx.guild.me).embed_links:
            raise ModError("I need Send Messages and Embed Links in that channel.")
        config["channel"] = channel.id
        self.store.save()
        await ctx.reply(f"Stream alerts will go to {channel.mention}. Anyone using Go Live in a voice channel is covered. For Twitch channels use `twitchadd`.", mention_author=False)

    @streamalerts.command(name="off")
    @commands.has_permissions(manage_guild=True)
    async def streamalerts_off(self, ctx):
        """Turns stream alerts off. Usage: !streamalerts off"""
        self.cfg(ctx.guild.id)["channel"] = None
        self.store.save()
        await ctx.reply("Stream alerts are off.", mention_author=False)

    @commands.command(name="streamrole")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def streamrole(self, ctx, role: discord.Role = None):
        """Picks a role to ping when someone starts streaming (leave empty to stop pinging). Usage: !streamrole @Streams"""
        if role and not role.mentionable and not ctx.guild.me.guild_permissions.mention_everyone:
            raise ModError("That role isn't mentionable. Turn on 'Allow anyone to @mention this role' for it first.")
        self.cfg(ctx.guild.id)["role"] = role.id if role else None
        self.store.save()
        await ctx.reply(f"I'll ping {role.mention} when someone starts streaming." if role else "I won't ping anyone for streams.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="twitchadd")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def twitchadd(self, ctx, login: str):
        """Watches a Twitch channel and posts when it goes live and offline. Usage: !twitchadd shroud"""
        if not self.twitch_ready:
            raise ModError("Twitch alerts need a free Twitch app. Create one at dev.twitch.tv/console, then set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` on the bot host and restart.")
        login = login.strip().lower().rsplit("/", 1)[-1]
        if not login.replace("_", "").isalnum() or not 3 <= len(login) <= 25:
            raise ModError("Give the channel name, like `shroud`.")
        config = self.cfg(ctx.guild.id)
        if not config["channel"]:
            raise ModError("Pick an alert channel first with `streamalerts #channel`.")
        if login in config["twitch"]:
            raise ModError("I'm already watching that channel.")
        if len(config["twitch"]) >= MAX_TWITCH:
            raise ModError(f"This server watches {MAX_TWITCH} Twitch channels already.")
        config["twitch"].append(login)
        self.store.save()
        await ctx.reply(f"Watching **{login}** on Twitch. I check every {TWITCH_POLL} seconds.", mention_author=False)

    @commands.command(name="twitchremove")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def twitchremove(self, ctx, login: str):
        """Stops watching a Twitch channel. Usage: !twitchremove shroud"""
        login = login.strip().lower().rsplit("/", 1)[-1]
        config = self.cfg(ctx.guild.id)
        if login not in config["twitch"]:
            raise ModError("I'm not watching that channel.")
        config["twitch"].remove(login)
        self.store.data["twitch_live"].get(str(ctx.guild.id), {}).pop(login, None)
        self.store.save()
        await ctx.reply("Stopped watching it.", mention_author=False)

    @commands.command(name="twitchlist")
    @commands.guild_only()
    async def twitchlist(self, ctx):
        """Lists the Twitch channels this server watches. Usage: !twitchlist"""
        names = self.cfg(ctx.guild.id)["twitch"]
        await ctx.reply(", ".join(f"[{n}](https://twitch.tv/{n})" for n in names) or "No Twitch channels are watched. Add one with `twitchadd`.", mention_author=False, suppress_embeds=True)

    @commands.command(name="streaming", aliases=["live", "whoslive"])
    @commands.guild_only()
    async def streaming(self, ctx):
        """Shows who is streaming right now. Usage: !streaming"""
        lines = []
        for (gid, uid, source), info in self.live.items():
            if gid == ctx.guild.id:
                lines.append(f"<@{uid}> on {source}, for {duration(time.time() - info['start'])}" + (f" - {info['title'][:60]}" if info["title"] else ""))
        for name, info in self.store.data["twitch_live"].get(str(ctx.guild.id), {}).items():
            lines.append(f"[{info['name']}](https://twitch.tv/{name}) on Twitch, for {duration(time.time() - info['start'])}")
        for name in self.store.data["tiktok_live"].get(str(ctx.guild.id), {}):
            lines.append(f"[@{name}](https://www.tiktok.com/@{name}/live) on TikTok")
        embed = discord.Embed(title="Live now", description="\n".join(lines) or "Nobody is streaming right now.", color=discord.Color.from_rgb(145, 70, 255))
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="streamstats", aliases=["laststream"])
    @commands.guild_only()
    async def streamstats(self, ctx, member: discord.Member = None):
        """Shows a member's stream count, total time and last stream. Usage: !streamstats @user"""
        member = member or ctx.author
        stats = self.store.data["stats"].get(str(ctx.guild.id), {}).get(str(member.id))
        if not stats:
            raise ModError(f"{member.display_name} hasn't streamed since I started tracking.")
        embed = discord.Embed(title=f"{member.display_name}'s streams", color=discord.Color.from_rgb(145, 70, 255))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Streams", value=str(stats["count"]))
        embed.add_field(name="Total time", value=duration(stats["seconds"]))
        embed.add_field(name="Longest", value=duration(stats["longest"]))
        embed.add_field(name="Last ended", value=f"<t:{stats['last']}:R>", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="streamers", aliases=["streamboard"])
    @commands.guild_only()
    async def streamers(self, ctx):
        """Ranks members by total time streamed. Usage: !streamers"""
        stats = self.store.data["stats"].get(str(ctx.guild.id), {})
        ranked = sorted(stats.items(), key=lambda kv: kv[1]["seconds"], reverse=True)[:10]
        if not ranked:
            raise ModError("Nobody has streamed since I started tracking.")
        lines = []
        for place, (key, s) in enumerate(ranked, 1):
            if key.startswith("twitch:"):
                who = f"[{key[7:]}](https://twitch.tv/{key[7:]})"
            elif key.startswith("tiktok:"):
                who = f"[@{key[7:]}](https://www.tiktok.com/@{key[7:]})"
            else:
                who = f"<@{key}>"
            lines.append(f"**{place}.** {who} - {duration(s['seconds'])} over {s['count']} stream(s)")
        await ctx.reply(embed=discord.Embed(title="Top streamers", description="\n".join(lines), color=discord.Color.from_rgb(145, 70, 255)), mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(Streams(bot))
