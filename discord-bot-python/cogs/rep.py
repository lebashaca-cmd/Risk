"""Rep: thanks members who put the server's invite in their Discord custom status.

When a member's custom status contains the rep text (usually the server invite, like `discord.gg/risk`), Risk posts a
pink embed in the chosen channel. Each member is posted once while the bot runs. If they remove the text and add it
back later, they are posted again.

It needs the Presence intent: turn it on in the Developer Portal (Bot, Privileged Gateway Intents) and set
PRESENCE_INTENT=1 on the bot host (STREAM_PRESENCE=1 works too), then restart the bot.
"""
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS
from utils.store import JsonStore

PINK = discord.Color.from_rgb(255, 105, 180)
MAX_TEXT = 100

try:
    from zoneinfo import ZoneInfo
    CENTRAL = ZoneInfo("America/Chicago")
except Exception:  # no time zone data on this host: fall back to daylight time
    CENTRAL = timezone(timedelta(hours=-5), "CDT")


def clean_text(text):
    text = text.strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip("<> ").rstrip("/")


def status_text(member):
    """The text of the member's custom status, or an empty string."""
    for activity in member.activities or ():
        if isinstance(activity, discord.CustomActivity):
            return (activity.name or activity.state or "").strip()
    return ""


def now_central():
    stamp = datetime.now(CENTRAL)
    return f"{stamp.strftime('%b')} {stamp.day}, {stamp.year} {stamp.strftime('%I:%M %p').lstrip('0')} {stamp.tzname()}"


class Rep(commands.Cog, name="Rep"):
    """Posts a thank-you when someone has the server invite in their status."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("rep")
        self.posted = {}  # guild id -> set of member ids already posted this session

    def cfg(self, guild_id):
        return self.store.data.setdefault(str(guild_id), {"text": "", "channel": None})

    def embed_for(self, member, text):
        embed = discord.Embed(title="New rep", description=f"“{text[:300]}”", color=PINK)
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Time", value=now_central(), inline=True)
        return embed

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        member = after
        guild = getattr(member, "guild", None)
        if guild is None or member.bot:
            return
        config = self.store.data.get(str(guild.id))
        if not config or not config.get("text") or not config.get("channel"):
            return
        text = status_text(member)
        posted = self.posted.setdefault(guild.id, set())
        if config["text"] in text.lower():
            if member.id in posted:
                return
            posted.add(member.id)
            channel = guild.get_channel(config["channel"])
            if channel is None or not channel.permissions_for(guild.me).send_messages or not channel.permissions_for(guild.me).embed_links:
                return
            try:
                await channel.send(embed=self.embed_for(member, text), allowed_mentions=NO_MENTIONS)
            except discord.HTTPException:
                posted.discard(member.id)
        elif member.status != discord.Status.offline:
            # Going offline clears activities, so only treat it as removed while they are online.
            posted.discard(member.id)

    @commands.group(name="rep", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def rep(self, ctx):
        """Shows the rep setup. Usage: !rep, !rep text discord.gg/risk, !rep channel #rep, !rep off, !rep test"""
        config = self.cfg(ctx.guild.id)
        channel = ctx.guild.get_channel(config["channel"]) if config["channel"] else None
        lines = [
            f"Rep text: `{config['text']}`" if config["text"] else "Rep text: not set. Use `rep text discord.gg/yourinvite`.",
            f"Channel: {channel.mention}" if channel else "Channel: not set. Use `rep channel #channel`.",
            "I post a pink embed when someone's custom status contains the rep text. Each person is posted once until they remove it and add it back.",
        ]
        if not self.bot.intents.presences:
            lines.append("**The Presence intent is off, so I can't see statuses.** Turn it on in the Developer Portal, set `PRESENCE_INTENT=1` on the bot host and restart.")
        await ctx.reply("\n".join(lines), mention_author=False, allowed_mentions=NO_MENTIONS)

    @rep.command(name="text")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def rep_text(self, ctx, *, text: str):
        """Sets the text to look for, usually your server invite. Usage: !rep text discord.gg/risk"""
        text = clean_text(text)
        if not 3 <= len(text) <= MAX_TEXT:
            raise ModError(f"The rep text must be 3 to {MAX_TEXT} characters.")
        self.cfg(ctx.guild.id)["text"] = text
        self.posted.pop(ctx.guild.id, None)
        self.store.save()
        await ctx.reply(f"Rep text set to `{text}`. I match it anywhere in a custom status, ignoring capitals.", mention_author=False)

    @rep.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def rep_channel(self, ctx, channel: discord.TextChannel):
        """Picks the channel the embeds go to. Usage: !rep channel #rep"""
        mine = channel.permissions_for(ctx.guild.me)
        if not mine.send_messages or not mine.embed_links:
            raise ModError(f"I need Send Messages and Embed Links in {channel.mention}.")
        self.cfg(ctx.guild.id)["channel"] = channel.id
        self.store.save()
        await ctx.reply(f"Rep embeds will go to {channel.mention}.", mention_author=False)

    @rep.command(name="off", aliases=["clear"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def rep_off(self, ctx):
        """Turns rep posts off and forgets the text and channel. Usage: !rep off"""
        self.store.data.pop(str(ctx.guild.id), None)
        self.posted.pop(ctx.guild.id, None)
        self.store.save()
        await ctx.reply("Rep posts are off.", mention_author=False)

    @rep.command(name="test")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def rep_test(self, ctx):
        """Posts a sample embed in the rep channel. Usage: !rep test"""
        config = self.cfg(ctx.guild.id)
        channel = ctx.guild.get_channel(config["channel"]) if config["channel"] else None
        if channel is None or not config["text"]:
            raise ModError("Set the rep text and channel first.")
        await channel.send(embed=self.embed_for(ctx.author, config["text"]), allowed_mentions=NO_MENTIONS)
        await ctx.reply(f"Sent a sample to {channel.mention}.", mention_author=False)


async def setup(bot):
    await bot.add_cog(Rep(bot))
