import time
from datetime import timedelta

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, Duration, ModError, explain_error, human_duration, parse_duration
from utils.store import JsonStore

MAX_TIMEOUT = timedelta(days=28)


class ModerationTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warns = JsonStore("warnings")

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

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

    async def modlog(self, ctx, action, target, reason, color=discord.Color.orange()):
        logs = self.bot.get_cog("ServerLogs")
        if logs is None:
            return
        try:
            await logs.send(
                ctx.guild,
                action,
                color,
                fields=[
                    ("Moderator", ctx.author.mention, True),
                    ("Target", getattr(target, "mention", str(target)), True),
                    ("Reason", (reason or "No reason given")[:1000], False),
                ],
            )
        except Exception:
            pass

    async def dm(self, member, text):
        try:
            await member.send(text)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def say(self, ctx, text):
        await ctx.send(text, allowed_mentions=NO_MENTIONS)

    @commands.command(name="timeout", aliases=["mute"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: Duration, *, reason: str = "No reason given"):
        """Times a member out so they can't talk. Usage: !timeout @user 10m reason"""
        self.check_target(ctx, member)
        if duration > MAX_TIMEOUT:
            raise ModError("Discord caps timeouts at 28 days.")
        await member.timeout(duration, reason=f"{ctx.author}: {reason}")
        await self.dm(member, f"You were timed out in **{ctx.guild.name}** for {human_duration(duration)}. Reason: {reason}")
        await self.say(ctx, f"Timed out {member.mention} for {human_duration(duration)}. Reason: {reason}")
        await self.modlog(ctx, "Member Timed Out", member, f"{human_duration(duration)}: {reason}")

    @commands.command(name="untimeout", aliases=["unmute"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason: str = "No reason given"):
        """Removes a timeout from a member. Usage: !untimeout @user"""
        if not member.is_timed_out():
            raise ModError("That member isn't timed out.")
        await member.timeout(None, reason=f"{ctx.author}: {reason}")
        await self.say(ctx, f"Removed the timeout from {member.mention}.")
        await self.modlog(ctx, "Timeout Removed", member, reason, discord.Color.green())

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason given"):
        """Warns a member and records it. Usage: !warn @user reason"""
        self.check_target(ctx, member)
        guild_warns = self.warns.data.setdefault(str(ctx.guild.id), {})
        entries = guild_warns.setdefault(str(member.id), [])
        next_id = max((w["id"] for w in entries), default=0) + 1
        entries.append({"id": next_id, "mod": ctx.author.id, "reason": reason[:500], "at": int(time.time())})
        self.warns.save()
        await self.dm(member, f"You were warned in **{ctx.guild.name}**. Reason: {reason}")
        await self.say(ctx, f"Warned {member.mention} (warning #{next_id}, {len(entries)} total). Reason: {reason}")
        await self.modlog(ctx, "Member Warned", member, reason)

    @commands.command(name="warnings", aliases=["warns"])
    @commands.has_permissions(manage_messages=True)
    async def warnings(self, ctx, member: discord.Member):
        """Lists the warnings a member has. Usage: !warnings @user"""
        entries = self.warns.data.get(str(ctx.guild.id), {}).get(str(member.id), [])
        if not entries:
            await self.say(ctx, f"{member.mention} has no warnings.")
            return
        lines = [f"**#{w['id']}** <t:{w['at']}:d> by <@{w['mod']}>: {w['reason']}" for w in entries[-15:]]
        embed = discord.Embed(title=f"Warnings for {member}", description="\n".join(lines)[:4000], color=discord.Color.orange())
        embed.set_footer(text=f"{len(entries)} total")
        await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)

    @commands.command(name="delwarn")
    @commands.has_permissions(manage_messages=True)
    async def delwarn(self, ctx, member: discord.Member, number: int):
        """Removes one warning by its number. Usage: !delwarn @user 2"""
        entries = self.warns.data.get(str(ctx.guild.id), {}).get(str(member.id), [])
        kept = [w for w in entries if w["id"] != number]
        if len(kept) == len(entries):
            raise ModError(f"{member} has no warning #{number}.")
        self.warns.data[str(ctx.guild.id)][str(member.id)] = kept
        self.warns.save()
        await self.say(ctx, f"Removed warning #{number} from {member.mention}.")

    @commands.command(name="clearwarnings", aliases=["clearwarns"])
    @commands.has_permissions(manage_guild=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        """Clears every warning for a member. Usage: !clearwarnings @user"""
        removed = self.warns.data.get(str(ctx.guild.id), {}).pop(str(member.id), [])
        self.warns.save()
        await self.say(ctx, f"Cleared {len(removed)} warning(s) for {member.mention}.")

    @commands.command(name="softban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def softban(self, ctx, member: discord.Member, *, reason: str = "No reason given"):
        """Bans and unbans a member to delete their recent messages. Usage: !softban @user reason"""
        self.check_target(ctx, member)
        await ctx.guild.ban(member, reason=f"Softban by {ctx.author}: {reason}", delete_message_seconds=86400)
        await ctx.guild.unban(member, reason="Softban")
        await self.say(ctx, f"Softbanned {member.mention}. Their last day of messages was removed.")
        await self.modlog(ctx, "Member Softbanned", member, reason)

    @commands.command(name="idban", aliases=["hackban"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def idban(self, ctx, user_id: int, *, reason: str = "No reason given"):
        """Bans someone by ID, even if they aren't in the server. Usage: !idban 123456789 reason"""
        if user_id in (ctx.author.id, ctx.guild.owner_id, ctx.guild.me.id):
            raise ModError("You can't ban that user.")
        member = ctx.guild.get_member(user_id)
        if member is not None:
            self.check_target(ctx, member)
        await ctx.guild.ban(discord.Object(id=user_id), reason=f"{ctx.author}: {reason}")
        await self.say(ctx, f"Banned user `{user_id}`. Reason: {reason}")
        await self.modlog(ctx, "Member Banned (by ID)", f"`{user_id}`", reason, discord.Color.red())

    @commands.command(name="banlist", aliases=["bans"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def banlist(self, ctx):
        """Shows the first 25 banned users. Usage: !banlist"""
        lines = []
        async for entry in ctx.guild.bans(limit=25):
            reason = (entry.reason or "no reason")[:60]
            lines.append(f"`{entry.user.id}` {discord.utils.escape_markdown(str(entry.user))}: {reason}")
        if not lines:
            await self.say(ctx, "Nobody is banned.")
            return
        await ctx.send(embed=discord.Embed(title="Bans", description="\n".join(lines)[:4000], color=discord.Color.red()))

    @commands.command(name="removerole", aliases=["rr"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def removerole(self, ctx, member: discord.Member, *, role: discord.Role):
        """Takes a role away from a member. Usage: !removerole @user Role"""
        if role not in member.roles:
            raise ModError("They don't have that role.")
        if role.managed or role >= ctx.guild.me.top_role:
            raise ModError("I can't remove that role. It's managed or above my top role.")
        if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
            raise ModError("That role is equal to or above your top role.")
        await member.remove_roles(role, reason=f"Removed by {ctx.author}")
        await self.say(ctx, f"Removed **{role.name}** from {member.mention}.")

    @commands.command(name="nick")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        """Changes or resets a member's nickname. Usage: !nick @user New Name"""
        if member.id != ctx.author.id:
            self.check_target(ctx, member)
        if nickname and len(nickname) > 32:
            raise ModError("Nicknames can be at most 32 characters.")
        await member.edit(nick=nickname, reason=f"Nickname by {ctx.author}")
        await self.say(ctx, f"Nickname for {member.mention} {'set to **' + nickname + '**' if nickname else 'reset'}.")

    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, amount: str = "off", channel: discord.TextChannel = None):
        """Sets slowmode in a channel, or turns it off. Usage: !slowmode 10s or !slowmode off"""
        channel = channel or ctx.channel
        if amount.lower() in ("off", "0", "none"):
            seconds = 0
        else:
            delta = parse_duration(amount) if not amount.isdigit() else timedelta(seconds=int(amount))
            if delta is None:
                raise ModError("Use `off` or a time like `10s`, `5m` or `1h`.")
            seconds = int(delta.total_seconds())
        if seconds > 21600:
            raise ModError("Slowmode can be at most 6 hours.")
        await channel.edit(slowmode_delay=seconds, reason=f"Slowmode by {ctx.author}")
        await self.say(ctx, f"Slowmode in {channel.mention} is {'off' if not seconds else human_duration(seconds)}.")

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        """Stops @everyone from sending messages in a channel. Usage: !lock #channel"""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Locked by {ctx.author}")
        await self.say(ctx, f"Locked {channel.mention}.")

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        """Lets @everyone send messages in a channel again. Usage: !unlock #channel"""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Unlocked by {ctx.author}")
        await self.say(ctx, f"Unlocked {channel.mention}.")

    @commands.command(name="purgeuser")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purgeuser(self, ctx, member: discord.Member, amount: int = 50):
        """Deletes one member's recent messages from this channel. Usage: !purgeuser @user 50"""
        amount = max(1, min(amount, 500))
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.id == member.id)
        await ctx.send(f"Deleted {len(deleted)} message(s) from {member.display_name}.", delete_after=5, allowed_mentions=NO_MENTIONS)

    @commands.command(name="purgebots")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def purgebots(self, ctx, amount: int = 50):
        """Deletes recent messages sent by bots. Usage: !purgebots 50"""
        amount = max(1, min(amount, 500))
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.bot)
        await ctx.send(f"Deleted {len(deleted)} bot message(s).", delete_after=5)

    @commands.command(name="vckick")
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def vckick(self, ctx, member: discord.Member):
        """Disconnects a member from voice. Usage: !vckick @user"""
        self.check_target(ctx, member)
        if member.voice is None:
            raise ModError("They aren't in a voice channel.")
        await member.move_to(None, reason=f"Voice kick by {ctx.author}")
        await self.say(ctx, f"Disconnected {member.mention} from voice.")


async def setup(bot):
    await bot.add_cog(ModerationTools(bot))
