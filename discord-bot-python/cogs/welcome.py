import re

import discord
from discord.ext import commands

from utils.helpers import embed_split, explain_error, message_payload
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
        """Greets new members in a channel. Write New_user where the name goes. Put {embed} at the start and the end to send it as an embed. Usage: !welcome #channel {embed} Welcome New_user to Risk {embed}"""
        entry = self.config.data.setdefault(str(ctx.guild.id), {})
        entry.update(channel=channel.id, text=text[:1500])
        self.config.save()
        payload = message_payload(text, ctx.author, user_pattern="new_user", ping=False)
        await ctx.send(f"Welcome messages will go to {channel.mention}. Preview:\n{payload.get('content') or ''}".rstrip(), embed=payload.get("embed"), allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="welcomeoff")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcomeoff(self, ctx):
        """Turns welcome messages off. Usage: !welcomeoff"""
        entry = self.config.data.get(str(ctx.guild.id), {})
        entry.pop("channel", None)
        entry.pop("text", None)
        if not entry:
            self.config.data.pop(str(ctx.guild.id), None)
        self.config.save()
        await ctx.send("Welcome messages are off.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        entry = self.config.data.get(str(member.guild.id))
        if not entry or not entry.get("channel") or not entry.get("text"):
            return
        channel = member.guild.get_channel(entry["channel"])
        if channel is None:
            return
        vip = self.bot.get_cog("VIP")
        payload = message_payload(entry["text"], member, user_pattern="new_user", color=vip.embed_color(member.guild.id) if vip else None)
        try:
            await channel.send(**payload, allowed_mentions=discord.AllowedMentions(users=[member]))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        entry = self.config.data.get(str(member.guild.id))
        if not entry or not entry.get("leave_channel") or not entry.get("leave_text"):
            return
        channel = member.guild.get_channel(entry["leave_channel"])
        if channel is None:
            return
        body, as_embed = embed_split(entry["leave_text"])
        name = discord.utils.escape_markdown(member.display_name)
        text = re.sub("new_user", name, body, flags=re.I)
        try:
            if as_embed:
                vip = self.bot.get_cog("VIP")
                color = vip.embed_color(member.guild.id) if vip else None
                embed = discord.Embed(description=text[:4000], color=color if color is not None else discord.Color.dark_grey())
                embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            else:
                await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))
