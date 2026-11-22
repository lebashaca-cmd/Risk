"""Another batch of VIP commands, grouped by the plan that unlocks them.

Basic (every VIP plan): vipdraw, vipcountdown, vipchoose.
White (White and Supreme): vipnicklock, vipautothread.
Supreme: vipcleanbots, vipnewmembers.
"""
import random
import re
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

DURATION = re.compile(r"(\d+)\s*([smhdw])", re.I)
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(text):
    parts = DURATION.findall(text)
    if not parts or DURATION.sub("", text).strip():
        raise ModError("Give a time like `30m`, `2h`, `3d` or `1w2d`.")
    return sum(int(n) * UNITS[u.lower()] for n, u in parts)


class VIPExtra(commands.Cog, name="VIPExtra"):
    """More VIP commands: draws, countdowns, nickname locks, auto threads and cleanup tools."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("vip_extra")
        for key in ("nicklock", "autothread"):
            self.store.data.setdefault(key, {})

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    @property
    def vip(self):
        cog = self.bot.get_cog("VIP")
        if cog is None:
            raise ModError("VIP isn't loaded right now.")
        return cog

    def need(self, ctx, group):
        self.vip.need(ctx, group)

    def active(self, guild_id, group="white"):
        vip = self.bot.get_cog("VIP")
        return vip is not None and vip.is_vip(guild_id) and vip.has(guild_id, group)

    # ------------------------------------------------------------------ Basic
    @commands.command(name="vipdraw")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def vipdraw(self, ctx, role: discord.Role, winners: int = 1):
        """VIP. Picks random members who have a role, like a quick raffle. Usage: !vipdraw @Members 3"""
        self.need(ctx, "basic")
        pool = [m for m in role.members if not m.bot]
        if not pool:
            raise ModError("Nobody (apart from bots) has that role.")
        winners = max(1, min(winners, 20, len(pool)))
        picked = random.sample(pool, winners)
        embed = discord.Embed(title="\U0001F389 Draw", description="\n".join(f"{i}. {m.mention}" for i, m in enumerate(picked, 1)), color=self.vip.embed_color(ctx.guild.id) or discord.Color.gold())
        embed.set_footer(text=f"{winners} of {len(pool)} members with {role.name}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=discord.AllowedMentions(users=picked))

    @commands.command(name="vipcountdown")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def vipcountdown(self, ctx, when: str, *, name: str):
        """VIP. Posts a live countdown that updates itself for everyone. Usage: !vipcountdown 3d Server event | !vipcountdown 2h30m Movie night"""
        self.need(ctx, "basic")
        seconds = parse_duration(when)
        if not 60 <= seconds <= 365 * 86400:
            raise ModError("Pick a time between 1 minute and 1 year from now.")
        end = int(time.time()) + seconds
        embed = discord.Embed(title=name[:200], description=f"Starts <t:{end}:R>\n<t:{end}:F>", color=self.vip.embed_color(ctx.guild.id) or discord.Color.gold())
        embed.set_footer(text=f"Set by {ctx.author.display_name}")
        await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)

    @commands.command(name="vipchoose", aliases=["vippick"])
    @commands.guild_only()
    async def vipchoose(self, ctx, *, options: str):
        """VIP. Picks one of your options at random. Separate them with commas. Usage: !vipchoose pizza, tacos, sushi"""
        self.need(ctx, "basic")
        items = [o.strip() for o in options.split(",") if o.strip()]
        if len(items) < 2:
            raise ModError("Give at least two options, separated by commas.")
        await ctx.reply(f"I choose **{random.choice(items)[:200]}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    # ------------------------------------------------------------------ White: nickname lock
    @commands.command(name="vipnicklock")
    @commands.guild_only()
    @commands.has_permissions(manage_nicknames=True)
    async def vipnicklock(self, ctx, member: discord.Member, *, nickname: str = ""):
        """VIP White. Locks a member's nickname: if they change it, Risk puts it back. Usage: !vipnicklock @user Cool Name | !vipnicklock @user (to unlock)"""
        self.need(ctx, "white")
        if member.top_role >= ctx.guild.me.top_role or member.id == ctx.guild.owner_id:
            raise ModError("I can't change that member's nickname (their role is above mine, or they own the server).")
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            raise ModError("That member's top role is not below yours.")
        locks = self.store.data["nicklock"].setdefault(str(ctx.guild.id), {})
        if not nickname:
            if locks.pop(str(member.id), None) is None:
                raise ModError("That member's nickname isn't locked.")
            self.store.save()
            await ctx.reply(f"Unlocked {member.display_name}'s nickname.", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        if len(nickname) > 32:
            raise ModError("A nickname can be up to 32 characters.")
        if len(locks) >= 100:
            raise ModError("A server can lock up to 100 nicknames.")
        locks[str(member.id)] = nickname
        self.store.save()
        await member.edit(nick=nickname, reason=f"Nickname lock by {ctx.author}")
        await ctx.reply(f"Locked {member.mention}'s nickname to **{nickname}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.Cog.listener("on_member_update")
    async def keep_nick(self, before, after):
        if before.nick == after.nick:
            return
        locks = self.store.data["nicklock"].get(str(after.guild.id))
        wanted = locks.get(str(after.id)) if locks else None
        if wanted is None or after.nick == wanted or not self.active(after.guild.id):
            return
        try:
            await after.edit(nick=wanted, reason="Nickname lock")
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------ White: auto threads
    @commands.command(name="vipautothread")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def vipautothread(self, ctx, channel: discord.TextChannel, state: str = "on"):
        """VIP White. Starts a thread under every new message in a channel, good for suggestions or feedback. Usage: !vipautothread #ideas | !vipautothread #ideas off"""
        self.need(ctx, "white")
        mine = channel.permissions_for(ctx.guild.me)
        entry = self.store.data["autothread"].setdefault(str(ctx.guild.id), [])
        if state.lower() == "off":
            if channel.id in entry:
                entry.remove(channel.id)
            self.store.save()
            await ctx.reply(f"Stopped starting threads in {channel.mention}.", mention_author=False)
            return
        if not (mine.create_public_threads and mine.send_messages_in_threads):
            raise ModError("I need Create Public Threads and Send Messages in Threads in that channel.")
        if channel.id not in entry:
            if len(entry) >= 10:
                raise ModError("You can use auto threads in up to 10 channels.")
            entry.append(channel.id)
        self.store.save()
        await ctx.reply(f"Every new message in {channel.mention} now gets its own thread.", mention_author=False)

    @commands.Cog.listener("on_message")
    async def start_thread(self, message):
        if message.guild is None or message.author.bot or message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        entry = self.store.data["autothread"].get(str(message.guild.id))
        if not entry or message.channel.id not in entry or not self.active(message.guild.id):
            return
        title = re.sub(r"\s+", " ", message.clean_content).strip()[:80] or f"{message.author.display_name}'s thread"
        try:
            await message.create_thread(name=title, auto_archive_duration=1440)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------ Supreme
    @commands.command(name="vipcleanbots")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def vipcleanbots(self, ctx, amount: int = 50):
        """VIP Supreme. Deletes recent messages from bots in this channel (not pinned ones). Usage: !vipcleanbots 100"""
        self.need(ctx, "supreme")
        amount = max(1, min(amount, 200))
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.bot and not m.pinned and m.id != ctx.message.id, reason=f"vipcleanbots by {ctx.author}")
        await ctx.send(f"Deleted {len(deleted)} bot message(s).", delete_after=6)

    @commands.command(name="vipnewmembers")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def vipnewmembers(self, ctx, within: str = "7d"):
        """VIP Supreme. Lists members who joined recently, with how old their accounts are. Usage: !vipnewmembers 3d"""
        self.need(ctx, "supreme")
        seconds = parse_duration(within)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        found = sorted((m for m in ctx.guild.members if m.joined_at and m.joined_at >= cutoff and not m.bot), key=lambda m: m.joined_at, reverse=True)
        if not found:
            raise ModError("Nobody joined in that time.")
        lines = [f"{m.mention}: joined <t:{int(m.joined_at.timestamp())}:R>, account made <t:{int(m.created_at.timestamp())}:R>" for m in found[:25]]
        more = f"\n...and {len(found) - 25} more." if len(found) > 25 else ""
        embed = discord.Embed(title=f"{len(found)} new member(s)", description="\n".join(lines) + more, color=self.vip.embed_color(ctx.guild.id) or discord.Color.gold())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(VIPExtra(bot))
