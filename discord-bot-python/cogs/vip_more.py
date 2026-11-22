"""Even more VIP commands, grouped by the plan that unlocks them.

Basic (every VIP plan): inrole.
White (White and Supreme): honeypot, stickyroles, joingate, viplog.
Supreme: massrole, exportmembers.

Each command calls `VIP.need(ctx, group)`, so a server on a lower plan is told which plan it needs.
"""
import asyncio
import csv
import io
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

TRAP_ACTIONS = ("ban", "kick", "timeout", "softban")
STICKY_CAP = 5000
# Roles with these permissions are never given back automatically when someone returns.
RISKY = ("administrator", "manage_guild", "manage_roles", "manage_channels", "manage_webhooks", "ban_members", "kick_members", "mention_everyone", "manage_messages")


class VIPMore(commands.Cog, name="VIPMore"):
    """More VIP commands: a honeypot trap channel, sticky roles, an account-age gate and bulk tools."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("vip_more")
        for key in ("honeypot", "sticky", "joingate", "log"):
            self.store.data.setdefault(key, {})
        self.busy = set()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Helpers
    @property
    def vip(self):
        cog = self.bot.get_cog("VIP")
        if cog is None:
            raise ModError("VIP isn't loaded right now.")
        return cog

    def need(self, ctx, group):
        self.vip.need(ctx, group)

    def active(self, guild_id, group="white"):
        """True when the server's plan still includes `group`. Automatic tools stop quietly when VIP ends."""
        vip = self.bot.get_cog("VIP")
        return vip is not None and vip.is_vip(guild_id) and vip.has(guild_id, group)

    async def note(self, guild, title, text, colour=discord.Color.orange()):
        """Posts to the server's VIP log channel (set with !viplog), if there is one."""
        channel_id = self.store.data["log"].get(str(guild.id))
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel is None:
            return
        embed = discord.Embed(title=title, description=text[:3500], color=colour, timestamp=datetime.now(timezone.utc))
        try:
            await channel.send(embed=embed, allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            pass

    @staticmethod
    def exempt(member):
        perms = member.guild_permissions
        return member.id == member.guild.owner_id or perms.administrator or perms.manage_guild or perms.ban_members or perms.manage_messages

    # ------------------------------------------------------------------ Basic
    @commands.command(name="vipinrole")
    @commands.guild_only()
    async def vipinrole(self, ctx, *, role: discord.Role):
        """VIP. Lists the members who have a role. Usage: !vipinrole @Moderators"""
        self.need(ctx, "basic")
        members = sorted(role.members, key=lambda m: m.display_name.lower())
        if not members:
            raise ModError("Nobody has that role.")
        shown = "\n".join(f"{m.display_name} (`{m.name}`)" for m in members[:40])
        more = f"\n...and {len(members) - 40} more." if len(members) > 40 else ""
        embed = discord.Embed(title=f"{role.name}: {len(members)} member(s)", description=shown + more, color=role.color if role.color.value else self.vip.embed_color(ctx.guild.id) or discord.Color.gold())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ------------------------------------------------------------------ White: log channel
    @commands.command(name="viplog")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def viplog(self, ctx, channel: str = ""):
        """VIP White. Chooses the channel where the honeypot, join gate and sticky roles report what they did. Usage: !viplog #staff-log | off"""
        self.need(ctx, "white")
        key = str(ctx.guild.id)
        if channel.lower() == "off":
            self.store.data["log"].pop(key, None)
            self.store.save()
            await ctx.reply("These tools will no longer post a log.", mention_author=False)
            return
        if not channel:
            current = self.store.data["log"].get(key)
            await ctx.reply(f"Log channel: {f'<#{current}>' if current else 'none'}. Use `{ctx.clean_prefix}viplog #channel` or `off`.", mention_author=False)
            return
        target = await commands.TextChannelConverter().convert(ctx, channel)
        if not target.permissions_for(ctx.guild.me).send_messages:
            raise ModError("I can't send messages in that channel.")
        self.store.data["log"][key] = target.id
        self.store.save()
        await ctx.reply(f"Logging to {target.mention}.", mention_author=False)

    # ------------------------------------------------------------------ White: honeypot
    @commands.group(name="honeypot", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def honeypot(self, ctx):
        """VIP White. A trap channel: anyone who posts in it is punished straight away, which catches spam bots and raiders. Usage: !honeypot create | set #channel [ban|kick|timeout|softban] | action <type> | off | status"""
        self.need(ctx, "white")
        await self.honeypot_status(ctx)

    @honeypot.command(name="create")
    @commands.has_permissions(manage_guild=True)
    async def honeypot_create(self, ctx, action: str = "ban"):
        """Makes a #do-not-post channel and turns it into the trap. Usage: !honeypot create [ban|kick|timeout|softban]"""
        self.need(ctx, "white")
        if not ctx.guild.me.guild_permissions.manage_channels:
            raise ModError("I need the Manage Channels permission to create the channel. You can also make one yourself and use `honeypot set #channel`.")
        action = self.check_action(action)
        channel = await ctx.guild.create_text_channel("do-not-post", reason=f"Honeypot made by {ctx.author}")
        await self.arm(ctx, channel, action)

    @honeypot.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def honeypot_set(self, ctx, channel: discord.TextChannel, action: str = "ban"):
        """Uses an existing channel as the trap. Usage: !honeypot set #channel [ban|kick|timeout|softban]"""
        self.need(ctx, "white")
        await self.arm(ctx, channel, self.check_action(action))

    @staticmethod
    def check_action(action):
        action = action.lower()
        if action not in TRAP_ACTIONS:
            raise ModError("The action must be one of: " + ", ".join(f"`{a}`" for a in TRAP_ACTIONS) + ".")
        return action

    async def arm(self, ctx, channel, action):
        me = ctx.guild.me.guild_permissions
        needed = {"ban": me.ban_members, "softban": me.ban_members, "kick": me.kick_members, "timeout": me.moderate_members}[action]
        if not needed:
            raise ModError(f"I don't have the permission I need to {action} members.")
        if not channel.permissions_for(ctx.guild.me).manage_messages:
            raise ModError("I need Manage Messages in that channel so I can delete what gets posted.")
        entry = self.store.data["honeypot"].setdefault(str(ctx.guild.id), {"caught": 0})
        entry.update({"channel": channel.id, "action": action})
        self.store.save()
        verbs = {"ban": "banned", "softban": "banned and unbanned (their last hour of messages is deleted)", "kick": "kicked", "timeout": "timed out for 28 days"}
        try:
            await channel.send(f"**Do not post in this channel.** Anyone who sends a message here is automatically {verbs[action]}. It is a trap for spam bots and raiders. Moderators are never affected.")
        except discord.HTTPException:
            pass
        await ctx.reply(f"{channel.mention} is now the honeypot. Anyone who posts there will be {verbs[action]}. Staff with Manage Messages or higher are skipped. Tip: put it near the top of the channel list and use `{ctx.clean_prefix}viplog #channel` to get a report each time it catches someone.", mention_author=False)

    @honeypot.command(name="action")
    @commands.has_permissions(manage_guild=True)
    async def honeypot_action(self, ctx, action: str):
        """Changes what happens to whoever posts. Usage: !honeypot action ban|kick|timeout|softban"""
        self.need(ctx, "white")
        entry = self.store.data["honeypot"].get(str(ctx.guild.id))
        if not entry:
            raise ModError("There is no honeypot yet. Use `honeypot create` or `honeypot set #channel`.")
        entry["action"] = self.check_action(action)
        self.store.save()
        await ctx.reply(f"The honeypot will now **{entry['action']}** whoever posts in it.", mention_author=False)

    @honeypot.command(name="off")
    @commands.has_permissions(manage_guild=True)
    async def honeypot_off(self, ctx):
        """Turns the honeypot off. The channel stays. Usage: !honeypot off"""
        self.need(ctx, "white")
        if self.store.data["honeypot"].pop(str(ctx.guild.id), None) is None:
            raise ModError("There is no honeypot.")
        self.store.save()
        await ctx.reply("The honeypot is off. The channel is still there, so delete it if you don't need it.", mention_author=False)

    @honeypot.command(name="status")
    @commands.has_permissions(manage_guild=True)
    async def honeypot_status(self, ctx):
        """Shows the trap channel, the action and how many it has caught. Usage: !honeypot status"""
        self.need(ctx, "white")
        entry = self.store.data["honeypot"].get(str(ctx.guild.id))
        if not entry:
            await ctx.reply(f"There is no honeypot. Use `{ctx.clean_prefix}honeypot create` to make a trap channel, or `{ctx.clean_prefix}honeypot set #channel` to use one you have.", mention_author=False)
            return
        log = self.store.data["log"].get(str(ctx.guild.id))
        await ctx.reply(f"Honeypot: <#{entry['channel']}>. Action: **{entry['action']}**. Caught so far: **{entry['caught']}**. Log: {f'<#{log}>' if log else 'none (set one with viplog)'}.", mention_author=False)

    @commands.Cog.listener("on_message")
    async def trap(self, message):
        if message.guild is None or message.author.bot or message.webhook_id:
            return
        entry = self.store.data["honeypot"].get(str(message.guild.id))
        if not entry or entry["channel"] != message.channel.id or not self.active(message.guild.id):
            return
        member = message.author
        if not isinstance(member, discord.Member) or self.exempt(member):
            return
        me = message.guild.me
        if member.top_role >= me.top_role:
            await self.note(message.guild, "Honeypot: could not act", f"{member.mention} posted in the honeypot, but their top role is not below mine.")
            return
        action = entry["action"]
        reason = f"Posted in the honeypot channel (#{message.channel.name})"
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        if action in ("kick", "timeout", "softban"):
            try:
                await member.send(f"You were removed from **{message.guild.name}** for posting in a trap channel that says not to post there. If this was a mistake, ask a moderator to let you back in.")
            except discord.HTTPException:
                pass
        try:
            if action == "ban":
                await message.guild.ban(member, reason=reason, delete_message_seconds=3600)
            elif action == "softban":
                await message.guild.ban(member, reason=reason, delete_message_seconds=3600)
                await message.guild.unban(member, reason="Honeypot softban")
            elif action == "kick":
                await member.kick(reason=reason)
            else:
                await member.timeout(timedelta(days=28), reason=reason)
        except discord.HTTPException as error:
            await self.note(message.guild, "Honeypot: action failed", f"{member.mention} posted in the honeypot, but I couldn't {action} them: {error}")
            return
        entry["caught"] += 1
        self.store.save()
        await self.note(message.guild, f"Honeypot caught someone ({action})", f"**{member}** (`{member.id}`)\nAccount created <t:{int(member.created_at.timestamp())}:R>\nMessage: {message.content[:300] or '(no text)'}")

    # ------------------------------------------------------------------ White: sticky roles
    @commands.command(name="stickyroles")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def stickyroles(self, ctx, state: str = "status"):
        """VIP White. Gives members their roles back when they rejoin. Roles with moderator permissions are never restored. Usage: !stickyroles on | off | clear | status"""
        self.need(ctx, "white")
        entry = self.store.data["sticky"].setdefault(str(ctx.guild.id), {"on": False, "roles": {}})
        state = state.lower()
        if state == "on":
            entry["on"] = True
            text = "Members who leave and come back get their roles back (except roles with moderator permissions)."
        elif state == "off":
            entry["on"] = False
            text = "Sticky roles are off."
        elif state == "clear":
            entry["roles"] = {}
            text = "Forgot every saved role."
        else:
            await ctx.reply(f"Sticky roles are **{'on' if entry['on'] else 'off'}**. Remembering roles for {len(entry['roles'])} member(s) who left.", mention_author=False)
            return
        self.store.save()
        await ctx.reply(text, mention_author=False)

    @commands.Cog.listener("on_member_remove")
    async def remember_roles(self, member):
        entry = self.store.data["sticky"].get(str(member.guild.id))
        if not entry or not entry["on"] or member.bot:
            return
        ids = [r.id for r in member.roles if not r.is_default() and not r.managed]
        if not ids:
            return
        entry["roles"].pop(str(member.id), None)
        entry["roles"][str(member.id)] = ids
        while len(entry["roles"]) > STICKY_CAP:
            entry["roles"].pop(next(iter(entry["roles"])))
        self.store.save()

    @commands.Cog.listener("on_member_join")
    async def restore_roles(self, member):
        entry = self.store.data["sticky"].get(str(member.guild.id))
        if not entry or not entry["on"] or member.bot or not self.active(member.guild.id):
            return
        ids = entry["roles"].pop(str(member.id), None)
        if not ids:
            return
        me = member.guild.me
        roles = []
        for role_id in ids:
            role = member.guild.get_role(role_id)
            if role is None or role.managed or role >= me.top_role or any(getattr(role.permissions, p) for p in RISKY):
                continue
            roles.append(role)
        self.store.save()
        if roles:
            try:
                await member.add_roles(*roles, reason="Sticky roles: restored after rejoining")
            except discord.HTTPException:
                return
            await self.note(member.guild, "Sticky roles restored", f"{member.mention} got back: {', '.join(r.name for r in roles)}", discord.Color.green())

    # ------------------------------------------------------------------ White: join gate
    @commands.command(name="joingate")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def joingate(self, ctx, days: str = "status", action: str = "kick"):
        """VIP White. Stops brand-new accounts: anyone whose Discord account is younger than N days is kicked (or only reported with `warn`). Usage: !joingate 7 | !joingate 7 warn | off | status"""
        self.need(ctx, "white")
        key = str(ctx.guild.id)
        if days.lower() == "off":
            self.store.data["joingate"].pop(key, None)
            self.store.save()
            await ctx.reply("The join gate is off.", mention_author=False)
            return
        if days.lower() == "status":
            entry = self.store.data["joingate"].get(key)
            if not entry:
                state = "off"
            elif entry["action"] == "kick":
                state = "accounts younger than **%d day(s)** are kicked" % entry["days"]
            else:
                state = "accounts younger than **%d day(s)** are reported" % entry["days"]
            await ctx.reply(f"Join gate: {state}. Set it with `{ctx.clean_prefix}joingate 7`.", mention_author=False)
            return
        if not days.isdigit() or not 1 <= int(days) <= 365:
            raise ModError("Give a number of days between 1 and 365, or `off`.")
        action = action.lower()
        if action not in ("kick", "warn"):
            raise ModError("The action is `kick` or `warn`.")
        if action == "kick" and not ctx.guild.me.guild_permissions.kick_members:
            raise ModError("I need the Kick Members permission for that.")
        self.store.data["joingate"][key] = {"days": int(days), "action": action}
        self.store.save()
        await ctx.reply(f"New members whose account is under **{days} day(s)** old will be {'kicked (they get a message first)' if action == 'kick' else 'reported to your viplog channel'}.", mention_author=False)

    @commands.Cog.listener("on_member_join")
    async def gate(self, member):
        entry = self.store.data["joingate"].get(str(member.guild.id))
        if not entry or member.bot or not self.active(member.guild.id):
            return
        age = (datetime.now(timezone.utc) - member.created_at).total_seconds() / 86400
        if age >= entry["days"]:
            return
        text = f"{member.mention} (`{member.id}`) has an account that is {age:.1f} day(s) old, under the {entry['days']}-day limit."
        if entry["action"] == "warn":
            await self.note(member.guild, "Join gate: new account", text)
            return
        try:
            await member.send(f"**{member.guild.name}** only lets in Discord accounts that are at least {entry['days']} days old. Yours is {age:.1f} days old, so you were removed. You are welcome to join again later.")
        except discord.HTTPException:
            pass
        try:
            await member.kick(reason=f"Join gate: account under {entry['days']} days old")
        except discord.HTTPException as error:
            await self.note(member.guild, "Join gate: could not kick", f"{text} I couldn't kick them: {error}")
            return
        await self.note(member.guild, "Join gate: kicked", text)

    # ------------------------------------------------------------------ Supreme
    @commands.group(name="massrole", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def massrole(self, ctx):
        """VIP Supreme. Gives a role to, or takes it from, many members at once. Usage: !massrole give @role [humans|bots|all] confirm | take @role [humans|bots|all] confirm"""
        self.need(ctx, "supreme")
        await ctx.reply("Use `massrole give @role [humans|bots|all]` or `massrole take @role [humans|bots|all]`. It shows how many members it would change and waits for you to repeat the command with `confirm` on the end.", mention_author=False)

    @massrole.command(name="give")
    @commands.has_permissions(manage_roles=True)
    async def massrole_give(self, ctx, role: discord.Role, who: str = "humans", confirm: str = ""):
        """Gives a role to everyone in a group. Usage: !massrole give @role humans confirm"""
        await self.mass(ctx, role, who, confirm, give=True)

    @massrole.command(name="take")
    @commands.has_permissions(manage_roles=True)
    async def massrole_take(self, ctx, role: discord.Role, who: str = "humans", confirm: str = ""):
        """Takes a role from everyone in a group. Usage: !massrole take @role humans confirm"""
        await self.mass(ctx, role, who, confirm, give=False)

    async def mass(self, ctx, role, who, confirm, give):
        self.need(ctx, "supreme")
        who = who.lower()
        if who == "confirm":
            who, confirm = "humans", "confirm"
        if who not in ("humans", "bots", "all"):
            raise ModError("Pick `humans`, `bots` or `all`.")
        if role.is_default() or role.managed:
            raise ModError("That role can't be given or taken.")
        if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
            raise ModError("That role is at or above your highest role.")
        if role >= ctx.guild.me.top_role:
            raise ModError("That role is above my highest role, so I can't manage it.")
        if ctx.guild.id in self.busy:
            raise ModError("A mass role change is already running here.")
        if not ctx.guild.chunked:
            await ctx.guild.chunk()
        pool = [m for m in ctx.guild.members if who == "all" or (m.bot if who == "bots" else not m.bot)]
        targets = [m for m in pool if (role not in m.roles) == give]
        if not targets:
            raise ModError(f"Nobody in that group needs the change: everyone already {'has' if give else 'lacks'} {role.name}.")
        verb = "give" if give else "take"
        if confirm.lower() != "confirm":
            await ctx.reply(f"This would {verb} **{role.name}** {'to' if give else 'from'} **{len(targets)}** member(s). Run it again with `confirm` on the end to do it: `{ctx.clean_prefix}massrole {verb} {role.name} {who} confirm`.", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        self.busy.add(ctx.guild.id)
        done = failed = 0
        started = await ctx.reply(f"Working on {len(targets)} member(s). This takes about {max(1, len(targets) // 2)} second(s).", mention_author=False)
        try:
            for member in targets:
                try:
                    if give:
                        await member.add_roles(role, reason=f"Mass role by {ctx.author}")
                    else:
                        await member.remove_roles(role, reason=f"Mass role by {ctx.author}")
                    done += 1
                except discord.HTTPException:
                    failed += 1
                await asyncio.sleep(0.5)
        finally:
            self.busy.discard(ctx.guild.id)
        await started.edit(content=f"Done. {done} member(s) changed" + (f", {failed} failed." if failed else "."))

    @commands.command(name="exportmembers")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def exportmembers(self, ctx):
        """VIP Supreme. Sends you a spreadsheet (CSV) of every member: id, name, when they joined, account age and roles. It goes to your DMs. Usage: !exportmembers"""
        self.need(ctx, "supreme")
        if not ctx.guild.chunked:
            await ctx.guild.chunk()
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["id", "username", "display_name", "bot", "joined_at", "account_created", "roles"])
        for m in sorted(ctx.guild.members, key=lambda m: m.joined_at or datetime.now(timezone.utc)):
            writer.writerow([m.id, str(m), m.display_name, int(m.bot), m.joined_at.isoformat() if m.joined_at else "", m.created_at.isoformat(), ";".join(r.name for r in m.roles if not r.is_default())])
        data = out.getvalue().encode("utf-8-sig")
        if len(data) > 8 * 1024 * 1024:
            raise ModError("That server is too big to export in one file.")
        file = discord.File(io.BytesIO(data), filename=f"members-{ctx.guild.id}-{int(time.time())}.csv")
        try:
            await ctx.author.send(f"Member list for **{ctx.guild.name}** ({ctx.guild.member_count} members). It contains personal data, so keep it private.", file=file)
        except discord.HTTPException:
            raise ModError("I couldn't DM you. Open your DMs for this server and try again. I don't post the list in a channel because it is private.")
        await ctx.reply("Sent to your DMs.", mention_author=False)


async def setup(bot):
    await bot.add_cog(VIPMore(bot))
