from collections import deque
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

# Which log titles belong to which switchable category. Any other title is treated as moderation.
CATEGORIES = {
    "messages": ("Deleted, bulk-deleted and edited messages", {"Message Deleted", "Messages Bulk Deleted", "Message Edited"}),
    "voice": ("Joining, leaving and moving voice channels", {"Joined Voice", "Left Voice", "Moved Voice"}),
    "roles": ("Roles given or taken, and role changes", {"Role Added", "Role Removed", "Role Created", "Role Deleted", "Role Updated"}),
    "nicknames": ("Nickname changes", {"Nickname Changed"}),
    "members": ("Members joining and leaving", {"Member Joined", "Member Left"}),
    "bans": ("Bans and unbans", {"Member Banned", "Member Unbanned"}),
    "channels": ("Channels created, deleted or changed", {"Channel Created", "Channel Deleted", "Channel Updated", "Webhooks Updated"}),
    "emojis": ("Emoji changes", {"Emojis Updated"}),
    "invites": ("Invites created or deleted", {"Invite Created", "Invite Deleted"}),
    "threads": ("Threads created, changed or deleted", {"Thread Created", "Thread Updated", "Thread Deleted"}),
    "server": ("Server name, icon and settings", {"Server Updated"}),
    "timeouts": ("Timeouts and boosts", {"Member Timed Out", "Timeout Removed", "Server Boost", "Boost Removed"}),
    "moderation": ("Actions from moderation commands (warn, timeout, softban and more)", set()),
}
TITLE_TO_CATEGORY = {title: name for name, (_, titles) in CATEGORIES.items() for title in titles}
TITLE_TO_CATEGORY.update({"Log Test": "system", "Server Logs Enabled": "system"})


def short(value, limit=200):
    value = str(value)
    return value if len(value) <= limit else value[: limit - 3] + "..."


class LogTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("logtools")
        self.recent = {}

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Settings used by ServerLogs.send
    def cfg(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {})
        data.setdefault("off", [])
        data.setdefault("routes", {})
        data.setdefault("ignored", [])
        return data

    @staticmethod
    def category_for(title):
        return TITLE_TO_CATEGORY.get(title, "moderation")

    def enabled(self, guild_id, category):
        return category == "system" or category not in self.cfg(guild_id)["off"]

    def route(self, guild, category):
        channel_id = self.cfg(guild.id)["routes"].get(category)
        return guild.get_channel(channel_id) if channel_id else None

    def is_muted(self, channel):
        return channel is not None and channel.id in self.cfg(channel.guild.id)["ignored"]

    def record(self, guild_id, category, title, description, fields, user):
        text = description or " | ".join(f"{name}: {short(value, 80)}" for name, value, _ in fields)
        entry = {"at": int(datetime.now(timezone.utc).timestamp()), "category": category, "title": title, "text": short(text, 300), "user": user.id if user else None}
        self.recent.setdefault(guild_id, deque(maxlen=200)).append(entry)

    async def emit(self, guild, title, color, **kwargs):
        logs = self.bot.get_cog("ServerLogs")
        if logs is not None:
            await logs.send(guild, title, color, **kwargs)

    # Commands
    @commands.command(name="logevents")
    @commands.has_permissions(manage_guild=True)
    async def logevents(self, ctx):
        """Lists every log category and whether it's on. Usage: !logevents"""
        config = self.cfg(ctx.guild.id)
        lines = []
        for name, (text, _) in CATEGORIES.items():
            state = "🔴 off" if name in config["off"] else "🟢 on"
            routed = config["routes"].get(name)
            where = f" → <#{routed}>" if routed else ""
            lines.append(f"{state} **{name}**{where}\n{text}")
        embed = discord.Embed(title="Log categories", description="\n".join(lines), color=discord.Color.light_grey())
        embed.set_footer(text="!logtoggle <category> turns one off or on. !logchannel <category> #channel sends it elsewhere.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="logtoggle")
    @commands.has_permissions(manage_guild=True)
    async def logtoggle(self, ctx, category: str):
        """Turns a log category off or on. Usage: !logtoggle voice"""
        category = category.lower()
        if category not in CATEGORIES:
            await ctx.reply("Unknown category. See `!logevents`.", mention_author=False)
            return
        off = self.cfg(ctx.guild.id)["off"]
        if category in off:
            off.remove(category)
            state = "on"
        else:
            off.append(category)
            state = "off"
        self.store.save()
        await ctx.reply(f"**{category}** logs are now {state}.", mention_author=False)

    @commands.command(name="logchannel")
    @commands.has_permissions(manage_guild=True)
    async def logchannel(self, ctx, category: str, target: str):
        """Sends one log category to its own channel, or back to the main one with off. Usage: !logchannel voice #voice-logs"""
        category = category.lower()
        if category not in CATEGORIES:
            await ctx.reply("Unknown category. See `!logevents`.", mention_author=False)
            return
        routes = self.cfg(ctx.guild.id)["routes"]
        if target.lower() == "off":
            routes.pop(category, None)
            self.store.save()
            await ctx.reply(f"**{category}** logs go to the main log channel again.", mention_author=False)
            return
        try:
            channel = await commands.TextChannelConverter().convert(ctx, target)
        except commands.BadArgument:
            await ctx.reply("I couldn't find that channel. Use a #channel mention or `off`.", mention_author=False)
            return
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.reply(f"I can't send messages in {channel.mention}.", mention_author=False)
            return
        routes[category] = channel.id
        self.store.save()
        await ctx.reply(f"**{category}** logs will go to {channel.mention}.", mention_author=False)

    @commands.command(name="logignore")
    @commands.has_permissions(manage_guild=True)
    async def logignore(self, ctx, channel: discord.TextChannel):
        """Stops logging message edits and deletes in a channel. Usage: !logignore #staff-chat"""
        ignored = self.cfg(ctx.guild.id)["ignored"]
        if channel.id in ignored:
            await ctx.reply(f"{channel.mention} is already ignored.", mention_author=False)
            return
        ignored.append(channel.id)
        self.store.save()
        await ctx.reply(f"Message logs are off for {channel.mention}.", mention_author=False)

    @commands.command(name="logunignore")
    @commands.has_permissions(manage_guild=True)
    async def logunignore(self, ctx, channel: discord.TextChannel):
        """Starts logging message edits and deletes in a channel again. Usage: !logunignore #staff-chat"""
        ignored = self.cfg(ctx.guild.id)["ignored"]
        if channel.id not in ignored:
            await ctx.reply(f"{channel.mention} wasn't ignored.", mention_author=False)
            return
        ignored.remove(channel.id)
        self.store.save()
        await ctx.reply(f"Message logs are back on for {channel.mention}.", mention_author=False)

    @commands.command(name="logignored")
    @commands.has_permissions(manage_guild=True)
    async def logignored(self, ctx):
        """Lists the channels whose message logs are off. Usage: !logignored"""
        ignored = self.cfg(ctx.guild.id)["ignored"]
        text = "\n".join(f"<#{channel_id}>" for channel_id in ignored) or "None."
        await ctx.reply(embed=discord.Embed(title="Ignored channels", description=text, color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="logstatus")
    @commands.has_permissions(manage_guild=True)
    async def logstatus(self, ctx):
        """Shows the log channel and the current log settings. Usage: !logstatus"""
        logs = self.bot.get_cog("ServerLogs")
        main = logs.log_channel(ctx.guild) if logs else None
        config = self.cfg(ctx.guild.id)
        embed = discord.Embed(title="Log settings", color=discord.Color.light_grey())
        embed.add_field(name="Main channel", value=main.mention if main else "Not set. Use `!logs #channel`.")
        embed.add_field(name="Categories off", value=", ".join(config["off"]) or "None")
        embed.add_field(name="Own channels", value="\n".join(f"{name} → <#{cid}>" for name, cid in config["routes"].items()) or "None", inline=False)
        embed.add_field(name="Ignored channels", value=" ".join(f"<#{cid}>" for cid in config["ignored"]) or "None", inline=False)
        embed.add_field(name="Events remembered", value=str(len(self.recent.get(ctx.guild.id, []))))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="logtest")
    @commands.has_permissions(manage_guild=True)
    async def logtest(self, ctx):
        """Sends a test message to the log channel. Usage: !logtest"""
        logs = self.bot.get_cog("ServerLogs")
        if logs is None or logs.log_channel(ctx.guild) is None:
            await ctx.reply("No log channel is set. Use `!logs #channel` first.", mention_author=False)
            return
        await logs.send(ctx.guild, "Log Test", discord.Color.light_grey(), description=f"{ctx.author.mention} ran a log test. If you can read this, logging works.")
        await ctx.reply("Sent a test log.", mention_author=False)

    @commands.command(name="logreset")
    @commands.has_permissions(manage_guild=True)
    async def logreset(self, ctx, confirm: str = ""):
        """Resets categories, extra channels and ignored channels to the defaults. Usage: !logreset confirm"""
        if confirm.lower() != "confirm":
            await ctx.reply("This clears your category switches, extra log channels and ignored channels. Run `!logreset confirm` to continue.", mention_author=False)
            return
        self.store.data.pop(str(ctx.guild.id), None)
        self.store.save()
        await ctx.reply("Log settings reset. The main log channel is unchanged.", mention_author=False)

    @commands.command(name="logrecent")
    @commands.has_permissions(view_audit_log=True)
    async def logrecent(self, ctx, count: int = 10):
        """Shows the most recent logged events since the bot started. Usage: !logrecent 15"""
        entries = list(self.recent.get(ctx.guild.id, []))[-max(1, min(count, 25)):]
        await self.show_entries(ctx, "Recent events", entries[::-1])

    @commands.command(name="logsearch")
    @commands.has_permissions(view_audit_log=True)
    async def logsearch(self, ctx, *, text: str):
        """Searches recent logged events for some text. Usage: !logsearch deleted"""
        needle = text.lower()
        entries = [e for e in self.recent.get(ctx.guild.id, []) if needle in e["text"].lower() or needle in e["title"].lower() or needle in e["category"]]
        await self.show_entries(ctx, f"Events matching “{short(text, 40)}”", entries[-15:][::-1])

    @commands.command(name="loguser")
    @commands.has_permissions(view_audit_log=True)
    async def loguser(self, ctx, member: discord.User):
        """Shows recent logged events about a person. Usage: !loguser @user"""
        marker = str(member.id)
        entries = [e for e in self.recent.get(ctx.guild.id, []) if e["user"] == member.id or marker in e["text"]]
        await self.show_entries(ctx, f"Events for {member.display_name}", entries[-15:][::-1])

    async def show_entries(self, ctx, title, entries):
        if not entries:
            await ctx.reply("Nothing logged yet. Events are remembered while the bot is running (the last 200 per server).", mention_author=False)
            return
        lines = [f"<t:{e['at']}:t> **{e['title']}**: {e['text']}" for e in entries]
        await ctx.reply(embed=discord.Embed(title=title, description="\n".join(lines)[:4000], color=discord.Color.light_grey()), mention_author=False, allowed_mentions=NO_MENTIONS)

    # Extra events
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.emit(role.guild, "Role Created", discord.Color.green(), description=f"{role.mention} (`{role.name}`) was created.")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.emit(role.guild, "Role Deleted", discord.Color.red(), description=f"`{role.name}` was deleted.")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", False))
        if before.color != after.color:
            changes.append(("Color", f"{before.color} → {after.color}", True))
        if before.hoist != after.hoist:
            changes.append(("Shown separately", f"{before.hoist} → {after.hoist}", True))
        if before.mentionable != after.mentionable:
            changes.append(("Mentionable", f"{before.mentionable} → {after.mentionable}", True))
        if before.permissions != after.permissions:
            gained = [name for name, value in after.permissions if value and not getattr(before.permissions, name)]
            lost = [name for name, value in after.permissions if not value and getattr(before.permissions, name)]
            if gained:
                changes.append(("Permissions added", short(", ".join(gained), 900), False))
            if lost:
                changes.append(("Permissions removed", short(", ".join(lost), 900), False))
        if changes:
            await self.emit(after.guild, "Role Updated", discord.Color.orange(), description=after.mention, fields=changes)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", False))
        if getattr(before, "topic", None) != getattr(after, "topic", None):
            changes.append(("Topic", f"{short(getattr(before, 'topic', None) or 'none', 200)} → {short(getattr(after, 'topic', None) or 'none', 200)}", False))
        if getattr(before, "slowmode_delay", 0) != getattr(after, "slowmode_delay", 0):
            changes.append(("Slowmode", f"{before.slowmode_delay}s → {after.slowmode_delay}s", True))
        if getattr(before, "nsfw", False) != getattr(after, "nsfw", False):
            changes.append(("Age-restricted", f"{before.nsfw} → {after.nsfw}", True))
        if before.category != after.category:
            changes.append(("Category", f"{before.category} → {after.category}", True))
        if before.overwrites != after.overwrites:
            changes.append(("Permissions", "Permission overrides changed.", False))
        if changes:
            await self.emit(after.guild, "Channel Updated", discord.Color.orange(), description=after.mention, fields=changes)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        await self.emit(channel.guild, "Webhooks Updated", discord.Color.orange(), description=f"Webhooks changed in {channel.mention}.")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        old, new = {e.id: e for e in before}, {e.id: e for e in after}
        lines = [f"Added {new[i]} `{new[i].name}`" for i in new if i not in old]
        lines += [f"Removed `{old[i].name}`" for i in old if i not in new]
        lines += [f"Renamed `{old[i].name}` → `{new[i].name}`" for i in new if i in old and old[i].name != new[i].name]
        if lines:
            await self.emit(guild, "Emojis Updated", discord.Color.orange(), description="\n".join(lines)[:1900])

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild is None:
            return
        inviter = invite.inviter.mention if invite.inviter else "someone"
        limit = f"{invite.max_uses} uses" if invite.max_uses else "unlimited uses"
        await self.emit(invite.guild, "Invite Created", discord.Color.green(), description=f"{inviter} made invite `{invite.code}` for {invite.channel.mention} ({limit}).")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild is None:
            return
        await self.emit(invite.guild, "Invite Deleted", discord.Color.red(), description=f"Invite `{invite.code}` was deleted.")

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await self.emit(thread.guild, "Thread Created", discord.Color.green(), description=f"{thread.mention} was created in {thread.parent.mention if thread.parent else 'a channel'}.")

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        await self.emit(thread.guild, "Thread Deleted", discord.Color.red(), description=f"Thread `{thread.name}` was deleted.")

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", False))
        if before.archived != after.archived:
            changes.append(("Archived", f"{before.archived} → {after.archived}", True))
        if before.locked != after.locked:
            changes.append(("Locked", f"{before.locked} → {after.locked}", True))
        if changes:
            await self.emit(after.guild, "Thread Updated", discord.Color.orange(), description=after.mention, fields=changes)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        changes = []
        if before.name != after.name:
            changes.append(("Name", f"{before.name} → {after.name}", False))
        if before.icon != after.icon:
            changes.append(("Icon", "The server icon changed.", False))
        if before.banner != after.banner:
            changes.append(("Banner", "The server banner changed.", False))
        if before.verification_level != after.verification_level:
            changes.append(("Verification level", f"{before.verification_level} → {after.verification_level}", True))
        if before.afk_channel != after.afk_channel:
            changes.append(("AFK channel", f"{before.afk_channel} → {after.afk_channel}", True))
        if before.system_channel != after.system_channel:
            changes.append(("System channel", f"{before.system_channel} → {after.system_channel}", True))
        if before.owner_id != after.owner_id:
            changes.append(("Owner", f"<@{before.owner_id}> → <@{after.owner_id}>", False))
        if changes:
            await self.emit(after, "Server Updated", discord.Color.orange(), fields=changes)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                stamp = int(after.timed_out_until.timestamp())
                await self.emit(after.guild, "Member Timed Out", discord.Color.orange(), description=f"{after.mention} is timed out until <t:{stamp}:f> (<t:{stamp}:R>).", user=after)
            else:
                await self.emit(after.guild, "Timeout Removed", discord.Color.green(), description=f"{after.mention}'s timeout ended.", user=after)
        if before.premium_since != after.premium_since:
            if after.premium_since:
                await self.emit(after.guild, "Server Boost", discord.Color.purple(), description=f"{after.mention} boosted the server.", user=after)
            else:
                await self.emit(after.guild, "Boost Removed", discord.Color.dark_grey(), description=f"{after.mention} stopped boosting.", user=after)


async def setup(bot):
    await bot.add_cog(LogTools(bot))
