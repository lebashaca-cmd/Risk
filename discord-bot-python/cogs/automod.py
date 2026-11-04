import re
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Union

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

INVITE_RE = re.compile(r"(?:discord(?:app)?\.com/invite|discord\.gg|discord\.me|dsc\.gg)/[A-Za-z0-9-]+", re.I)
LINK_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
SPAM_COUNT = 6
SPAM_WINDOW = 5
SPAM_TIMEOUT = 300


class AutoMod(commands.Cog):
    """Deletes unwanted messages: links, invites, listed words, mention floods and spam."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("automod")
        self.recent = defaultdict(lambda: deque(maxlen=SPAM_COUNT))
        self.patterns = {}

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def cfg(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {})
        data.setdefault("antilink", False)
        data.setdefault("antiinvite", False)
        data.setdefault("antispam", False)
        data.setdefault("maxmentions", 0)
        data.setdefault("badwords", [])
        data.setdefault("ignore_channels", [])
        data.setdefault("ignore_roles", [])
        return data

    def word_pattern(self, words):
        """One compiled pattern per word list, built as a trie so thousands of words stay fast."""
        if not words:
            return None
        key = (len(words), hash(tuple(words)))
        cached = self.patterns.get(key)
        if cached is None:
            trie = {}
            for word in words:
                node = trie
                for char in word.lower():
                    node = node.setdefault(char, {})
                node[""] = True

            def build(node):
                ends = "" in node
                branches = [re.escape(c) + build(child) for c, child in sorted(node.items()) if c != ""]
                if not branches:
                    return ""
                body = branches[0] if len(branches) == 1 else "|".join(branches)
                return "(?:" + body + ")?" if ends else ("(?:" + body + ")" if len(branches) > 1 else body)

            cached = re.compile(r"(?<![A-Za-z0-9])" + build(trie) + r"(?![A-Za-z0-9])", re.I)
            if len(self.patterns) > 200:
                self.patterns.clear()
            self.patterns[key] = cached
        return cached

    async def punish(self, message, reason, notice):
        guild = message.guild
        me = guild.me
        if not message.channel.permissions_for(me).manage_messages:
            return False
        try:
            await message.delete()
        except discord.HTTPException:
            return False
        try:
            await message.channel.send(f"{message.author.mention}, {notice}", delete_after=6, allowed_mentions=discord.AllowedMentions(users=[message.author]))
        except discord.HTTPException:
            pass
        logs = self.bot.get_cog("ServerLogs")
        if logs is not None:
            await logs.send(guild, "Automod", discord.Color.orange(), description=f"Removed a message from {message.author.mention} in {message.channel.mention}: {reason}.", user=message.author)
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or not isinstance(message.author, discord.Member):
            return
        config = self.store.data.get(str(message.guild.id))
        if not config:
            return
        member = message.author
        perms = member.guild_permissions
        if perms.administrator or perms.manage_messages:
            return
        if message.channel.id in config.get("ignore_channels", []) or any(role.id in config.get("ignore_roles", []) for role in member.roles):
            return
        text = message.content or ""

        if config.get("antiinvite") and INVITE_RE.search(text):
            await self.punish(message, "invite link", "invite links aren't allowed here.")
            return
        if config.get("antilink") and LINK_RE.search(text):
            await self.punish(message, "link", "links aren't allowed here.")
            return
        pattern = self.word_pattern(config.get("badwords", []))
        if pattern and pattern.search(text):
            await self.punish(message, "blocked word", "that word isn't allowed here.")
            return
        limit = config.get("maxmentions", 0)
        if limit and len(message.mentions) + len(message.role_mentions) > limit:
            await self.punish(message, "too many mentions", f"please keep it to {limit} mentions or fewer.")
            return
        if config.get("antispam"):
            now = time.monotonic()
            history = self.recent[(message.guild.id, member.id)]
            history.append(now)
            if len(history) >= SPAM_COUNT and now - history[0] <= SPAM_WINDOW:
                history.clear()
                removed = await self.punish(message, "spam", "slow down, you're sending messages too fast.")
                if removed and message.guild.me.guild_permissions.moderate_members and member.top_role < message.guild.me.top_role:
                    try:
                        await member.timeout(timedelta(seconds=SPAM_TIMEOUT), reason="Automod: spam")
                    except discord.HTTPException:
                        pass

    # Commands
    async def toggle(self, ctx, key, value, label):
        config = self.cfg(ctx.guild.id)
        if value is None:
            state = "on" if config[key] else "off"
            await ctx.reply(f"{label} is **{state}**. Use `{ctx.clean_prefix}{ctx.command.name} on` or `off`.", mention_author=False)
            return
        value = value.lower()
        if value not in ("on", "off"):
            await ctx.reply("Say `on` or `off`.", mention_author=False)
            return
        config[key] = value == "on"
        self.store.save()
        await ctx.reply(f"{label} is now **{value}**.", mention_author=False)

    @commands.command(name="antilink")
    @commands.has_permissions(manage_guild=True)
    async def antilink(self, ctx, value: str = None):
        """Deletes messages with links from members who can't manage messages. Usage: !antilink on"""
        await self.toggle(ctx, "antilink", value, "Link blocking")

    @commands.command(name="antiinvite")
    @commands.has_permissions(manage_guild=True)
    async def antiinvite(self, ctx, value: str = None):
        """Deletes messages with Discord invite links. Usage: !antiinvite on"""
        await self.toggle(ctx, "antiinvite", value, "Invite blocking")

    @commands.command(name="antispam")
    @commands.has_permissions(manage_guild=True)
    async def antispam(self, ctx, value: str = None):
        """Deletes message floods and times the sender out for 5 minutes. Usage: !antispam on"""
        await self.toggle(ctx, "antispam", value, "Spam protection")

    @commands.command(name="maxmentions")
    @commands.has_permissions(manage_guild=True)
    async def maxmentions(self, ctx, limit: int):
        """Deletes messages that mention more than a number of people or roles, or 0 to turn off. Usage: !maxmentions 5"""
        if not 0 <= limit <= 50:
            await ctx.reply("Pick a number from 0 to 50. Use 0 to turn this off.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["maxmentions"] = limit
        self.store.save()
        await ctx.reply("Mention limit turned off." if limit == 0 else f"Messages with more than {limit} mentions are now removed.", mention_author=False)

    @commands.group(name="badwords", aliases=["blockedwords"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def badwords(self, ctx):
        """Manages words that get a message deleted. Actions: add, import, remove, list, clear. Usage: !badwords add word"""
        await ctx.reply("Use `badwords add <word>`, `import` (attach a .txt or .env file), `remove <word>`, `list` or `clear`.", mention_author=False)

    @badwords.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def badwords_add(self, ctx, *, word: str):
        """Blocks a word or short phrase. Your command message is deleted so the word isn't shown. Usage: !badwords add word"""
        word = word.strip().lower()
        words = self.cfg(ctx.guild.id)["badwords"]
        if not 2 <= len(word) <= 40:
            await ctx.reply("Use 2 to 40 characters.", mention_author=False)
            return
        if word in words:
            await ctx.reply("That word is already blocked.", mention_author=False)
            return
        if len(words) >= 10000:
            await ctx.reply("The list is full (10,000 words).", mention_author=False)
            return
        words.append(word)
        self.store.save()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(f"Blocked a new word. The list has {len(words)}.", delete_after=8)

    @badwords.command(name="import", aliases=["upload", "file"])
    @commands.has_permissions(manage_guild=True)
    async def badwords_import(self, ctx):
        """Blocks every word in an attached .txt or .env file (one per line, or comma separated). Usage: !badwords import (attach the file)"""
        files = [a for a in ctx.message.attachments if a.filename.lower().endswith((".txt", ".env"))]
        if not files:
            await ctx.reply("Attach a `.txt` or `.env` file to the same message. Put one word per line, or separate words with commas.", mention_author=False)
            return
        file = files[0]
        if file.size > 1_000_000:
            await ctx.reply("That file is over 1 MB. Split it into smaller files.", mention_author=False)
            return
        try:
            text = (await file.read()).decode("utf-8-sig")
        except (UnicodeDecodeError, discord.HTTPException):
            await ctx.reply("I couldn't read that as a text file.", mention_author=False)
            return
        words = self.cfg(ctx.guild.id)["badwords"]
        have, added, skipped, full = set(words), 0, 0, 0
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "//")):
                continue
            line = re.sub(r"^export\s+", "", line)
            match = re.match(r"^[A-Za-z_][\w.-]*\s*=(.*)$", line)
            if match:
                line = match.group(1).strip()
            for part in re.split(r"[,;]", line):
                word = part.strip().strip("\"'").strip().lower()
                if not word:
                    continue
                if not 2 <= len(word) <= 40:
                    skipped += 1
                elif word in have:
                    continue
                elif len(words) >= 10000:
                    full += 1
                else:
                    words.append(word)
                    have.add(word)
                    added += 1
        self.store.save()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        extra = (f" {skipped} skipped (2 to 40 characters only)." if skipped else "") + (f" {full} didn't fit (limit 10,000)." if full else "")
        await ctx.send(f"Blocked {added} new word(s). The list has {len(words)}.{extra}", delete_after=15)

    @badwords.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def badwords_remove(self, ctx, *, word: str):
        """Unblocks a word. Usage: !badwords remove word"""
        words = self.cfg(ctx.guild.id)["badwords"]
        word = word.strip().lower()
        if word not in words:
            await ctx.reply("That word isn't on the list.", mention_author=False)
            return
        words.remove(word)
        self.store.save()
        await ctx.reply("Removed it from the list.", mention_author=False)

    @badwords.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def badwords_list(self, ctx):
        """Sends you the blocked words in a direct message. Usage: !badwords list"""
        words = self.cfg(ctx.guild.id)["badwords"]
        if not words:
            await ctx.reply("No words are blocked.", mention_author=False)
            return
        try:
            await ctx.author.send("Blocked words in **" + ctx.guild.name + "**:\n" + ", ".join(f"||{w}||" for w in words)[:1800])
        except discord.Forbidden:
            await ctx.reply("I couldn't message you. Turn on direct messages from this server.", mention_author=False)
            return
        await ctx.reply(f"I sent you the list of {len(words)} word(s) in a direct message.", mention_author=False)

    @badwords.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def badwords_clear(self, ctx, confirm: str = ""):
        """Removes every blocked word. Usage: !badwords clear confirm"""
        if confirm.lower() != "confirm":
            await ctx.reply("This empties the blocked word list. Run `badwords clear confirm` to continue.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["badwords"] = []
        self.store.save()
        await ctx.reply("The blocked word list is empty.", mention_author=False)

    @commands.command(name="automodignore")
    @commands.has_permissions(manage_guild=True)
    async def automodignore(self, ctx, target: Union[discord.TextChannel, discord.Role]):
        """Toggles a channel or role that automod leaves alone. Usage: !automodignore #staff-chat"""
        config = self.cfg(ctx.guild.id)
        bucket = config["ignore_roles"] if isinstance(target, discord.Role) else config["ignore_channels"]
        if target.id in bucket:
            bucket.remove(target.id)
            text = f"Automod checks {target.mention} again."
        else:
            bucket.append(target.id)
            text = f"Automod now ignores {target.mention}."
        self.store.save()
        await ctx.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="automod")
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):
        """Shows which automod protections are on. Usage: !automod"""
        config = self.cfg(ctx.guild.id)
        flag = lambda value: "🟢 on" if value else "🔴 off"
        embed = discord.Embed(title="Automod", color=discord.Color.light_grey())
        embed.add_field(name="Links", value=flag(config["antilink"]))
        embed.add_field(name="Invites", value=flag(config["antiinvite"]))
        embed.add_field(name="Spam", value=flag(config["antispam"]))
        embed.add_field(name="Mention limit", value=str(config["maxmentions"]) if config["maxmentions"] else "🔴 off")
        embed.add_field(name="Blocked words", value=str(len(config["badwords"])))
        embed.add_field(name="Ignored", value=" ".join([f"<#{c}>" for c in config["ignore_channels"]] + [f"<@&{r}>" for r in config["ignore_roles"]]) or "Nothing", inline=False)
        embed.set_footer(text="Members who can manage messages are never checked. Turn each one on with !antilink, !antiinvite, !antispam, !maxmentions or !badwords.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
