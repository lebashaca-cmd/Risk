import asyncio
import time
from datetime import timedelta

import discord
from discord.ext import commands, tasks

from utils.helpers import NO_MENTIONS, Duration, ModError, explain_error, human_duration
from utils.store import JsonStore

MAX_TEMPBAN = timedelta(days=365)


class ConfirmView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.result = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the person who ran the command can answer.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        self.result = True
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        self.result = False
        await interaction.response.edit_message(view=None)
        self.stop()


class ModerationMore(commands.Cog):
    """Lockdowns, temporary bans, role and channel management, and voice moderation."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("tempbans")

    async def cog_load(self):
        self.unban_loop.start()

    def cog_unload(self):
        self.unban_loop.cancel()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Helpers
    def check_target(self, ctx, member):
        guild = ctx.guild
        if member.id == ctx.author.id:
            raise ModError("You can't do that to yourself.")
        if member.id == guild.me.id:
            raise ModError("I can't do that to myself.")
        if member.id == guild.owner_id:
            raise ModError("You can't target the server owner.")
        if ctx.author.id != guild.owner_id and member.top_role >= ctx.author.top_role:
            raise ModError("That member's top role is equal to or above yours.")
        if member.top_role >= guild.me.top_role:
            raise ModError("That member's top role is equal to or above mine.")

    def check_role(self, ctx, role):
        if role.is_default() or role.managed:
            raise ModError("I can't manage @everyone or bot-managed roles.")
        if role >= ctx.guild.me.top_role:
            raise ModError("That role is equal to or above my highest role.")
        if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
            raise ModError("That role is equal to or above your highest role.")

    async def modlog(self, ctx, action, target, reason, color=discord.Color.orange()):
        logs = self.bot.get_cog("ServerLogs")
        if logs is None:
            return
        try:
            await logs.send(ctx.guild, action, color, fields=[
                ("Moderator", ctx.author.mention, True),
                ("Target", getattr(target, "mention", str(target)), True),
                ("Reason", (reason or "No reason given")[:1000], False),
            ])
        except Exception:
            pass

    async def say(self, ctx, text):
        await ctx.send(text, allowed_mentions=NO_MENTIONS)

    async def confirm(self, ctx, question):
        view = ConfirmView(ctx.author.id)
        message = await ctx.reply(question, view=view, mention_author=False, allowed_mentions=NO_MENTIONS)
        await view.wait()
        try:
            await message.edit(content=question + ("\nConfirmed." if view.result else "\nCancelled." if view.result is False else "\nTimed out."), view=None)
        except discord.HTTPException:
            pass
        return bool(view.result)

    # Lockdown
    @commands.command(name="lockdown")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown(self, ctx, *, reason: str = "Server lockdown"):
        """Stops @everyone from sending messages in every text channel. Usage: !lockdown raid"""
        if not await self.confirm(ctx, f"Lock **every** text channel for @everyone? Reason: {reason[:200]}"):
            return
        everyone = ctx.guild.default_role
        done = failed = 0
        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).manage_roles:
                failed += 1
                continue
            overwrite = channel.overwrites_for(everyone)
            if overwrite.send_messages is False:
                continue
            overwrite.send_messages = False
            try:
                await channel.set_permissions(everyone, overwrite=overwrite, reason=f"{ctx.author}: {reason}")
                done += 1
            except discord.HTTPException:
                failed += 1
        await self.say(ctx, f"🔒 Locked {done} channel(s)." + (f" {failed} could not be changed." if failed else "") + " Undo with `!unlockdown`.")
        await self.modlog(ctx, "Server Lockdown", ctx.guild.default_role, reason)

    @commands.command(name="unlockdown")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockdown(self, ctx, *, reason: str = "Lockdown ended"):
        """Lets @everyone send messages again in every text channel. Usage: !unlockdown"""
        if not await self.confirm(ctx, "Unlock every text channel for @everyone?"):
            return
        everyone = ctx.guild.default_role
        done = 0
        for channel in ctx.guild.text_channels:
            overwrite = channel.overwrites_for(everyone)
            if overwrite.send_messages is not False or not channel.permissions_for(ctx.guild.me).manage_roles:
                continue
            overwrite.send_messages = None
            try:
                await channel.set_permissions(everyone, overwrite=None if overwrite.is_empty() else overwrite, reason=f"{ctx.author}: {reason}")
                done += 1
            except discord.HTTPException:
                pass
        await self.say(ctx, f"🔓 Unlocked {done} channel(s).")
        await self.modlog(ctx, "Lockdown Ended", ctx.guild.default_role, reason, discord.Color.green())

    # Temporary bans
    @commands.command(name="tempban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def tempban(self, ctx, member: discord.Member, duration: Duration, *, reason: str = "No reason given"):
        """Bans a member and unbans them automatically later. Usage: !tempban @user 3d reason"""
        self.check_target(ctx, member)
        if duration > MAX_TEMPBAN:
            raise ModError("Temporary bans can last up to 365 days.")
        try:
            await member.send(f"You were banned from **{ctx.guild.name}** for {human_duration(duration)}. Reason: {reason}")
        except discord.HTTPException:
            pass
        await ctx.guild.ban(member, reason=f"Tempban by {ctx.author}: {reason}", delete_message_days=0)
        self.store.data.setdefault(str(ctx.guild.id), {})[str(member.id)] = int(time.time() + duration.total_seconds())
        self.store.save()
        await self.say(ctx, f"Banned {member.mention} for {human_duration(duration)}. Reason: {reason}")
        await self.modlog(ctx, "Member Banned", member, f"Temporary, {human_duration(duration)}: {reason}", discord.Color.red())

    @commands.command(name="tempbans")
    @commands.has_permissions(ban_members=True)
    async def tempbans(self, ctx):
        """Lists the temporary bans that will end on their own. Usage: !tempbans"""
        entries = self.store.data.get(str(ctx.guild.id), {})
        if not entries:
            await ctx.reply("There are no temporary bans.", mention_author=False)
            return
        lines = [f"<@{uid}> (`{uid}`) ends <t:{when}:R>" for uid, when in sorted(entries.items(), key=lambda x: x[1])[:30]]
        await ctx.reply(embed=discord.Embed(title="Temporary bans", description="\n".join(lines), color=discord.Color.red()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @tasks.loop(minutes=1)
    async def unban_loop(self):
        now = time.time()
        changed = False
        for guild_id, entries in list(self.store.data.items()):
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue
            for uid, when in list(entries.items()):
                if when > now:
                    continue
                try:
                    await guild.unban(discord.Object(int(uid)), reason="Temporary ban ended")
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    continue
                entries.pop(uid, None)
                changed = True
        if changed:
            self.store.save()

    @unban_loop.before_loop
    async def before_unban(self):
        await self.bot.wait_until_ready()

    # Bulk role changes
    async def bulk_role(self, ctx, role, add, include_bots):
        self.check_role(ctx, role)
        targets = [m for m in ctx.guild.members if (include_bots or not m.bot) and ((role not in m.roles) if add else (role in m.roles))]
        if not targets:
            raise ModError("Nobody needs a change.")
        if len(targets) > 1000:
            raise ModError("That would change more than 1,000 members. Do it in smaller groups.")
        verb = "Give" if add else "Remove"
        if not await self.confirm(ctx, f"{verb} **{role.name}** {'to' if add else 'from'} {len(targets)} member(s)? This takes about {len(targets) // 2 + 1} seconds."):
            return
        done = 0
        for member in targets:
            try:
                if add:
                    await member.add_roles(role, reason=f"Roleall by {ctx.author}")
                else:
                    await member.remove_roles(role, reason=f"Unroleall by {ctx.author}")
                done += 1
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.5)
        await self.say(ctx, f"Changed {done} of {len(targets)} member(s).")
        await self.modlog(ctx, "Bulk Role Change", role, f"{verb} {done} member(s) by {ctx.author}")

    @commands.command(name="roleall")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def roleall(self, ctx, role: discord.Role, include_bots: bool = False):
        """Gives a role to every member who doesn't have it. Usage: !roleall @Member"""
        await self.bulk_role(ctx, role, True, include_bots)

    @commands.command(name="unroleall")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unroleall(self, ctx, role: discord.Role, include_bots: bool = False):
        """Takes a role away from every member who has it. Usage: !unroleall @Member"""
        await self.bulk_role(ctx, role, False, include_bots)

    # Roles
    @commands.command(name="createrole")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def createrole(self, ctx, *, name: str):
        """Creates a role with no permissions. Usage: !createrole Event Team"""
        if len(name) > 100:
            raise ModError("Role names can be up to 100 characters.")
        if len(ctx.guild.roles) >= 250:
            raise ModError("This server has reached the 250 role limit.")
        role = await ctx.guild.create_role(name=name, reason=f"Created by {ctx.author}")
        await self.say(ctx, f"Created {role.mention}.")
        await self.modlog(ctx, "Role Created", role, f"By {ctx.author}", discord.Color.green())

    @commands.command(name="deleterole", aliases=["delrole"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def deleterole(self, ctx, *, role: discord.Role):
        """Deletes a role. Usage: !deleterole @Old Role"""
        self.check_role(ctx, role)
        name = role.name
        await role.delete(reason=f"Deleted by {ctx.author}")
        await self.say(ctx, f"Deleted the role **{discord.utils.escape_markdown(name)}**.")
        await self.modlog(ctx, "Role Deleted", name, f"By {ctx.author}", discord.Color.red())

    @commands.command(name="rolecolor", aliases=["rolecolour"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rolecolor(self, ctx, role: discord.Role, color: discord.Color):
        """Changes a role's color. Usage: !rolecolor @Member #ff8800"""
        self.check_role(ctx, role)
        await role.edit(color=color, reason=f"Color changed by {ctx.author}")
        await self.say(ctx, f"Changed the color of {role.mention} to `{color}`.")

    @commands.command(name="rolename")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rolename(self, ctx, role: discord.Role, *, name: str):
        """Renames a role. Usage: !rolename @Member Verified Member"""
        self.check_role(ctx, role)
        if len(name) > 100:
            raise ModError("Role names can be up to 100 characters.")
        await role.edit(name=name, reason=f"Renamed by {ctx.author}")
        await self.say(ctx, f"Renamed the role to {role.mention}.")

    # Channels
    @commands.command(name="createchannel", aliases=["makechannel"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def createchannel(self, ctx, kind: str, *, name: str):
        """Creates a text or voice channel. Usage: !createchannel text general-2"""
        kind = kind.lower()
        if kind not in ("text", "voice"):
            raise ModError("Pick `text` or `voice`.")
        if len(ctx.guild.channels) >= 500:
            raise ModError("This server has reached the 500 channel limit.")
        category = ctx.channel.category
        if kind == "text":
            channel = await ctx.guild.create_text_channel(name[:100], category=category, reason=f"Created by {ctx.author}")
        else:
            channel = await ctx.guild.create_voice_channel(name[:100], category=category, reason=f"Created by {ctx.author}")
        await self.say(ctx, f"Created {channel.mention}.")
        await self.modlog(ctx, "Channel Created", channel, f"By {ctx.author}", discord.Color.green())

    @commands.command(name="deletechannel", aliases=["delchannel"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def deletechannel(self, ctx, channel: discord.abc.GuildChannel = None):
        """Deletes a channel (this one if you name none) after you confirm. Usage: !deletechannel #old-chat"""
        channel = channel or ctx.channel
        if channel in (ctx.guild.rules_channel, ctx.guild.public_updates_channel):
            raise ModError("That channel is required by Community settings.")
        if not await self.confirm(ctx, f"Delete **#{channel.name}** for good?"):
            return
        name = channel.name
        await channel.delete(reason=f"Deleted by {ctx.author}")
        if channel.id != ctx.channel.id:
            await self.say(ctx, f"Deleted **#{name}**.")
        await self.modlog(ctx, "Channel Deleted", f"#{name}", f"By {ctx.author}", discord.Color.red())

    @commands.command(name="renamechannel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def renamechannel(self, ctx, channel: discord.abc.GuildChannel, *, name: str):
        """Renames a channel. Usage: !renamechannel #general chat-room"""
        await channel.edit(name=name[:100], reason=f"Renamed by {ctx.author}")
        await self.say(ctx, f"Renamed it to {channel.mention}.")

    @commands.command(name="settopic")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def settopic(self, ctx, *, topic: str):
        """Sets this channel's topic, or use `clear` to remove it. Usage: !settopic Daily chat"""
        if len(topic) > 1024:
            raise ModError("Topics can be up to 1,024 characters.")
        await ctx.channel.edit(topic=None if topic.lower() == "clear" else topic, reason=f"Topic set by {ctx.author}")
        await self.say(ctx, "Topic cleared." if topic.lower() == "clear" else "Topic updated.")

    @commands.command(name="clonechannel")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def clonechannel(self, ctx, channel: discord.TextChannel = None):
        """Makes a copy of a text channel with the same permissions. Usage: !clonechannel #general"""
        channel = channel or ctx.channel
        copy = await channel.clone(reason=f"Cloned by {ctx.author}")
        await self.say(ctx, f"Cloned into {copy.mention}.")

    # Voice moderation
    async def voice_change(self, ctx, member, text, color=discord.Color.orange(), **changes):
        self.check_target(ctx, member)
        if member.voice is None:
            raise ModError("That member isn't in a voice channel.")
        await member.edit(reason=f"{ctx.author}", **changes)
        await self.say(ctx, text.format(member=member.mention))
        await self.modlog(ctx, "Voice Moderation", member, text.format(member=member.display_name), color)

    @commands.command(name="vcmute")
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def vcmute(self, ctx, member: discord.Member):
        """Server-mutes a member in voice. Usage: !vcmute @user"""
        await self.voice_change(ctx, member, "Muted {member} in voice.", mute=True)

    @commands.command(name="vcunmute")
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def vcunmute(self, ctx, member: discord.Member):
        """Removes a server mute in voice. Usage: !vcunmute @user"""
        await self.voice_change(ctx, member, "Unmuted {member} in voice.", discord.Color.green(), mute=False)

    @commands.command(name="vcdeafen")
    @commands.has_permissions(deafen_members=True)
    @commands.bot_has_permissions(deafen_members=True)
    async def vcdeafen(self, ctx, member: discord.Member):
        """Server-deafens a member in voice. Usage: !vcdeafen @user"""
        await self.voice_change(ctx, member, "Deafened {member} in voice.", deafen=True)

    @commands.command(name="vcundeafen")
    @commands.has_permissions(deafen_members=True)
    @commands.bot_has_permissions(deafen_members=True)
    async def vcundeafen(self, ctx, member: discord.Member):
        """Removes a server deafen in voice. Usage: !vcundeafen @user"""
        await self.voice_change(ctx, member, "Undeafened {member} in voice.", discord.Color.green(), deafen=False)

    @commands.command(name="vcmove")
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def vcmove(self, ctx, member: discord.Member, channel: discord.VoiceChannel):
        """Moves a member to another voice channel. Usage: !vcmove @user General"""
        if not channel.permissions_for(ctx.guild.me).connect:
            raise ModError("I can't connect to that channel.")
        await self.voice_change(ctx, member, f"Moved {{member}} to {channel.name}.", voice_channel=channel)

    @commands.command(name="vcmuteall")
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def vcmuteall(self, ctx, mute: bool = True):
        """Mutes or unmutes everyone in your voice channel except you. Usage: !vcmuteall on"""
        if ctx.author.voice is None:
            raise ModError("Join a voice channel first.")
        count = 0
        for member in ctx.author.voice.channel.members:
            if member.id == ctx.author.id or member.bot:
                continue
            if member.guild_permissions.administrator and ctx.author.id != ctx.guild.owner_id:
                continue
            try:
                await member.edit(mute=mute, reason=f"{ctx.author}")
                count += 1
            except discord.HTTPException:
                pass
        await self.say(ctx, f"{'Muted' if mute else 'Unmuted'} {count} member(s).")

    @commands.command(name="vcdisconnectall", aliases=["vcclear"])
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def vcdisconnectall(self, ctx):
        """Disconnects everyone from your voice channel except you. Usage: !vcdisconnectall"""
        if ctx.author.voice is None:
            raise ModError("Join a voice channel first.")
        if not await self.confirm(ctx, f"Disconnect everyone else from **{ctx.author.voice.channel.name}**?"):
            return
        count = 0
        for member in list(ctx.author.voice.channel.members):
            if member.id == ctx.author.id:
                continue
            try:
                await member.move_to(None, reason=f"Disconnected by {ctx.author}")
                count += 1
            except discord.HTTPException:
                pass
        await self.say(ctx, f"Disconnected {count} member(s).")

    # Bans
    @commands.command(name="unbanall")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unbanall(self, ctx):
        """Unbans everyone in this server after you confirm. Usage: !unbanall"""
        bans = [entry async for entry in ctx.guild.bans(limit=2000)]
        if not bans:
            raise ModError("Nobody is banned.")
        if not await self.confirm(ctx, f"Unban all **{len(bans)}** banned user(s)? This can't be undone."):
            return
        done = 0
        for entry in bans:
            try:
                await ctx.guild.unban(entry.user, reason=f"Unbanall by {ctx.author}")
                done += 1
            except discord.HTTPException:
                pass
            await asyncio.sleep(0.4)
        await self.say(ctx, f"Unbanned {done} of {len(bans)} user(s).")
        await self.modlog(ctx, "Mass Unban", f"{done} user(s)", f"By {ctx.author}", discord.Color.green())

    @commands.command(name="resetnick")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnick(self, ctx, member: discord.Member):
        """Clears a member's nickname. Usage: !resetnick @user"""
        self.check_target(ctx, member)
        if member.nick is None:
            raise ModError("That member has no nickname.")
        await member.edit(nick=None, reason=f"Reset by {ctx.author}")
        await self.say(ctx, f"Cleared the nickname of {member.mention}.")

    @commands.command(name="addrole", aliases=["giverole"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def addrole(self, ctx, member: discord.Member, *, role: discord.Role):
        """Gives one role to a member. Usage: !addrole @user @Member"""
        self.check_role(ctx, role)
        if role in member.roles:
            raise ModError("They already have that role.")
        await member.add_roles(role, reason=f"Added by {ctx.author}")
        await self.say(ctx, f"Gave {role.mention} to {member.mention}.")
        await self.modlog(ctx, "Role Added", member, f"{role.name} by {ctx.author}", discord.Color.green())


async def setup(bot):
    await bot.add_cog(ModerationMore(bot))
