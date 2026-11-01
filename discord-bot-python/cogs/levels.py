import random
import time

import discord
from discord.ext import commands, tasks

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

XP_COOLDOWN = 60


def level_for(xp):
    return int((xp / 100) ** 0.5)


def xp_for(level):
    return 100 * level * level


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("levels")
        self.dirty = False

    async def cog_load(self):
        self.flush.start()

    def cog_unload(self):
        self.flush.cancel()
        if self.dirty:
            self.store.save()

    @tasks.loop(seconds=30)
    async def flush(self):
        if self.dirty:
            self.dirty = False
            self.store.save()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def entry(self, guild_id, user_id):
        return self.store.data.setdefault(str(guild_id), {}).setdefault(str(user_id), {"xp": 0, "last": 0})

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or not message.content:
            return
        entry = self.entry(message.guild.id, message.author.id)
        now = int(time.time())
        if now - entry["last"] < XP_COOLDOWN:
            return
        before = level_for(entry["xp"])
        entry["xp"] += random.randint(15, 25)
        entry["last"] = now
        self.dirty = True
        after = level_for(entry["xp"])
        if after > before:
            try:
                await message.channel.send(f"🎉 {message.author.mention} reached level **{after}**!", allowed_mentions=discord.AllowedMentions(users=[message.author]))
            except discord.HTTPException:
                pass

    @commands.command(name="rank", aliases=["level"])
    async def rank(self, ctx, member: discord.Member = None):
        """Shows someone's level and XP. Usage: !rank @user"""
        member = member or ctx.author
        guild = self.store.data.get(str(ctx.guild.id), {})
        entry = guild.get(str(member.id), {"xp": 0})
        xp = entry["xp"]
        level = level_for(xp)
        start, goal = xp_for(level), xp_for(level + 1)
        progress = (xp - start) / (goal - start)
        filled = int(progress * 12)
        bar = "█" * filled + "░" * (12 - filled)
        ranked = sorted(guild.items(), key=lambda item: item[1]["xp"], reverse=True)
        position = next((i for i, (uid, _) in enumerate(ranked, start=1) if uid == str(member.id)), None)
        embed = discord.Embed(title=member.display_name, color=discord.Color.light_grey())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="Rank", value=f"#{position}" if position else "Unranked")
        embed.add_field(name="XP", value=f"{xp:,} / {goal:,}")
        embed.add_field(name="Progress", value=f"`{bar}` {int(progress * 100)}%", inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="levels", aliases=["xpboard"])
    async def levels(self, ctx):
        """Shows the most active members by XP. Usage: !levels"""
        guild = self.store.data.get(str(ctx.guild.id), {})
        ranked = sorted(guild.items(), key=lambda item: item[1]["xp"], reverse=True)[:10]
        if not ranked:
            await ctx.reply("Nobody has any XP yet. Start chatting.", mention_author=False)
            return
        lines = []
        for index, (uid, entry) in enumerate(ranked, start=1):
            member = ctx.guild.get_member(int(uid))
            name = discord.utils.escape_markdown(member.display_name) if member else f"User {uid}"
            lines.append(f"**{index}.** {name}: level {level_for(entry['xp'])} ({entry['xp']:,} XP)")
        await ctx.reply(embed=discord.Embed(title="Top chatters", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="setxp")
    @commands.has_permissions(manage_guild=True)
    async def setxp(self, ctx, member: discord.Member, xp: int):
        """Sets someone's XP. Usage: !setxp @user 2500"""
        if not 0 <= xp <= 10_000_000:
            await ctx.reply("XP must be between 0 and 10,000,000.", mention_author=False)
            return
        self.entry(ctx.guild.id, member.id)["xp"] = xp
        self.dirty = True
        await ctx.reply(f"Set {member.display_name} to {xp:,} XP (level {level_for(xp)}).", mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(Levels(bot))
