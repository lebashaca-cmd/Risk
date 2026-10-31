
import asyncio
import discord
from discord.ext import commands


class Sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sticky_messages = {}
        self.sticky_ids = {}
        self.channel_locks = {}

    def create_embed(self, message):
        embed = discord.Embed(
            description=message,
            color=discord.Color.from_rgb(255, 200, 0)
        )
        embed.set_footer(text="RISK • Sticky Message")
        return embed

    @commands.command(name="sticky")
    @commands.has_permissions(manage_messages=True)
    async def sticky(self, ctx, channel: discord.TextChannel, *, message: str):
        """Set an embedded sticky message."""

        self.sticky_messages[channel.id] = message

        old_id = self.sticky_ids.get(channel.id)

        if old_id:
            try:
                old = await channel.fetch_message(old_id)
                await old.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        try:
            embed = self.create_embed(message)
            sticky = await channel.send(embed=embed)
            self.sticky_ids[channel.id] = sticky.id
        except discord.Forbidden:
            return await ctx.send("I don't have permission to send messages or embeds there.")

        await ctx.send(
            f"Sticky embed set in {channel.mention}.",
            delete_after=5
        )

    @commands.command(name="unsticky")
    @commands.has_permissions(manage_messages=True)
    async def unsticky(self, ctx, channel: discord.TextChannel):
        """Remove a sticky message."""

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

        await ctx.send(f"Sticky embed removed from {channel.mention}.")

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
                embed = self.create_embed(sticky_text)
                new_sticky = await message.channel.send(embed=embed)
                self.sticky_ids[channel_id] = new_sticky.id
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(Sticky(bot))
