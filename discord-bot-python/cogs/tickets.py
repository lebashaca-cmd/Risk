import asyncio
import io
import json
import os
from datetime import datetime, timezone
from typing import Union

import discord
from discord.ext import commands

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "tickets_config.json")


class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:close",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if cog is None:
            await interaction.response.send_message("Tickets are unavailable right now.", ephemeral=True)
            return
        await cog.close_ticket(interaction)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = self._load()

    async def cog_load(self):
        self.bot.add_view(CloseView())

    def _load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def _guild(self, guild_id):
        data = self.config.setdefault(str(guild_id), {})
        data.setdefault("log_channel", None)
        data.setdefault("tickets", {})
        return data

    async def send_log(self, guild, embed, file=None):
        channel_id = self._guild(guild.id).get("log_channel")
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel is None:
            return
        try:
            await channel.send(embed=embed, file=file)
        except discord.HTTPException:
            pass

    @commands.command(name="ticket")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def ticket(
        self,
        ctx,
        category: discord.CategoryChannel,
        creator: discord.Member,
        staff: Union[discord.Role, discord.Member],
    ):
        """Opens a ticket. Usage: ,ticket "category_id" @creator @staff"""
        guild = ctx.guild

        access = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        )
        staff_access = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True,
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            creator: access,
            staff: staff_access,
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                embed_links=True,
            ),
        }

        name = f"ticket-{creator.name}"[:90]
        try:
            channel = await guild.create_text_channel(
                name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {creator} | opened by {ctx.author}",
                reason=f"Ticket opened by {ctx.author}",
            )
        except discord.Forbidden:
            await ctx.send("I don't have permission to create channels in that category.")
            return

        data = self._guild(guild.id)
        data["tickets"][str(channel.id)] = {
            "creator_id": creator.id,
            "staff_id": staff.id,
            "staff_type": "role" if isinstance(staff, discord.Role) else "member",
            "opened_by": ctx.author.id,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Welcome {creator.mention}!\n\n"
                f"{staff.mention} will be with you shortly. "
                "Please describe your issue in as much detail as you can.\n\n"
                "When this is resolved, press the button below to close the ticket."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Opened by {ctx.author}")
        await channel.send(content=f"{creator.mention} {staff.mention}", embed=embed, view=CloseView())

        await ctx.send(f"Ticket created: {channel.mention}")

        log = discord.Embed(title="Ticket Opened", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        log.add_field(name="Channel", value=channel.mention, inline=True)
        log.add_field(name="Creator", value=creator.mention, inline=True)
        log.add_field(name="Staff", value=staff.mention, inline=True)
        log.add_field(name="Opened by", value=ctx.author.mention, inline=True)
        await self.send_log(guild, log)

    async def close_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user
        data = self._guild(guild.id)
        record = data["tickets"].get(str(channel.id))

        allowed = user.guild_permissions.manage_channels
        if record:
            if user.id == record["creator_id"]:
                allowed = True
            elif record["staff_type"] == "role":
                allowed = allowed or any(r.id == record["staff_id"] for r in user.roles)
            else:
                allowed = allowed or user.id == record["staff_id"]

        if not allowed:
            await interaction.response.send_message("You can't close this ticket.", ephemeral=True)
            return

        closing = discord.Embed(
            title="🔒 Closing Ticket",
            description="This ticket will be deleted in 5 seconds.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=closing)

        lines = []
        async for message in channel.history(limit=None, oldest_first=True):
            stamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = message.clean_content
            if message.attachments:
                content += " " + " ".join(a.url for a in message.attachments)
            if not content and message.embeds:
                content = "[embed]"
            lines.append(f"[{stamp}] {message.author}: {content}")
        transcript = discord.File(io.BytesIO("\n".join(lines).encode("utf-8")), filename=f"{channel.name}.txt")

        log = discord.Embed(title="Ticket Closed", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        log.add_field(name="Ticket", value=f"#{channel.name}", inline=True)
        if record:
            log.add_field(name="Creator", value=f"<@{record['creator_id']}>", inline=True)
        log.add_field(name="Closed by", value=user.mention, inline=True)
        await self.send_log(guild, log, file=transcript)

        data["tickets"].pop(str(channel.id), None)
        self._save()

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket closed by {user}")
        except discord.HTTPException:
            pass

    @commands.command(name="setlogs")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setlogs(self, ctx, channel: discord.TextChannel):
        """Sets the log channel for tickets. Usage: ,setlogs #channel"""
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(f"I can't send messages in {channel.mention}.")
            return

        self._guild(ctx.guild.id)["log_channel"] = channel.id
        self._save()

        embed = discord.Embed(
            title="Log Channel Set",
            description=f"Ticket logs and transcripts will be sent here.\nSet by {ctx.author.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        await channel.send(embed=embed)
        await ctx.send(f"Log channel set to {channel.mention}.")

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use that command.")
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.BadUnionArgument)):
            await ctx.send(
                "Usage:\n"
                "`,ticket \"category_id\" @creator @staff`\n"
                "`,setlogs #channel`"
            )
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command only works in a server.")
        else:
            raise error


async def setup(bot):
    await bot.add_cog(Tickets(bot))
