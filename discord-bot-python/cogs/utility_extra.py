import base64
import binascii
import codecs
import hashlib
import re
import secrets
import string
from datetime import datetime, timezone
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..", "j": ".---",
    "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-",
    "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}
UNMORSE = {code: letter for letter, code in MORSE.items()}
HASHES = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}
TODO_LIMIT = 25


class UtilityExtra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.todos = JsonStore("todo")

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def send_text(self, ctx, title, text):
        embed = discord.Embed(title=title, description=f"```\n{text[:1900]}\n```", color=discord.Color.light_grey())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="base64", aliases=["b64"])
    async def base64_command(self, ctx, mode: str, *, text: str):
        """Encodes or decodes Base64 text. Usage: !base64 encode hello"""
        mode = mode.lower()
        if mode == "encode":
            await self.send_text(ctx, "Base64", base64.b64encode(text.encode()).decode())
        elif mode == "decode":
            try:
                result = base64.b64decode(text.strip(), validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                await ctx.reply("That isn't valid Base64 text.", mention_author=False)
                return
            await self.send_text(ctx, "Base64 decoded", result)
        else:
            await ctx.reply("Use `encode` or `decode`, like `!base64 encode hello`.", mention_author=False)

    @commands.command(name="morse")
    async def morse(self, ctx, *, text: str):
        """Converts text to Morse code, or Morse code back to text. Usage: !morse hello world"""
        if re.fullmatch(r"[.\-/ ]+", text.strip()):
            words = text.strip().split(" / ") if " / " in text else text.strip().split("/")
            decoded = " ".join("".join(UNMORSE.get(code, "?") for code in word.split()) for word in words)
            await self.send_text(ctx, "Morse decoded", decoded)
            return
        encoded = " / ".join(" ".join(MORSE[ch] for ch in word if ch in MORSE) for word in text.lower().split())
        await self.send_text(ctx, "Morse", encoded or "No letters or numbers to convert.")

    @commands.command(name="rot13")
    async def rot13(self, ctx, *, text: str):
        """Applies the ROT13 letter swap. Usage: !rot13 hello"""
        await self.send_text(ctx, "ROT13", codecs.encode(text, "rot13"))

    @commands.command(name="binary")
    async def binary(self, ctx, *, text: str):
        """Converts text to binary, or binary back to text. Usage: !binary hi"""
        if re.fullmatch(r"[01 ]+", text.strip()):
            try:
                chunks = text.split() if " " in text.strip() else [text.strip()[i:i + 8] for i in range(0, len(text.strip()), 8)]
                decoded = bytes(int(chunk, 2) for chunk in chunks).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                await ctx.reply("That isn't valid binary text.", mention_author=False)
                return
            await self.send_text(ctx, "Binary decoded", decoded)
            return
        await self.send_text(ctx, "Binary", " ".join(f"{byte:08b}" for byte in text.encode()))

    @commands.command(name="hash")
    async def hash_command(self, ctx, algorithm: str, *, text: str):
        """Hashes text with md5, sha1, sha256 or sha512. Usage: !hash sha256 hello"""
        function = HASHES.get(algorithm.lower())
        if function is None:
            await ctx.reply("Pick one of: " + ", ".join(f"`{name}`" for name in HASHES) + ".", mention_author=False)
            return
        await self.send_text(ctx, algorithm.lower(), function(text.encode()).hexdigest())

    @commands.command(name="password", aliases=["pass"])
    async def password(self, ctx, length: int = 16):
        """Sends you a random password in a direct message. Usage: !password 20"""
        if not 8 <= length <= 64:
            await ctx.reply("Pick a length from 8 to 64.", mention_author=False)
            return
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
        while True:
            value = "".join(secrets.choice(alphabet) for _ in range(length))
            if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
                break
        try:
            await ctx.author.send(f"Your password:\n||`{value}`||")
        except discord.Forbidden:
            await ctx.reply("I couldn't message you. Turn on direct messages from this server and try again.", mention_author=False)
            return
        await ctx.reply("I sent you a password in a direct message.", mention_author=False)

    WIKI_API = "https://en.wikipedia.org/w/api.php"
    WIKI_HEADERS = {"User-Agent": "RiskDiscordBot/2.0 (https://github.com/lebashaca-cmd/Risk; Discord bot) aiohttp", "Accept": "application/json"}

    async def wiki_lookup(self, topic):
        """Searches Wikipedia (so capitals, typos and redirects don't matter) and returns the best article, or None."""
        params = {
            "action": "query", "format": "json", "formatversion": "2", "generator": "search", "gsrsearch": topic, "gsrlimit": "1",
            "prop": "extracts|pageimages|info|pageprops", "exintro": "1", "explaintext": "1", "exchars": "1200",
            "inprop": "url", "piprop": "thumbnail", "pithumbsize": "300", "redirects": "1",
        }
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout, headers=self.WIKI_HEADERS) as session:
            async with session.get(self.WIKI_API, params=params) as response:
                if response.status != 200:
                    raise RuntimeError(f"Wikipedia answered HTTP {response.status}")
                data = await response.json(content_type=None)
        pages = (data.get("query") or {}).get("pages") or []
        return pages[0] if pages else None

    @commands.command(name="wiki", aliases=["wikipedia"])
    async def wiki(self, ctx, *, topic: str):
        """Shows the summary of a Wikipedia article. Usage: !wiki Alan Turing"""
        topic = topic.strip()[:200]
        try:
            async with ctx.typing():
                page = await self.wiki_lookup(topic)
        except Exception as error:
            print(f"[wiki] lookup failed: {type(error).__name__}: {error}")
            await ctx.reply("Wikipedia isn't answering right now. Try again soon.", mention_author=False)
            return
        if not page:
            await ctx.reply("I couldn't find an article for that. Try different words.", mention_author=False)
            return
        extract = (page.get("extract") or "").strip() or "No summary is available for this article."
        embed = discord.Embed(title=str(page.get("title", topic))[:250], description=extract[:1500], url=page.get("fullurl"), color=discord.Color.light_grey())
        if "disambiguation" in (page.get("pageprops") or {}):
            embed.set_footer(text="This name has several meanings. Try a more specific title.")
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            embed.set_thumbnail(url=thumb)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="timestamp", aliases=["ts"])
    async def timestamp(self, ctx, *, when: str = "now"):
        """Makes a Discord timestamp from a UTC date. Usage: !timestamp 2026-12-25 18:00"""
        when = when.strip()
        if when.lower() == "now":
            moment = datetime.now(timezone.utc)
        else:
            moment = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    moment = datetime.strptime(when, fmt).replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue
            if moment is None:
                await ctx.reply("Use `now`, `YYYY-MM-DD` or `YYYY-MM-DD HH:MM` (UTC).", mention_author=False)
                return
        stamp = int(moment.timestamp())
        lines = [f"`<t:{stamp}:{code}>` → <t:{stamp}:{code}>" for code in ("F", "f", "D", "t", "R")]
        await ctx.reply(embed=discord.Embed(title="Timestamp", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embed_command(self, ctx, channel: discord.TextChannel, *, content: str):
        """Posts an embed in a channel. Separate the title and text with a pipe. Usage: !embed #news Title | The text"""
        title, _, body = content.partition("|")
        title, body = title.strip(), body.strip()
        if not body:
            title, body = "", title
        if not body:
            await ctx.reply("Give the embed some text, like `!embed #news Title | The text`.", mention_author=False)
            return
        permissions = channel.permissions_for(ctx.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await ctx.reply("I need Send Messages and Embed Links in that channel.", mention_author=False)
            return
        embed = discord.Embed(title=title[:250] or None, description=body[:3900], color=discord.Color.light_grey())
        await channel.send(embed=embed)
        await ctx.reply(f"Posted in {channel.mention}.", mention_author=False)

    @commands.command(name="announce")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def announce(self, ctx, channel: discord.TextChannel, *, message: str):
        """Sends an announcement to a channel. Usage: !announce #news Server maintenance tonight"""
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.send_messages:
            await ctx.reply("I can't send messages in that channel.", mention_author=False)
            return
        await channel.send(f"📢 {message[:1900]}", allowed_mentions=NO_MENTIONS)
        await ctx.reply(f"Announced in {channel.mention}.", mention_author=False)

    @commands.command(name="todo")
    async def todo(self, ctx, action: str = "list", *, text: str = ""):
        """Keeps a personal to-do list. Actions: add, list, done, remove, clear. Usage: !todo add buy milk"""
        action = action.lower()
        items = self.todos.data.setdefault(str(ctx.author.id), [])
        if action == "add":
            if not text.strip():
                await ctx.reply("Say what to add, like `!todo add buy milk`.", mention_author=False)
            elif len(items) >= TODO_LIMIT:
                await ctx.reply(f"Your list is full ({TODO_LIMIT} items). Remove some first.", mention_author=False)
            else:
                items.append({"text": text.strip()[:200], "done": False})
                self.todos.save()
                await ctx.reply(f"Added item {len(items)}.", mention_author=False)
            return
        if action in ("done", "remove", "rm"):
            if not text.strip().isdigit() or not 1 <= int(text) <= len(items):
                await ctx.reply(f"Give an item number from 1 to {len(items)}." if items else "Your list is empty.", mention_author=False)
                return
            index = int(text) - 1
            if action == "done":
                items[index]["done"] = not items[index]["done"]
                message = "Marked as done." if items[index]["done"] else "Marked as not done."
            else:
                items.pop(index)
                message = "Removed."
            self.todos.save()
            await ctx.reply(message, mention_author=False)
            return
        if action == "clear":
            self.todos.data[str(ctx.author.id)] = []
            self.todos.save()
            await ctx.reply("Cleared your list.", mention_author=False)
            return
        if action != "list":
            await ctx.reply("Use `add`, `list`, `done`, `remove` or `clear`.", mention_author=False)
            return
        if not items:
            await ctx.reply("Your list is empty. Add something with `!todo add buy milk`.", mention_author=False)
            return
        lines = [f"{index}. {'~~' if item['done'] else ''}{discord.utils.escape_markdown(item['text'])}{'~~' if item['done'] else ''}" for index, item in enumerate(items, start=1)]
        await ctx.reply(embed=discord.Embed(title=f"{ctx.author.display_name}'s to-do list", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(UtilityExtra(bot))
