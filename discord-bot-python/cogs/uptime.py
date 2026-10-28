import time
from datetime import datetime, timezone

import discord
from discord.ext import commands


class Uptime(commands.Cog):
    """Shows how long the bot has been running."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Monotonic time is stable even if the system clock changes.
        self.started_at = time.monotonic()

    @commands.command(name="uptime")
    async def uptime(self, ctx: commands.Context):
        """Usage: ,uptime"""
        elapsed_seconds = max(0, int(time.monotonic() - self.started_at))
        days, remainder = divmod(elapsed_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds or not parts:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        embed = discord.Embed(
            title="Bot Uptime",
            description="I've been online for **" + ", ".join(parts) + "**.",
            color=discord.Color.dark_purple(),
        )
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Uptime(bot))
