import re
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
REPORT_COOLDOWN = 300


def parse_day(text):
    """Accepts MM-DD or MM/DD. Returns (month, day) or None."""
    match = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})", text.strip())
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12 or not 1 <= day <= MONTH_DAYS[month - 1]:
        return None
    return month, day


def pretty(month, day):
    return f"{MONTHS[month - 1]} {day}"


def next_occurrence(month, day, today):
    for year in (today.year, today.year + 1):
        try:
            candidate = datetime(year, month, day, tzinfo=timezone.utc).date()
        except ValueError:  # Feb 29 in a non-leap year
            continue
        if candidate >= today.date():
            return candidate
    return None


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, emoji="✅", custom_id="community:verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("CommunityExtra")
        if cog is None:
            await interaction.response.send_message("Verification is unavailable right now.", ephemeral=True)
            return
        await cog.handle_verify(interaction)


class CommunityExtra(commands.Cog):
    """Birthdays, staff notes, reports, a counting game, server rules and a verify button."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("community_extra")
        self.report_times = {}

    async def cog_load(self):
        self.bot.add_view(VerifyView())
        self.birthday_loop.start()

    def cog_unload(self):
        self.birthday_loop.cancel()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def cfg(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {})
        data.setdefault("birthdays", {})
        data.setdefault("birthday_channel", None)
        data.setdefault("last_birthday_check", "")
        data.setdefault("notes", {})
        data.setdefault("report_channel", None)
        data.setdefault("rules", "")
        data.setdefault("verify", {})
        data.setdefault("counting", {"channel": None, "number": 0, "last": None, "best": 0})
        return data

    async def channel_from(self, ctx, target):
        try:
            return await commands.TextChannelConverter().convert(ctx, target)
        except commands.BadArgument:
            return None

    # Birthdays
    @commands.group(name="birthday", aliases=["bday"], invoke_without_command=True)
    async def birthday(self, ctx, member: discord.Member = None):
        """Shows a member's birthday. Also: set, remove, list, next. Usage: !birthday @user"""
        member = member or ctx.author
        entry = self.cfg(ctx.guild.id)["birthdays"].get(str(member.id))
        if not entry:
            await ctx.reply(f"{member.display_name} hasn't set a birthday. Use `!birthday set 05-17`.", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        await ctx.reply(f"🎂 {member.display_name}'s birthday is **{pretty(entry['month'], entry['day'])}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @birthday.command(name="set")
    async def birthday_set(self, ctx, day: str):
        """Saves your birthday as month and day. Usage: !birthday set 05-17"""
        parsed = parse_day(day)
        if parsed is None:
            await ctx.reply("Use month and day like `05-17`.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["birthdays"][str(ctx.author.id)] = {"month": parsed[0], "day": parsed[1]}
        self.store.save()
        await ctx.reply(f"Saved. Your birthday is {pretty(*parsed)}.", mention_author=False)

    @birthday.command(name="remove", aliases=["clear"])
    async def birthday_remove(self, ctx):
        """Removes your saved birthday. Usage: !birthday remove"""
        if self.cfg(ctx.guild.id)["birthdays"].pop(str(ctx.author.id), None) is None:
            await ctx.reply("You haven't saved a birthday.", mention_author=False)
            return
        self.store.save()
        await ctx.reply("Your birthday was removed.", mention_author=False)

    @birthday.command(name="list")
    async def birthday_list(self, ctx):
        """Lists birthdays in this server by month. Usage: !birthday list"""
        entries = []
        for uid, entry in self.cfg(ctx.guild.id)["birthdays"].items():
            member = ctx.guild.get_member(int(uid))
            if member is not None:
                entries.append((entry["month"], entry["day"], member.display_name))
        if not entries:
            await ctx.reply("Nobody has saved a birthday yet.", mention_author=False)
            return
        entries.sort()
        lines = [f"**{pretty(m, d)}**: {discord.utils.escape_markdown(name)}" for m, d, name in entries[:40]]
        await ctx.reply(embed=discord.Embed(title="🎂 Birthdays", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @birthday.command(name="next", aliases=["upcoming"])
    async def birthday_next(self, ctx):
        """Shows the next few birthdays. Usage: !birthday next"""
        today = datetime.now(timezone.utc)
        upcoming = []
        for uid, entry in self.cfg(ctx.guild.id)["birthdays"].items():
            member = ctx.guild.get_member(int(uid))
            when = next_occurrence(entry["month"], entry["day"], today)
            if member is not None and when is not None:
                upcoming.append((when, member.display_name))
        if not upcoming:
            await ctx.reply("No birthdays are coming up.", mention_author=False)
            return
        upcoming.sort()
        lines = []
        for when, name in upcoming[:8]:
            days = (when - today.date()).days
            lines.append(f"**{discord.utils.escape_markdown(name)}**: {'today' if days == 0 else f'in {days} day(s)'} ({pretty(when.month, when.day)})")
        await ctx.reply(embed=discord.Embed(title="🎂 Coming up", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="birthdaychannel")
    @commands.has_permissions(manage_guild=True)
    async def birthdaychannel(self, ctx, target: str):
        """Sets where birthday messages go, or turns them off. Usage: !birthdaychannel #birthdays"""
        config = self.cfg(ctx.guild.id)
        if target.lower() == "off":
            config["birthday_channel"] = None
            text = "Birthday messages are off."
        else:
            channel = await self.channel_from(ctx, target)
            if channel is None:
                await ctx.reply("Use a #channel or `off`.", mention_author=False)
                return
            if not channel.permissions_for(ctx.guild.me).send_messages:
                await ctx.reply(f"I can't send messages in {channel.mention}.", mention_author=False)
                return
            config["birthday_channel"] = channel.id
            text = f"Birthday messages will go to {channel.mention}."
        self.store.save()
        await ctx.reply(text, mention_author=False)

    @tasks.loop(minutes=10)
    async def birthday_loop(self):
        now = datetime.now(timezone.utc)
        key = now.strftime("%Y-%m-%d")
        for guild_id, config in list(self.store.data.items()):
            if config.get("last_birthday_check") == key or not config.get("birthday_channel"):
                continue
            guild = self.bot.get_guild(int(guild_id))
            channel = guild.get_channel(config["birthday_channel"]) if guild else None
            if channel is None:
                continue
            config["last_birthday_check"] = key
            names = [uid for uid, e in config.get("birthdays", {}).items() if e["month"] == now.month and e["day"] == now.day and guild.get_member(int(uid))]
            if not names and not (now.month == 3 and now.day == 1 and any(e["month"] == 2 and e["day"] == 29 for e in config.get("birthdays", {}).values())):
                self.store.save()
                continue
            if now.month == 3 and now.day == 1 and not (now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0)):
                names += [uid for uid, e in config["birthdays"].items() if e["month"] == 2 and e["day"] == 29 and guild.get_member(int(uid))]
            self.store.save()
            if names:
                mentions = " ".join(f"<@{uid}>" for uid in names[:20])
                try:
                    await channel.send(f"🎂 Happy birthday {mentions}! 🎉", allowed_mentions=discord.AllowedMentions(users=[discord.Object(int(u)) for u in names[:20]]))
                except discord.HTTPException:
                    pass

    @birthday_loop.before_loop
    async def before_birthday_loop(self):
        await self.bot.wait_until_ready()

    # Staff notes on members
    @commands.group(name="note", aliases=["usernote"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def note(self, ctx):
        """Keeps private staff notes about members. Actions: add, list, remove. Usage: !note add @user trusted"""
        await ctx.reply("Use `note add @user text`, `note list @user` or `note remove @user number`.", mention_author=False)

    @note.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def note_add(self, ctx, member: discord.Member, *, text: str):
        """Adds a staff note to a member. Usage: !note add @user helped in the last event"""
        notes = self.cfg(ctx.guild.id)["notes"].setdefault(str(member.id), [])
        if len(notes) >= 25:
            await ctx.reply("That member already has 25 notes.", mention_author=False)
            return
        notes.append({"by": ctx.author.id, "text": text[:500], "at": int(time.time())})
        self.store.save()
        await ctx.reply(f"Added note {len(notes)} for {member.display_name}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @note.command(name="list", aliases=["show"])
    @commands.has_permissions(manage_messages=True)
    async def note_list(self, ctx, member: discord.Member):
        """Shows the staff notes for a member. Usage: !note list @user"""
        notes = self.cfg(ctx.guild.id)["notes"].get(str(member.id), [])
        if not notes:
            await ctx.reply(f"{member.display_name} has no notes.", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        lines = [f"**{i}.** <t:{n['at']}:d> by <@{n['by']}>: {n['text']}" for i, n in enumerate(notes, start=1)]
        embed = discord.Embed(title=f"Notes for {member.display_name}", description="\n".join(lines)[:4000], color=discord.Color.light_grey())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @note.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_messages=True)
    async def note_remove(self, ctx, member: discord.Member, number: int):
        """Removes one staff note by its number. Usage: !note remove @user 2"""
        notes = self.cfg(ctx.guild.id)["notes"].get(str(member.id), [])
        if not 1 <= number <= len(notes):
            await ctx.reply(f"Pick a note number from 1 to {len(notes)}." if notes else "That member has no notes.", mention_author=False)
            return
        notes.pop(number - 1)
        self.store.save()
        await ctx.reply("Removed that note.", mention_author=False)

    # Reports
    @commands.command(name="reportchannel")
    @commands.has_permissions(manage_guild=True)
    async def reportchannel(self, ctx, target: str):
        """Sets the staff channel for member reports, or turns reports off. Usage: !reportchannel #reports"""
        config = self.cfg(ctx.guild.id)
        if target.lower() == "off":
            config["report_channel"] = None
            text = "Reports are off."
        else:
            channel = await self.channel_from(ctx, target)
            if channel is None:
                await ctx.reply("Use a #channel or `off`.", mention_author=False)
                return
            config["report_channel"] = channel.id
            text = f"Reports will be sent to {channel.mention}."
        self.store.save()
        await ctx.reply(text, mention_author=False)

    @commands.command(name="report")
    async def report(self, ctx, member: discord.Member, *, reason: str):
        """Reports a member to the staff team. Usage: !report @user spamming links"""
        config = self.cfg(ctx.guild.id)
        channel = ctx.guild.get_channel(config["report_channel"]) if config["report_channel"] else None
        if channel is None:
            await ctx.reply("Reports aren't set up. A staff member can use `!reportchannel #channel`.", mention_author=False)
            return
        if member.id == ctx.author.id or member.bot:
            await ctx.reply("Pick a real member to report.", mention_author=False)
            return
        key = (ctx.guild.id, ctx.author.id)
        wait = self.report_times.get(key, 0) + REPORT_COOLDOWN - time.time()
        if wait > 0:
            await ctx.reply(f"You can send another report in {int(wait // 60) + 1} minute(s).", mention_author=False)
            return
        embed = discord.Embed(title="New report", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Reported", value=f"{member.mention} (`{member.id}`)")
        embed.add_field(name="By", value=ctx.author.mention)
        embed.add_field(name="Channel", value=ctx.channel.mention)
        embed.add_field(name="Reason", value=reason[:1000], inline=False)
        embed.add_field(name="Message", value=f"[Jump to report]({ctx.message.jump_url})", inline=False)
        try:
            await channel.send(embed=embed, allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            await ctx.reply("I couldn't send that report. Tell a staff member directly.", mention_author=False)
            return
        self.report_times[key] = time.time()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(f"{ctx.author.mention}, your report was sent to the staff team.", delete_after=8, allowed_mentions=discord.AllowedMentions(users=[ctx.author]))

    # Rules
    @commands.command(name="setrules")
    @commands.has_permissions(manage_guild=True)
    async def setrules(self, ctx, *, text: str):
        """Saves the server rules shown by the rules command, or reset to clear them. Usage: !setrules 1. Be kind. 2. No spam."""
        config = self.cfg(ctx.guild.id)
        if text.lower() == "reset":
            config["rules"] = ""
            reply = "The rules were cleared."
        else:
            config["rules"] = text[:1500]
            reply = "The rules were saved. Members can read them with `!rules`."
        self.store.save()
        await ctx.reply(reply, mention_author=False)

    @commands.command(name="rules")
    async def rules(self, ctx):
        """Shows this server's rules. Usage: !rules"""
        text = self.cfg(ctx.guild.id)["rules"]
        if not text:
            await ctx.reply("No rules have been set. Staff can use `!setrules`.", mention_author=False)
            return
        await ctx.reply(embed=discord.Embed(title=f"Rules for {ctx.guild.name}", description=text, color=discord.Color.light_grey()), mention_author=False, allowed_mentions=NO_MENTIONS)

    # Verify button
    @commands.command(name="verifysetup")
    @commands.has_permissions(manage_roles=True)
    async def verifysetup(self, ctx, channel: discord.TextChannel, role: discord.Role):
        """Posts a Verify button that gives a role to whoever presses it. Usage: !verifysetup #verify @Member"""
        if role.is_default() or role.managed or role >= ctx.guild.me.top_role:
            await ctx.reply("I can't hand out that role. Move my role above it, and don't pick @everyone or a bot role.", mention_author=False)
            return
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.reply("That role is above your highest role.", mention_author=False)
            return
        permissions = channel.permissions_for(ctx.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await ctx.reply(f"I need Send Messages and Embed Links in {channel.mention}.", mention_author=False)
            return
        embed = discord.Embed(title="✅ Verify", description=f"Press the button to get {role.mention} and see the rest of the server.", color=discord.Color.green())
        message = await channel.send(embed=embed, view=VerifyView(), allowed_mentions=NO_MENTIONS)
        self.cfg(ctx.guild.id)["verify"][str(message.id)] = role.id
        self.store.save()
        await ctx.reply(f"Verify button posted in {channel.mention}.", mention_author=False)

    async def handle_verify(self, interaction):
        role_id = self.cfg(interaction.guild_id)["verify"].get(str(interaction.message.id)) if interaction.guild_id else None
        role = interaction.guild.get_role(role_id) if role_id else None
        if role is None:
            await interaction.response.send_message("This button isn't active any more. Tell staff.", ephemeral=True)
            return
        member = interaction.user
        if role in member.roles:
            await interaction.response.send_message("You're already verified.", ephemeral=True)
            return
        try:
            await member.add_roles(role, reason="Verify button")
        except discord.HTTPException:
            await interaction.response.send_message("I couldn't give you the role. Tell staff.", ephemeral=True)
            return
        await interaction.response.send_message(f"You're verified and now have {role.name}.", ephemeral=True)

    # Counting game
    @commands.group(name="counting", invoke_without_command=True)
    async def counting(self, ctx):
        """Shows the counting game status. Actions: set, off, reset. Usage: !counting"""
        state = self.cfg(ctx.guild.id)["counting"]
        if not state["channel"]:
            await ctx.reply("Counting is off. Staff can start it with `!counting set #channel`.", mention_author=False)
            return
        await ctx.reply(f"Counting in <#{state['channel']}>. Current number: **{state['number']}**. Best: **{state['best']}**.", mention_author=False)

    @counting.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def counting_set(self, ctx, channel: discord.TextChannel):
        """Starts the counting game in a channel. Usage: !counting set #counting"""
        state = self.cfg(ctx.guild.id)["counting"]
        state.update(channel=channel.id, number=0, last=None)
        self.store.save()
        await ctx.reply(f"Counting started in {channel.mention}. Type **1** to begin. Take turns, no one counts twice in a row.", mention_author=False)

    @counting.command(name="off")
    @commands.has_permissions(manage_guild=True)
    async def counting_off(self, ctx):
        """Stops the counting game. Usage: !counting off"""
        state = self.cfg(ctx.guild.id)["counting"]
        state.update(channel=None, number=0, last=None)
        self.store.save()
        await ctx.reply("Counting is off.", mention_author=False)

    @counting.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def counting_reset(self, ctx):
        """Resets the count to zero. Usage: !counting reset"""
        state = self.cfg(ctx.guild.id)["counting"]
        state.update(number=0, last=None)
        self.store.save()
        await ctx.reply("The count is back to 0.", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        config = self.store.data.get(str(message.guild.id))
        state = config.get("counting") if config else None
        if not state or state.get("channel") != message.channel.id:
            return
        text = message.content.strip()
        if not re.fullmatch(r"\d{1,9}", text):
            return
        value = int(text)
        expected = state["number"] + 1
        if value == expected and state["last"] != message.author.id:
            state["number"], state["last"] = value, message.author.id
            state["best"] = max(state["best"], value)
            self.store.save()
            try:
                await message.add_reaction("✅")
            except discord.HTTPException:
                pass
            return
        reason = "You can't count twice in a row." if value == expected else f"Wrong number. It should have been **{expected}**."
        state["number"], state["last"] = 0, None
        self.store.save()
        try:
            await message.add_reaction("❌")
            await message.channel.send(f"{message.author.mention} {reason} The count starts again at **1**. Best: {state['best']}.", allowed_mentions=discord.AllowedMentions(users=[message.author]))
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(CommunityExtra(bot))
