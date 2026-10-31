from datetime import datetime, timezone

import discord
from discord.ext import commands


class BotTime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="time")
    async def tell_time(self, ctx, timezone_name: str = None):
        """Shows the current time in UTC or a timezone. Usage: !time or !time America/Chicago"""
        now = datetime.now(timezone.utc)
        if timezone_name:
            try:
                from zoneinfo import ZoneInfo
                now = now.astimezone(ZoneInfo(timezone_name))
            except Exception:
                await ctx.reply("I don't know that timezone. Try `America/Chicago` or `Europe/London`.", mention_author=False)
                return
        label = timezone_name or "UTC"
        embed = discord.Embed(title=f"Time in {label}", description=f"**{now.strftime('%A, %B %d, %Y')}**\n{now.strftime('%I:%M:%S %p')}", color=discord.Color.light_grey())
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(BotTime(bot))
