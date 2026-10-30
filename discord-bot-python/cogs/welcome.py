import re

import discord
from discord.ext import commands

from utils.helpers import explain_error
from utils.store import JsonStore


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = JsonStore("welcome")

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    @commands.command(name="welcome")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx, channel: discord.TextChannel, *, text: str):
        """Greets new members in a channel. Write New_user where the name goes. Usage: !welcome #channel Welcome New_user to Risk"""
        self.config.data[str(ctx.guild.id)] = {"channel": channel.id, "text": text[:1500]}
        self.config.save()
        preview = re.sub("new_user", ctx.author.mention, text, flags=re.I)
        await ctx.send(f"Welcome messages will go to {channel.mention}. Preview:\n{preview}", allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="welcomeoff")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcomeoff(self, ctx):
        """Turns welcome messages off. Usage: !welcomeoff"""
        self.config.data.pop(str(ctx.guild.id), None)
        self.config.save()
        await ctx.send("Welcome messages are off.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        entry = self.config.data.get(str(member.guild.id))
        if not entry:
            return
        channel = member.guild.get_channel(entry["channel"])
        if channel is None:
            return
        text = re.sub("new_user", member.mention, entry["text"], flags=re.I)
        try:
            await channel.send(text, allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))
