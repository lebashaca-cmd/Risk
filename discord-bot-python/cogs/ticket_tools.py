import asyncio
import io
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error

PRIORITIES = {
    "low": ("🟢", discord.Color.green()),
    "normal": ("🔵", discord.Color.blue()),
    "high": ("🟠", discord.Color.orange()),
    "urgent": ("🔴", discord.Color.red()),
}


class TicketTools(commands.Cog):
    """Staff tools that work inside the ticket channels made by the Tickets cog."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if self.bot.get_cog("Tickets") is None:
            await ctx.reply("Tickets aren't loaded right now.", mention_author=False)
            return False
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Helpers
    @property
    def tickets(self):
        return self.bot.get_cog("Tickets")

    def data(self, guild):
        return self.tickets._guild(guild.id)

    def record_for(self, channel):
        return self.data(channel.guild)["tickets"].get(str(channel.id))

    @staticmethod
    def is_staff(member, record):
        if member.guild_permissions.manage_channels:
            return True
        if record is None:
            return False
        if record["staff_type"] == "role":
            return any(role.id == record["staff_id"] for role in member.roles)
        return member.id == record["staff_id"]

    async def in_ticket(self, ctx, channel=None, staff=True):
        """Returns the ticket record for the channel, or None after replying why not."""
        channel = channel or ctx.channel
        record = self.record_for(channel)
        if record is None:
            await ctx.reply("That isn't a ticket channel.", mention_author=False)
            return None
        if staff and not self.is_staff(ctx.author, record):
            await ctx.reply("Only ticket staff can do that.", mention_author=False)
            return None
        return record

    async def transcript(self, channel):
        lines = []
        async for message in channel.history(limit=None, oldest_first=True):
            stamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = message.clean_content
            if message.attachments:
                content += " " + " ".join(a.url for a in message.attachments)
            if not content and message.embeds:
                content = "[embed]"
            lines.append(f"[{stamp}] {message.author}: {content}")
        return discord.File(io.BytesIO("\n".join(lines).encode("utf-8")), filename=f"{channel.name}.txt")

    async def refresh_topic(self, channel, record):
        parts = [f"Ticket for <@{record['creator_id']}>"]
        if record.get("claimed_by"):
            parts.append(f"claimed by <@{record['claimed_by']}>")
        if record.get("priority"):
            parts.append(f"priority: {record['priority']}")
        try:
            await channel.edit(topic=" | ".join(parts)[:1000])
        except discord.HTTPException:
            pass

    # Members and access
    @commands.command(name="ticketadd")
    async def ticketadd(self, ctx, member: discord.Member):
        """Adds someone to the current ticket. Usage: !ticketadd @user"""
        if await self.in_ticket(ctx) is None:
            return
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
        await ctx.reply(f"Added {member.mention} to this ticket.", mention_author=False, allowed_mentions=discord.AllowedMentions(users=[member]))

    @commands.command(name="ticketremove")
    async def ticketremove(self, ctx, member: discord.Member):
        """Removes someone from the current ticket. Usage: !ticketremove @user"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        if member.id == record["creator_id"]:
            await ctx.reply("You can't remove the person who opened the ticket. Close it instead.", mention_author=False)
            return
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.reply(f"Removed {member.display_name} from this ticket.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="ticketlock")
    async def ticketlock(self, ctx):
        """Stops the ticket's opener from sending messages. Usage: !ticketlock"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        creator = ctx.guild.get_member(record["creator_id"])
        if creator is None:
            await ctx.reply("The person who opened this ticket isn't in the server.", mention_author=False)
            return
        await ctx.channel.set_permissions(creator, view_channel=True, send_messages=False, read_message_history=True)
        await ctx.reply("🔒 Ticket locked. Use `!ticketunlock` to let them reply again.", mention_author=False)

    @commands.command(name="ticketunlock")
    async def ticketunlock(self, ctx):
        """Lets the ticket's opener send messages again. Usage: !ticketunlock"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        creator = ctx.guild.get_member(record["creator_id"])
        if creator is None:
            await ctx.reply("The person who opened this ticket isn't in the server.", mention_author=False)
            return
        await ctx.channel.set_permissions(creator, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
        await ctx.reply("🔓 Ticket unlocked.", mention_author=False)

    @commands.command(name="ticketping")
    async def ticketping(self, ctx):
        """Pings the ticket's opener to ask for a reply. Usage: !ticketping"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        user = discord.Object(record["creator_id"])
        await ctx.send(f"<@{record['creator_id']}>, staff are waiting for your reply in this ticket.", allowed_mentions=discord.AllowedMentions(users=[user]))

    # Ownership and status
    @commands.command(name="ticketclaim")
    async def ticketclaim(self, ctx):
        """Claims the current ticket so others know you're handling it. Usage: !ticketclaim"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        if record.get("claimed_by") and record["claimed_by"] != ctx.author.id:
            await ctx.reply(f"<@{record['claimed_by']}> already claimed this ticket.", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        record["claimed_by"] = ctx.author.id
        self.tickets._save()
        await ctx.reply(embed=discord.Embed(description=f"{ctx.author.mention} claimed this ticket.", color=discord.Color.green()), mention_author=False)
        await self.refresh_topic(ctx.channel, record)

    @commands.command(name="ticketunclaim")
    async def ticketunclaim(self, ctx):
        """Releases your claim on the current ticket. Usage: !ticketunclaim"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        if not record.get("claimed_by"):
            await ctx.reply("Nobody has claimed this ticket.", mention_author=False)
            return
        if record["claimed_by"] != ctx.author.id and not ctx.author.guild_permissions.manage_channels:
            await ctx.reply("Only the person who claimed it, or a channel manager, can release it.", mention_author=False)
            return
        record.pop("claimed_by", None)
        self.tickets._save()
        await ctx.reply("Ticket released. Anyone on staff can claim it.", mention_author=False)
        await self.refresh_topic(ctx.channel, record)

    @commands.command(name="ticketpriority")
    async def ticketpriority(self, ctx, level: str):
        """Sets the ticket priority: low, normal, high or urgent. Usage: !ticketpriority high"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        level = level.lower()
        if level not in PRIORITIES:
            await ctx.reply("Pick one of: " + ", ".join(f"`{name}`" for name in PRIORITIES) + ".", mention_author=False)
            return
        record["priority"] = level
        self.tickets._save()
        emoji, color = PRIORITIES[level]
        await ctx.reply(embed=discord.Embed(description=f"{emoji} Priority set to **{level}** by {ctx.author.mention}.", color=color), mention_author=False)
        await self.refresh_topic(ctx.channel, record)

    @commands.command(name="ticketrename")
    async def ticketrename(self, ctx, *, name: str):
        """Renames the current ticket channel. Usage: !ticketrename billing-issue"""
        if await self.in_ticket(ctx) is None:
            return
        slug = "-".join("".join(ch for ch in name.lower() if ch.isalnum() or ch in " -_").split())[:90]
        if not slug:
            await ctx.reply("Give a name using letters or numbers.", mention_author=False)
            return
        try:
            await ctx.channel.edit(name=slug)
        except discord.HTTPException:
            await ctx.reply("Discord limits how often a channel can be renamed. Try again in a few minutes.", mention_author=False)
            return
        await ctx.reply(f"Renamed this ticket to **{slug}**.", mention_author=False)

    # Notes
    @commands.command(name="ticketnote")
    async def ticketnote(self, ctx, *, text: str):
        """Saves a private staff note on the ticket and hides your message. Usage: !ticketnote customer wants a refund"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        notes = record.setdefault("notes", [])
        if len(notes) >= 25:
            await ctx.reply("This ticket already has 25 notes.", mention_author=False)
            return
        notes.append({"by": ctx.author.id, "text": text[:500], "at": datetime.now(timezone.utc).isoformat()})
        self.tickets._save()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(f"📝 Note {len(notes)} saved. Staff can read notes with `!ticketnotes` (sent by direct message).")

    @commands.command(name="ticketnotes")
    async def ticketnotes(self, ctx):
        """Sends you this ticket's staff notes by direct message. Usage: !ticketnotes"""
        record = await self.in_ticket(ctx)
        if record is None:
            return
        notes = record.get("notes", [])
        if not notes:
            await ctx.reply("This ticket has no notes.", mention_author=False)
            return
        lines = []
        for index, note in enumerate(notes, start=1):
            stamp = int(datetime.fromisoformat(note["at"]).timestamp())
            lines.append(f"**{index}.** <t:{stamp}:f> by <@{note['by']}>\n{note['text']}")
        embed = discord.Embed(title=f"Notes for #{ctx.channel.name}", description="\n\n".join(lines)[:4000], color=discord.Color.light_grey())
        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            await ctx.reply("I couldn't message you. Turn on direct messages from this server and try again.", mention_author=False)
            return
        await ctx.reply("I sent you the notes in a direct message.", mention_author=False)

    # Information
    @commands.command(name="ticketinfo")
    async def ticketinfo(self, ctx, channel: discord.TextChannel = None):
        """Shows details about a ticket. Usage: !ticketinfo #ticket-name"""
        channel = channel or ctx.channel
        record = await self.in_ticket(ctx, channel)
        if record is None:
            return
        opened = int(datetime.fromisoformat(record["opened_at"]).timestamp())
        embed = discord.Embed(title=f"#{channel.name}", color=discord.Color.blurple())
        embed.add_field(name="Opened by", value=f"<@{record['creator_id']}>")
        embed.add_field(name="Opened", value=f"<t:{opened}:R>")
        embed.add_field(name="Claimed by", value=f"<@{record['claimed_by']}>" if record.get("claimed_by") else "Nobody")
        priority = record.get("priority", "normal")
        embed.add_field(name="Priority", value=f"{PRIORITIES[priority][0]} {priority}")
        embed.add_field(name="Notes", value=str(len(record.get("notes", []))))
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="tickets", aliases=["opentickets"])
    @commands.has_permissions(manage_channels=True)
    async def tickets_list(self, ctx):
        """Lists the open tickets in this server. Usage: !tickets"""
        records = self.data(ctx.guild)["tickets"]
        rows = []
        for channel_id, record in records.items():
            channel = ctx.guild.get_channel(int(channel_id))
            if channel is None:
                continue
            priority = record.get("priority", "normal")
            claimed = f"<@{record['claimed_by']}>" if record.get("claimed_by") else "unclaimed"
            rows.append(f"{PRIORITIES[priority][0]} {channel.mention} by <@{record['creator_id']}>, {claimed}")
        if not rows:
            await ctx.reply("There are no open tickets.", mention_author=False)
            return
        embed = discord.Embed(title=f"Open tickets ({len(rows)})", description="\n".join(rows[:20]), color=discord.Color.blurple())
        if len(rows) > 20:
            embed.set_footer(text=f"Showing 20 of {len(rows)}.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="ticketstats")
    @commands.has_permissions(manage_channels=True)
    async def ticketstats(self, ctx):
        """Shows a summary of open tickets. Usage: !ticketstats"""
        records = [r for cid, r in self.data(ctx.guild)["tickets"].items() if ctx.guild.get_channel(int(cid))]
        claimed = sum(1 for r in records if r.get("claimed_by"))
        by_priority = {name: sum(1 for r in records if r.get("priority", "normal") == name) for name in PRIORITIES}
        embed = discord.Embed(title="Ticket summary", color=discord.Color.blurple())
        embed.add_field(name="Open", value=str(len(records)))
        embed.add_field(name="Claimed", value=str(claimed))
        embed.add_field(name="Unclaimed", value=str(len(records) - claimed))
        embed.add_field(name="By priority", value="\n".join(f"{PRIORITIES[n][0]} {n}: {c}" for n, c in by_priority.items()), inline=False)
        embed.add_field(name="Panels", value=str(len(self.data(ctx.guild)["panels"])))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="transcript")
    async def transcript_command(self, ctx):
        """Sends a text transcript of the current ticket without closing it. Usage: !transcript"""
        if await self.in_ticket(ctx) is None:
            return
        await ctx.reply("Here's the transcript so far.", file=await self.transcript(ctx.channel), mention_author=False)

    # Closing and panels
    @commands.command(name="ticketclose", aliases=["closeticket"])
    async def ticketclose(self, ctx, *, reason: str = "No reason given"):
        """Closes the current ticket with a reason and saves a transcript to the log channel. Usage: !ticketclose resolved"""
        record = self.record_for(ctx.channel)
        if record is None:
            await ctx.reply("That isn't a ticket channel.", mention_author=False)
            return
        if ctx.author.id != record["creator_id"] and not self.is_staff(ctx.author, record):
            await ctx.reply("You can't close this ticket.", mention_author=False)
            return
        await ctx.send(embed=discord.Embed(title="🔒 Closing Ticket", description=f"{reason[:500]}\n\nThis ticket will be deleted in 5 seconds.", color=discord.Color.red()))
        log = discord.Embed(title="Ticket Closed", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        log.add_field(name="Ticket", value=f"#{ctx.channel.name}")
        log.add_field(name="Creator", value=f"<@{record['creator_id']}>")
        log.add_field(name="Closed by", value=ctx.author.mention)
        log.add_field(name="Reason", value=reason[:1000], inline=False)
        if record.get("claimed_by"):
            log.add_field(name="Handled by", value=f"<@{record['claimed_by']}>")
        await self.tickets.send_log(ctx.guild, log, file=await self.transcript(ctx.channel))
        self.data(ctx.guild)["tickets"].pop(str(ctx.channel.id), None)
        self.tickets._save()
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}: {reason[:100]}")
        except discord.HTTPException:
            pass

    @commands.command(name="ticketpanels")
    @commands.has_permissions(manage_guild=True)
    async def ticketpanels(self, ctx):
        """Lists the ticket panels that are active. Usage: !ticketpanels"""
        panels = self.data(ctx.guild)["panels"]
        if not panels:
            await ctx.reply("There are no ticket panels. Post one with `!ticket`.", mention_author=False)
            return
        lines = []
        for message_id, panel in panels.items():
            category = ctx.guild.get_channel(panel["category_id"])
            staff = f"<@&{panel['staff_id']}>" if panel["staff_type"] == "role" else f"<@{panel['staff_id']}>"
            lines.append(f"`{message_id}`: tickets go in **{category.name if category else 'a deleted category'}**, staff {staff}")
        await ctx.reply(embed=discord.Embed(title="Ticket panels", description="\n".join(lines[:20]), color=discord.Color.blurple()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="delpanel")
    @commands.has_permissions(manage_guild=True)
    async def delpanel(self, ctx, message_id: int):
        """Turns off a ticket panel by its message ID. Usage: !delpanel 123456789012345678"""
        panels = self.data(ctx.guild)["panels"]
        if str(message_id) not in panels:
            await ctx.reply("No panel has that message ID. See `!ticketpanels`.", mention_author=False)
            return
        panels.pop(str(message_id))
        self.tickets._save()
        await ctx.reply("That panel is turned off. Its button will say it's no longer active.", mention_author=False)


async def setup(bot):
    await bot.add_cog(TicketTools(bot))
