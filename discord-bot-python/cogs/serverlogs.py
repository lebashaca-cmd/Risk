import json
import os
from datetime import datetime, timezone
from typing import Union

import discord
from discord.ext import commands

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs_config.json")


def clip(text, limit=1000):
    text = text or "*empty*"
    return text if len(text) <= limit else text[:limit - 3] + "..."


class ServerLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self._load()

    def _load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def log_channel(self, guild):
        channel_id = self.config.get(str(guild.id))
        return guild.get_channel(channel_id) if channel_id else None

    async def send(self, guild, title, color, description=None, fields=(), user=None):
        channel = self.log_channel(guild)
        if channel is None:
            return
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        if user is not None:
            embed.set_author(name=str(user), icon_url=user.display_avatar.url)
            embed.set_footer(text=f"User ID: {user.id}")
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    def ignored_channel(self, channel):
        log = self.log_channel(channel.guild) if channel is not None else None
        return log is not None and log.id == channel.id

    @commands.command(name="logs")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def logs(self, ctx, target: Union[discord.TextChannel, str] = None):
        """Sets the server log channel (deletes, edits, voice, roles). Usage: ,logs #channel"""
        key = str(ctx.guild.id)

        if target is None:
            channel = self.log_channel(ctx.guild)
            if channel:
                await ctx.send(f"Server logs are going to {channel.mention}. Use `,logs off` to turn them off.")
            else:
                await ctx.send("Server logs are off. Use `,logs #channel` to turn them on.")
            return

        if isinstance(target, str):
            if target.lower() == "off":
                self.config.pop(key, None)
                self._save()
                await ctx.send("Server logs turned off.")
            else:
                await ctx.send("I couldn't find that channel. Use `,logs #channel` or `,logs off`.")
            return

        if not target.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(f"I can't send messages in {target.mention}.")
            return

        self.config[key] = target.id
        self._save()
        await ctx.send(f"Server logs will be sent to {target.mention}.")
        await self.send(
            ctx.guild,
            "Server Logs Enabled",
            discord.Color.green(),
            description=f"Set by {ctx.author.mention}.",
        )

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the Manage Server permission to use this.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command only works in a server.")
        else:
            raise error

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id) if guild else None
        if guild is None or channel is None or self.ignored_channel(channel):
            return

        message = payload.cached_message
        if message is None:
            await self.send(
                guild,
                "Message Deleted",
                discord.Color.red(),
                description=f"A message was deleted in {channel.mention}. The content isn't available.",
            )
            return
        if message.author.bot:
            return

        fields = [
            ("Channel", channel.mention, True),
            ("Author", message.author.mention, True),
            ("Content", clip(message.content), False),
        ]
        if message.attachments:
            fields.append(("Attachments", clip("\n".join(a.filename for a in message.attachments)), False))
        await self.send(guild, "Message Deleted", discord.Color.red(), fields=fields, user=message.author)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        channel = guild.get_channel(payload.channel_id) if guild else None
        if guild is None or channel is None or self.ignored_channel(channel):
            return
        await self.send(
            guild,
            "Messages Bulk Deleted",
            discord.Color.dark_red(),
            description=f"{len(payload.message_ids)} messages were deleted in {channel.mention}.",
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.guild is None or after.author.bot or before.content == after.content:
            return
        if self.ignored_channel(after.channel):
            return
        await self.send(
            after.guild,
            "Message Edited",
            discord.Color.orange(),
            fields=[
                ("Channel", after.channel.mention, True),
                ("Author", after.author.mention, True),
                ("Before", clip(before.content), False),
                ("After", clip(after.content), False),
                ("Jump", f"[Go to message]({after.jump_url})", False),
            ],
            user=after.author,
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or before.channel == after.channel:
            return
        if before.channel is None:
            title, color = "Joined Voice", discord.Color.green()
            text = f"{member.mention} joined {after.channel.mention}"
        elif after.channel is None:
            title, color = "Left Voice", discord.Color.red()
            text = f"{member.mention} left {before.channel.mention}"
        else:
            title, color = "Moved Voice", discord.Color.blue()
            text = f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}"
        await self.send(member.guild, title, color, description=text, user=member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]

        if added:
            await self.send(
                after.guild,
                "Role Added",
                discord.Color.green(),
                description=f"{after.mention} was given {', '.join(r.mention for r in added)}",
                user=after,
            )
        if removed:
            await self.send(
                after.guild,
                "Role Removed",
                discord.Color.red(),
                description=f"{after.mention} lost {', '.join(r.mention for r in removed)}",
                user=after,
            )
        if before.nick != after.nick:
            await self.send(
                after.guild,
                "Nickname Changed",
                discord.Color.blue(),
                fields=[
                    ("Before", before.nick or "*none*", True),
                    ("After", after.nick or "*none*", True),
                ],
                user=after,
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        created = int(member.created_at.timestamp())
        await self.send(
            member.guild,
            "Member Joined",
            discord.Color.green(),
            description=f"{member.mention} joined.\nAccount created <t:{created}:R>",
            user=member,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.send(
            member.guild,
            "Member Left",
            discord.Color.red(),
            description=f"{member.mention} left the server.",
            user=member,
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.send(guild, "Member Banned", discord.Color.dark_red(), description=f"{user.mention} was banned.", user=user)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.send(guild, "Member Unbanned", discord.Color.green(), description=f"{user.mention} was unbanned.", user=user)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.send(channel.guild, "Channel Created", discord.Color.green(), description=f"{channel.mention} (`{channel.name}`) was created.")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if self.ignored_channel(channel):
            self.config.pop(str(channel.guild.id), None)
            self._save()
            return
        await self.send(channel.guild, "Channel Deleted", discord.Color.red(), description=f"`#{channel.name}` was deleted.")


async def setup(bot):
    await bot.add_cog(ServerLogs(bot))
