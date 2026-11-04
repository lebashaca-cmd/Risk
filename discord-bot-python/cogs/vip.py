"""Risk VIP: a per-server upgrade that raises limits and unlocks extra features.

VIP is granted by the bot owner (`!vipgrant`) or by listing server ids in the VIP_GUILD_IDS environment
variable. It is not tied to any payment system. Other cogs ask `is_vip(guild_id)` and `limit(guild_id, key)`.
"""
import asyncio
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

import os

# (free, vip) for every number the dashboard and commands limit.
LIMITS = {
    "responders": (5, 50),
    "command_rules": (5, 100),
    "schedules": (0, 10),
    "badwords": (25, 100),
    "level_rewards": (5, 25),
    "xp_multiplier": (2.0, 5.0),
    "ignored_channels": (10, 50),
}
PERKS = [
    "Up to 50 auto-replies (free: 5)",
    "Command rules for up to 100 commands (free: 5)",
    "Scheduled announcements in the dashboard and with !schedule",
    "XP multiplier up to 5x (free: 2x), 25 level rewards (free: 5)",
    "Up to 100 blocked words (free: 25)",
    "Custom embed colour for Risk's replies in your server",
    "VIP-only commands: !vipembed, !serverstats, !schedule",
]
MIN_INTERVAL = 300


def env_ids():
    ids = set()
    for part in os.getenv("VIP_GUILD_IDS", "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


class VIP(commands.Cog):
    """VIP status, VIP-only commands and scheduled announcements."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("vip")
        self.store.data.setdefault("guilds", {})
        self.store.data.setdefault("schedules", {})

    async def cog_load(self):
        self.sender.start()

    def cog_unload(self):
        self.sender.cancel()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Status helpers used by other cogs
    def info(self, guild_id):
        """{'vip': bool, 'source': 'env'|'granted'|None, 'until': ts|None, 'note': str}"""
        if int(guild_id) in env_ids():
            return {"vip": True, "source": "env", "until": None, "note": ""}
        entry = self.store.data["guilds"].get(str(guild_id))
        if entry:
            until = entry.get("until")
            if until is None or until > time.time():
                return {"vip": True, "source": "granted", "until": until, "note": entry.get("note", "")}
        return {"vip": False, "source": None, "until": None, "note": ""}

    def is_vip(self, guild_id):
        return self.info(guild_id)["vip"]

    def limit(self, guild_id, key):
        free, vip = LIMITS[key]
        return vip if self.is_vip(guild_id) else free

    def limits(self, guild_id):
        return {key: self.limit(guild_id, key) for key in LIMITS}

    def cfg(self, guild_id):
        data = self.store.data.setdefault("guilds", {}).setdefault(str(guild_id), {})
        return data

    def embed_color(self, guild_id):
        """The custom embed colour (an int) when the server is VIP and picked one."""
        if not self.is_vip(guild_id):
            return None
        value = self.store.data["guilds"].get(str(guild_id), {}).get("color")
        return value if isinstance(value, int) else None

    def need_vip(self, ctx):
        if ctx.guild is None or not self.is_vip(ctx.guild.id):
            raise ModError("That's a **VIP** feature. Run `!vip` to see what VIP adds and how to get it.")

    # Commands
    @commands.command(name="vip")
    @commands.guild_only()
    async def vip(self, ctx):
        """Shows this server's VIP status and what VIP unlocks. Usage: !vip"""
        info = self.info(ctx.guild.id)
        embed = discord.Embed(title="Risk VIP", color=self.embed_color(ctx.guild.id) or discord.Color.gold() if info["vip"] else discord.Color.dark_grey())
        if info["vip"]:
            until = f"until <t:{int(info['until'])}:D>" if info["until"] else "with no end date"
            embed.description = f"**{ctx.guild.name}** has VIP {until}."
        else:
            embed.description = f"**{ctx.guild.name}** is on the free plan."
        embed.add_field(name="VIP includes", value="\n".join(f"• {p}" for p in PERKS), inline=False)
        url = os.getenv("VIP_URL", "").strip()
        if not info["vip"] and url.startswith("https://"):
            embed.add_field(name="Get VIP", value=url, inline=False)
        elif not info["vip"]:
            embed.add_field(name="Get VIP", value="Ask the bot owner to enable it for this server.", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="vipgrant")
    @commands.is_owner()
    async def vipgrant(self, ctx, guild_id: int, days: int = 0, *, note: str = ""):
        """Owner only. Gives a server VIP for some days (0 = no end). Usage: !vipgrant <server id> [days] [note]"""
        if self.bot.get_guild(guild_id) is None:
            raise ModError("Risk isn't in that server.")
        if not 0 <= days <= 3650:
            raise ModError("Days must be between 0 and 3650.")
        entry = self.cfg(guild_id)
        entry["until"] = time.time() + days * 86400 if days else None
        entry["note"] = note[:100]
        self.store.save()
        await ctx.reply(f"VIP is on for **{self.bot.get_guild(guild_id).name}** " + (f"for {days} days." if days else "with no end date."), mention_author=False)

    @commands.command(name="viprevoke")
    @commands.is_owner()
    async def viprevoke(self, ctx, guild_id: int):
        """Owner only. Removes a server's VIP. Usage: !viprevoke <server id>"""
        entry = self.store.data["guilds"].get(str(guild_id))
        if not entry or "until" not in entry:
            raise ModError("That server has no granted VIP.")
        entry.pop("until", None)
        entry.pop("note", None)
        entry["until"] = 1
        self.store.save()
        await ctx.reply("VIP removed. Their settings are kept, but the VIP limits no longer apply.", mention_author=False)

    @commands.command(name="viplist")
    @commands.is_owner()
    async def viplist(self, ctx):
        """Owner only. Lists servers that have VIP. Usage: !viplist"""
        rows = []
        for guild in self.bot.guilds:
            info = self.info(guild.id)
            if info["vip"]:
                when = f"until <t:{int(info['until'])}:D>" if info["until"] else "no end"
                rows.append(f"**{guild.name}** (`{guild.id}`) - {info['source']}, {when}")
        await ctx.reply("\n".join(rows) or "No server has VIP.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="vipembed")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def vipembed(self, ctx, channel: discord.TextChannel, colour: str, *, text: str):
        """VIP. Posts a custom embed. Usage: !vipembed #channel #5865f2 Title | Body text"""
        self.need_vip(ctx)
        try:
            value = int(colour.lstrip("#"), 16)
        except ValueError:
            raise ModError("Give the colour as hex, like `#5865f2`.")
        if not 0 <= value <= 0xFFFFFF:
            raise ModError("That colour isn't valid.")
        if not channel.permissions_for(ctx.author).send_messages or not channel.permissions_for(ctx.guild.me).send_messages:
            raise ModError("Either of us can't post in that channel.")
        title, _, body = text.partition("|")
        if not body.strip():
            title, body = "", title
        if len(title.strip()) > 256 or len(body.strip()) > 3500:
            raise ModError("That's too long for an embed.")
        embed = discord.Embed(title=title.strip() or None, description=body.strip(), color=value)
        embed.set_footer(text=f"Posted by {ctx.author.display_name}")
        await channel.send(embed=embed, allowed_mentions=NO_MENTIONS)
        await ctx.reply(f"Posted in {channel.mention}.", mention_author=False)

    @commands.command(name="serverstats")
    @commands.guild_only()
    async def serverstats(self, ctx):
        """VIP. Shows a detailed server report. Usage: !serverstats"""
        self.need_vip(ctx)
        g = ctx.guild
        humans = sum(1 for m in g.members if not m.bot)
        online = sum(1 for m in g.members if m.status != discord.Status.offline)
        embed = discord.Embed(title=f"{g.name} report", color=self.embed_color(g.id) or discord.Color.gold())
        embed.add_field(name="Members", value=f"{g.member_count} total\n{humans} people, {g.member_count - humans} bots\n{online} online (cached)")
        embed.add_field(name="Channels", value=f"{len(g.text_channels)} text\n{len(g.voice_channels)} voice\n{len(g.categories)} categories")
        embed.add_field(name="Other", value=f"{len(g.roles) - 1} roles\n{len(g.emojis)} emojis\nBoost level {g.premium_tier} ({g.premium_subscription_count} boosts)")
        embed.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:D>", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    # Scheduled announcements (shared with the dashboard)
    def schedules(self, guild_id):
        return self.store.data["schedules"].setdefault(str(guild_id), [])

    @staticmethod
    def parse_interval(text):
        text = text.strip().lower()
        units = {"m": 60, "h": 3600, "d": 86400}
        if len(text) < 2 or text[-1] not in units or not text[:-1].isdigit():
            raise ModError("Use an interval like `30m`, `6h` or `1d`.")
        seconds = int(text[:-1]) * units[text[-1]]
        if not MIN_INTERVAL <= seconds <= 30 * 86400:
            raise ModError("The interval must be between 5 minutes and 30 days.")
        return seconds

    @commands.command(name="schedule")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def schedule(self, ctx, channel: discord.TextChannel, every: str, *, message: str):
        """VIP. Repeats a message in a channel. Usage: !schedule #channel 6h Your message"""
        self.need_vip(ctx)
        interval = self.parse_interval(every)
        items = self.schedules(ctx.guild.id)
        if len(items) >= self.limit(ctx.guild.id, "schedules"):
            raise ModError("This server has used all its scheduled messages. Remove one with `!unschedule`.")
        if len(message) > 1500:
            raise ModError("Keep the message under 1500 characters.")
        if not channel.permissions_for(ctx.guild.me).send_messages:
            raise ModError("I can't post in that channel.")
        number = max((i["id"] for i in items), default=0) + 1
        items.append({"id": number, "channel": channel.id, "every": interval, "text": message, "next": time.time() + interval, "on": True})
        self.store.save()
        await ctx.reply(f"Scheduled #{number}: every {every} in {channel.mention}.", mention_author=False)

    @commands.command(name="schedules")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def schedules_cmd(self, ctx):
        """Lists this server's scheduled messages. Usage: !schedules"""
        items = self.schedules(ctx.guild.id)
        lines = [f"**#{i['id']}** every {i['every'] // 60} min in <#{i['channel']}>{'' if i.get('on', True) else ' (paused)'}: {i['text'][:60]}" for i in items]
        await ctx.reply("\n".join(lines) or "Nothing is scheduled.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="unschedule")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def unschedule(self, ctx, number: int):
        """Removes a scheduled message. Usage: !unschedule <number>"""
        items = self.schedules(ctx.guild.id)
        keep = [i for i in items if i["id"] != number]
        if len(keep) == len(items):
            raise ModError("There's no scheduled message with that number.")
        self.store.data["schedules"][str(ctx.guild.id)] = keep
        self.store.save()
        await ctx.reply("Removed.", mention_author=False)

    @tasks.loop(seconds=60)
    async def sender(self):
        now = time.time()
        changed = False
        for gid, items in list(self.store.data["schedules"].items()):
            guild = self.bot.get_guild(int(gid))
            if guild is None or not self.is_vip(guild.id):
                continue
            for item in items:
                if not item.get("on", True) or item["next"] > now:
                    continue
                item["next"] = now + item["every"]
                changed = True
                channel = guild.get_channel(item["channel"])
                if isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).send_messages:
                    try:
                        await channel.send(item["text"][:2000], allowed_mentions=NO_MENTIONS)
                    except discord.HTTPException:
                        pass
        if changed:
            self.store.save()

    @sender.before_loop
    async def before_sender(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(VIP(bot))
