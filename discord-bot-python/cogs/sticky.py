
import asyncio
import discord
from discord.ext import commands


class Sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sticky_messages = {}
        self.sticky_ids = {}
        self.channel_locks = {}

    @commands.command(name="sticky")
    @commands.has_permissions(manage_messages=True)
    async def sticky(self, ctx, channel: discord.TextChannel, *, message: str):
        """Set a sticky message in a channel."""

        self.sticky_messages[channel.id] = message

        # Remove the old sticky message
        old_id = self.sticky_ids.get(channel.id)

        if old_id:
            try:
                old = await channel.fetch_message(old_id)
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        # Send the new sticky message
        sticky = await channel.send(message)
        self.sticky_ids[channel.id] = sticky.id

        await ctx.send(
            f"Sticky message set in {channel.mention}.",
            delete_after=5
        )

    @commands.command(name="unsticky")
    @commands.has_permissions(manage_messages=True)
    async def unsticky(self, ctx, channel: discord.TextChannel):
        """Remove a channel's sticky message."""

        if channel.id not in self.sticky_messages:
            return await ctx.send("That channel has no sticky message.")

        self.sticky_messages.pop(channel.id, None)

        old_id = self.sticky_ids.pop(channel.id, None)

        if old_id:
            try:
                old = await channel.fetch_message(old_id)
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        await ctx.send(
            f"Sticky message removed from {channel.mention}."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return

        channel_id = message.channel.id

        if channel_id not in self.sticky_messages:
            return

        lock = self.channel_locks.setdefault(
            channel_id, asyncio.Lock()
        )

        async with lock:
            sticky_text = self.sticky_messages.get(channel_id)

            if sticky_text is None:
                return

            old_id = self.sticky_ids.get(channel_id)

            if old_id:
                try:
                    old = await message.channel.fetch_message(old_id)
                    await old.delete()
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    return

            try:
                new_sticky = await message.channel.send(sticky_text)
                self.sticky_ids[channel_id] = new_sticky.id
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(Sticky(bot))
