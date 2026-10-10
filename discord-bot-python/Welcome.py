import json
import os

import discord
from discord.ext import commands

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "welcome_config.json")
PLACEHOLDER = "New_user"


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self._load()

    # ---------- storage ----------
    def _load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    @staticmethod
    def _format(text: str, member: discord.Member) -> str:
        return text.replace(PLACEHOLDER, member.mention)

    # ---------- command ----------
    @commands.command(name="welcome")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx, channel_id: int, *, text: str):
        """Set the welcome message. Usage: ?welcome 123456789 Welcome New_user to Risk
        'New_user' is replaced with a mention of the member who joins."""
        channel = ctx.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await ctx.send("I couldn't find a text channel with that ID in this server.")
            return

        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(f"I don't have permission to send messages in {channel.mention}.")
            return

        self.config[str(ctx.guild.id)] = {"channel_id": channel_id, "text": text}
        self._save()

        await ctx.send(
            f"Welcome message set for {channel.mention}.\n"
            f"Preview: {self._format(text, ctx.author)}"
        )

    @welcome.error
    async def welcome_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the Manage Server permission to use this.")
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send("Usage: `?welcome <channel_id> <text>` — example: "
                           "`?welcome 123456789 Welcome New_user to Risk`")
        else:
            raise error

    # ---------- event ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = self.config.get(str(member.guild.id))
        if not settings:
            return
        channel = member.guild.get_channel(settings["channel_id"])
        if channel is None:
            return
        try:
            await channel.send(self._format(settings["text"], member))
        except discord.Forbidden:
            pass


async def setup(bot):
    await bot.add_cog(Welcome(bot))