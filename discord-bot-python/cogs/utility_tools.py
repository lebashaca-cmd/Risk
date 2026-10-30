import ast
import operator
import platform
import re
import time
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands, tasks

from utils.helpers import NO_MENTIONS, Duration, explain_error, human_duration
from utils.store import JsonStore

NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
HEX = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}


def safe_eval(node):
    if isinstance(node, ast.Expression):
        return safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = safe_eval(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = safe_eval(node.left), safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1e6):
            raise ValueError("That power is too large.")
        return OPS[type(node.op)](left, right)
    raise ValueError("Unsupported expression.")


def format_number(value):
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Not a finite number.")
        return f"{value:,.10g}"
    return f"{value:,}"


class UtilityTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminders = JsonStore("reminders", {"items": []})
        self.afk = JsonStore("afk")
        self.deleted = {}
        self.edited = {}

    async def cog_load(self):
        self.reminder_loop.start()

    async def cog_unload(self):
        self.reminder_loop.cancel()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def fetch_json(self, url, **kwargs):
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, **kwargs) as response:
                if response.status != 200:
                    raise RuntimeError(response.status)
                return await response.json(content_type=None)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar(self, ctx, member: discord.Member = None):
        """Shows someone's avatar in full size. Usage: !avatar @user"""
        member = member or ctx.author
        embed = discord.Embed(title=f"{member.display_name}'s avatar", color=member.color)
        embed.set_image(url=member.display_avatar.replace(size=1024).url)
        await ctx.send(embed=embed)

    @commands.command(name="banner")
    async def banner(self, ctx, member: discord.Member = None):
        """Shows someone's profile banner. Usage: !banner @user"""
        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)
        if user.banner is None:
            await ctx.reply("That user doesn't have a banner.", mention_author=False)
            return
        embed = discord.Embed(title=f"{member.display_name}'s banner", color=member.color)
        embed.set_image(url=user.banner.url)
        await ctx.send(embed=embed)

    @commands.command(name="servericon", aliases=["guildicon"])
    @commands.guild_only()
    async def servericon(self, ctx):
        """Shows the server icon. Usage: !servericon"""
        if ctx.guild.icon is None:
            await ctx.reply("This server has no icon.", mention_author=False)
            return
        embed = discord.Embed(title=ctx.guild.name, color=discord.Color.light_grey())
        embed.set_image(url=ctx.guild.icon.replace(size=1024).url)
        await ctx.send(embed=embed)

    @commands.command(name="membercount", aliases=["members"])
    @commands.guild_only()
    async def membercount(self, ctx):
        """Shows how many members the server has. Usage: !membercount"""
        guild = ctx.guild
        humans = sum(1 for m in guild.members if not m.bot)
        embed = discord.Embed(title=f"{guild.name} members", color=discord.Color.light_grey())
        embed.add_field(name="Total", value=f"{guild.member_count:,}")
        if len(guild.members) >= guild.member_count * 0.9:
            embed.add_field(name="Humans", value=f"{humans:,}")
            embed.add_field(name="Bots", value=f"{len(guild.members) - humans:,}")
        await ctx.send(embed=embed)

    @commands.command(name="roleinfo")
    @commands.guild_only()
    async def roleinfo(self, ctx, *, role: discord.Role):
        """Shows details about a role. Usage: !roleinfo Moderator"""
        embed = discord.Embed(title=role.name, color=role.color)
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Members", value=len(role.members))
        embed.add_field(name="Color", value=str(role.color))
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No")
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No")
        embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, "D"), inline=False)
        await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)

    @commands.command(name="roles")
    @commands.guild_only()
    async def roles(self, ctx):
        """Lists every role in the server. Usage: !roles"""
        names = [r.mention for r in reversed(ctx.guild.roles) if r.id != ctx.guild.id]
        text = " ".join(names) or "No roles."
        embed = discord.Embed(title=f"Roles ({len(names)})", description=text[:4000], color=discord.Color.light_grey())
        await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)

    @commands.command(name="inrole")
    @commands.guild_only()
    async def inrole(self, ctx, *, role: discord.Role):
        """Lists members who have a role. Usage: !inrole Moderator"""
        members = [m.display_name for m in role.members][:40]
        if not members:
            await ctx.reply("Nobody has that role.", mention_author=False)
            return
        more = len(role.members) - len(members)
        text = ", ".join(discord.utils.escape_markdown(n) for n in members) + (f" and {more} more" if more > 0 else "")
        await ctx.send(embed=discord.Embed(title=f"{role.name} ({len(role.members)})", description=text[:4000], color=role.color), allowed_mentions=NO_MENTIONS)

    @commands.command(name="channelinfo")
    @commands.guild_only()
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        """Shows details about a channel. Usage: !channelinfo #general"""
        channel = channel or ctx.channel
        embed = discord.Embed(title=f"#{channel.name}", description=channel.topic or None, color=discord.Color.light_grey())
        embed.add_field(name="ID", value=channel.id)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None")
        embed.add_field(name="Slowmode", value=human_duration(channel.slowmode_delay) if channel.slowmode_delay else "Off")
        embed.add_field(name="NSFW", value="Yes" if channel.is_nsfw() else "No")
        embed.add_field(name="Created", value=discord.utils.format_dt(channel.created_at, "D"))
        await ctx.send(embed=embed)

    @commands.command(name="permissions", aliases=["perms"])
    @commands.guild_only()
    async def permissions(self, ctx, member: discord.Member = None):
        """Lists the permissions a member has here. Usage: !permissions @user"""
        member = member or ctx.author
        perms = ctx.channel.permissions_for(member)
        if perms.administrator:
            text = "Administrator (everything)"
        else:
            text = ", ".join(name.replace("_", " ").title() for name, value in perms if value) or "None"
        await ctx.send(embed=discord.Embed(title=f"{member.display_name} in #{ctx.channel.name}", description=text[:4000], color=member.color))

    @commands.command(name="botinfo", aliases=["about", "stats"])
    async def botinfo(self, ctx):
        """Shows stats about the bot. Usage: !botinfo"""
        embed = discord.Embed(title=str(self.bot.user), color=discord.Color.light_grey())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Servers", value=f"{len(self.bot.guilds):,}")
        embed.add_field(name="Members", value=f"{sum(g.member_count or 0 for g in self.bot.guilds):,}")
        embed.add_field(name="Commands", value=len([c for c in self.bot.commands if not c.hidden]))
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
        embed.add_field(name="discord.py", value=discord.__version__)
        embed.add_field(name="Python", value=platform.python_version())
        await ctx.send(embed=embed)

    @commands.command(name="invite")
    async def invite(self, ctx):
        """Gives the link to add the bot to a server. Usage: !invite"""
        perms = discord.Permissions(
            view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True,
            add_reactions=True, manage_messages=True, manage_channels=True, manage_roles=True, manage_nicknames=True,
            kick_members=True, ban_members=True, moderate_members=True, move_members=True, view_audit_log=True,
        )
        url = discord.utils.oauth_url(self.bot.user.id, permissions=perms, scopes=("bot", "applications.commands"))
        await ctx.reply(f"Add me to your server: <{url}>", mention_author=False)

    @commands.command(name="poll")
    @commands.guild_only()
    async def poll(self, ctx, *, text: str):
        """Starts a reaction poll. Usage: !poll Pizza or tacos? | Pizza | Tacos"""
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if not parts:
            await ctx.reply("Give me a question to ask.", mention_author=False)
            return
        question, options = parts[0], parts[1:]
        if len(options) > 10:
            await ctx.reply("Polls can have at most 10 options.", mention_author=False)
            return
        if len(options) == 1:
            await ctx.reply("Give at least two options, or none for a yes/no poll.", mention_author=False)
            return
        if options:
            body = "\n".join(f"{NUMBER_EMOJI[i]} {opt}" for i, opt in enumerate(options))
            reactions = NUMBER_EMOJI[: len(options)]
        else:
            body, reactions = "React with 👍 or 👎", ["👍", "👎"]
        embed = discord.Embed(title=question[:250], description=body, color=discord.Color.blurple())
        embed.set_footer(text=f"Poll by {ctx.author.display_name}")
        message = await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)
        for emoji in reactions:
            await message.add_reaction(emoji)

    @commands.command(name="remindme", aliases=["remind"])
    async def remindme(self, ctx, duration: Duration, *, reminder: str):
        """Reminds you later in this channel. Usage: !remindme 1h take out the trash"""
        seconds = int(duration.total_seconds())
        if seconds < 10 or seconds > 60 * 86400:
            await ctx.reply("Pick a time between 10 seconds and 60 days.", mention_author=False)
            return
        items = self.reminders.data.setdefault("items", [])
        if sum(1 for r in items if r["user"] == ctx.author.id) >= 15:
            await ctx.reply("You already have 15 reminders. Wait for one to finish.", mention_author=False)
            return
        due = int(time.time()) + seconds
        items.append({"user": ctx.author.id, "channel": ctx.channel.id, "due": due, "text": reminder[:500], "link": ctx.message.jump_url})
        self.reminders.save()
        await ctx.reply(f"I'll remind you <t:{due}:R>.", mention_author=False)

    @commands.command(name="reminders")
    async def reminders_list(self, ctx):
        """Lists your pending reminders. Usage: !reminders"""
        mine = [r for r in self.reminders.data.get("items", []) if r["user"] == ctx.author.id]
        if not mine:
            await ctx.reply("You have no reminders.", mention_author=False)
            return
        lines = [f"<t:{r['due']}:R>: {r['text'][:80]}" for r in sorted(mine, key=lambda r: r["due"])]
        await ctx.send(embed=discord.Embed(title="Your reminders", description="\n".join(lines), color=discord.Color.light_grey()), allowed_mentions=NO_MENTIONS)

    @tasks.loop(seconds=15)
    async def reminder_loop(self):
        items = self.reminders.data.get("items", [])
        now = time.time()
        due = [r for r in items if r["due"] <= now]
        if not due:
            return
        self.reminders.data["items"] = [r for r in items if r["due"] > now]
        self.reminders.save()
        for r in due:
            text = f"<@{r['user']}> reminder: {r['text']}\n{r['link']}"
            channel = self.bot.get_channel(r["channel"])
            try:
                if channel is not None:
                    await channel.send(text, allowed_mentions=discord.AllowedMentions(users=True))
                else:
                    user = await self.bot.fetch_user(r["user"])
                    await user.send(text)
            except discord.HTTPException:
                pass

    @reminder_loop.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()

    @commands.command(name="afk")
    @commands.guild_only()
    async def afk_command(self, ctx, *, reason: str = "AFK"):
        """Marks you as away. Anyone who pings you is told. Usage: !afk lunch"""
        self.afk.data.setdefault(str(ctx.guild.id), {})[str(ctx.author.id)] = {"reason": reason[:200], "since": int(time.time())}
        self.afk.save()
        await ctx.reply(f"You're now AFK: {reason[:200]}", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        guild_afk = self.afk.data.get(str(message.guild.id), {})
        if not guild_afk:
            return
        ctx = await self.bot.get_context(message)
        is_afk_command = ctx.command is not None and ctx.command.name == "afk"
        if str(message.author.id) in guild_afk and not is_afk_command:
            del guild_afk[str(message.author.id)]
            self.afk.save()
            try:
                await message.channel.send(f"Welcome back {message.author.mention}, I removed your AFK.", delete_after=8, allowed_mentions=discord.AllowedMentions(users=True))
            except discord.HTTPException:
                pass
        notes = []
        for user in message.mentions[:5]:
            entry = guild_afk.get(str(user.id))
            if entry and user.id != message.author.id:
                notes.append(f"**{discord.utils.escape_markdown(user.display_name)}** is AFK: {entry['reason']} (<t:{entry['since']}:R>)")
        if notes:
            try:
                await message.reply("\n".join(notes), mention_author=False, allowed_mentions=NO_MENTIONS)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or message.author.bot:
            return
        self.deleted[message.channel.id] = (message.content, message.author, message.created_at, [a.url for a in message.attachments])

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is None or before.author.bot or before.content == after.content:
            return
        self.edited[before.channel.id] = (before.content, after.content, before.author, after.edited_at)

    @commands.command(name="snipe")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):
        """Shows the last deleted message in this channel. Usage: !snipe"""
        entry = self.deleted.get(ctx.channel.id)
        if not entry:
            await ctx.reply("Nothing to snipe.", mention_author=False)
            return
        content, author, when, files = entry
        embed = discord.Embed(description=(content or "*no text*")[:4000], color=discord.Color.red(), timestamp=when)
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        if files:
            embed.add_field(name="Attachments", value="\n".join(files)[:1000])
        await ctx.send(embed=embed)

    @commands.command(name="editsnipe", aliases=["esnipe"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def editsnipe(self, ctx):
        """Shows the last edited message in this channel. Usage: !editsnipe"""
        entry = self.edited.get(ctx.channel.id)
        if not entry:
            await ctx.reply("Nothing to snipe.", mention_author=False)
            return
        before, after, author, when = entry
        embed = discord.Embed(color=discord.Color.orange(), timestamp=when)
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        embed.add_field(name="Before", value=(before or "*empty*")[:1000], inline=False)
        embed.add_field(name="After", value=(after or "*empty*")[:1000], inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="firstmessage", aliases=["firstmsg"])
    @commands.guild_only()
    async def firstmessage(self, ctx):
        """Links to the first message in this channel. Usage: !firstmessage"""
        async for message in ctx.channel.history(limit=1, oldest_first=True):
            await ctx.reply(f"The first message: {message.jump_url}", mention_author=False)
            return
        await ctx.reply("This channel is empty.", mention_author=False)

    @commands.command(name="calc", aliases=["math"])
    async def calc(self, ctx, *, expression: str):
        """Does math with + - * / // % and **. Usage: !calc (12 + 8) * 3"""
        try:
            result = safe_eval(ast.parse(expression.replace("^", "**").replace("×", "*").replace("÷", "/"), mode="eval"))
            text = format_number(result)
        except ZeroDivisionError:
            await ctx.reply("You can't divide by zero.", mention_author=False)
            return
        except (ValueError, SyntaxError, OverflowError, TypeError):
            await ctx.reply("I couldn't work that out. Use numbers and `+ - * / // % **`.", mention_author=False)
            return
        await ctx.reply(f"`{expression[:200]}` = **{text}**", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="color", aliases=["colour"])
    async def color(self, ctx, hex_code: str):
        """Previews a hex color. Usage: !color #ff8800"""
        match = HEX.match(hex_code)
        if not match:
            await ctx.reply("Give a hex color like `#ff8800`.", mention_author=False)
            return
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        value = int(digits, 16)
        r, g, b = value >> 16, (value >> 8) & 255, value & 255
        embed = discord.Embed(title=f"#{digits.upper()}", color=discord.Color(value))
        embed.add_field(name="RGB", value=f"{r}, {g}, {b}")
        embed.add_field(name="Decimal", value=str(value))
        await ctx.send(embed=embed)

    @commands.command(name="snowflake")
    async def snowflake(self, ctx, number: int):
        """Shows when a Discord ID was created. Usage: !snowflake 123456789012345678"""
        if number < 4194304 or number > 2 ** 63:
            await ctx.reply("That isn't a valid Discord ID.", mention_author=False)
            return
        when = discord.utils.snowflake_time(number)
        await ctx.reply(f"Created {discord.utils.format_dt(when, 'F')} ({discord.utils.format_dt(when, 'R')})", mention_author=False)

    @commands.command(name="qr")
    async def qr(self, ctx, *, text: str):
        """Makes a QR code from text or a link. Usage: !qr https://example.com"""
        embed = discord.Embed(title="QR code", color=discord.Color.light_grey())
        embed.set_image(url=f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(text[:500])}")
        await ctx.send(embed=embed)

    @commands.command(name="define", aliases=["dictionary"])
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def define(self, ctx, *, word: str):
        """Looks up the definition of a word. Usage: !define serendipity"""
        word = word.strip()[:50]
        try:
            data = await self.fetch_json(f"https://api.dictionaryapi.dev/v2/entries/en/{quote(word)}")
            entry = data[0]
        except Exception:
            await ctx.reply(f"I couldn't find a definition for **{discord.utils.escape_markdown(word)}**.", mention_author=False)
            return
        embed = discord.Embed(title=entry.get("word", word), color=discord.Color.light_grey())
        if entry.get("phonetic"):
            embed.description = entry["phonetic"]
        for meaning in entry.get("meanings", [])[:3]:
            definitions = meaning.get("definitions", [])
            if definitions:
                embed.add_field(name=meaning.get("partOfSpeech", "meaning"), value=definitions[0]["definition"][:1000], inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="weather")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def weather(self, ctx, *, city: str):
        """Shows the current weather for a city. Usage: !weather Chicago"""
        try:
            data = await self.fetch_json(f"https://wttr.in/{quote(city[:80])}?format=j1")
            now = data["current_condition"][0]
            area = data["nearest_area"][0]["areaName"][0]["value"]
        except Exception:
            await ctx.reply("I couldn't get the weather for that place.", mention_author=False)
            return
        embed = discord.Embed(title=f"Weather in {area}", description=now["weatherDesc"][0]["value"], color=discord.Color.light_grey())
        embed.add_field(name="Temperature", value=f"{now['temp_C']}°C / {now['temp_F']}°F")
        embed.add_field(name="Feels like", value=f"{now['FeelsLikeC']}°C / {now['FeelsLikeF']}°F")
        embed.add_field(name="Humidity", value=f"{now['humidity']}%")
        embed.add_field(name="Wind", value=f"{now['windspeedKmph']} km/h")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(UtilityTools(bot))
