import colorsys
import ipaddress
import math
import re
import statistics
import unicodedata
import uuid as uuidlib
from datetime import datetime, timezone
from typing import Union
from urllib.parse import quote, unquote, urlparse

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error

UA = {"User-Agent": "RiskBot/1.0 (discord bot)"}
PER_PAGE = 15

# Unit tables: value is how many base units one of the unit is.
LENGTH = {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344}
MASS = {"mg": 1e-6, "g": 0.001, "kg": 1, "t": 1000, "oz": 0.028349523125, "lb": 0.45359237, "st": 6.35029318}
VOLUME = {"ml": 0.001, "l": 1, "tsp": 0.00492892159375, "tbsp": 0.01478676478125, "floz": 0.0295735295625, "cup": 0.2365882365, "pt": 0.473176473, "qt": 0.946352946, "gal": 3.785411784}
SPEED = {"mps": 1, "kph": 1000 / 3600, "mph": 0.44704, "knot": 0.514444444, "fps": 0.3048}
TABLES = {"length": LENGTH, "mass": MASS, "volume": VOLUME, "speed": SPEED}
ALIASES = {
    "millimeter": "mm", "millimeters": "mm", "centimeter": "cm", "centimeters": "cm", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "kilometer": "km", "kilometers": "km", "kilometre": "km", "kilometres": "km", "inch": "in", "inches": "in", "foot": "ft", "feet": "ft",
    "yard": "yd", "yards": "yd", "mile": "mi", "miles": "mi",
    "milligram": "mg", "milligrams": "mg", "gram": "g", "grams": "g", "kilogram": "kg", "kilograms": "kg", "kgs": "kg", "tonne": "t", "tonnes": "t",
    "ounce": "oz", "ounces": "oz", "pound": "lb", "pounds": "lb", "lbs": "lb", "stone": "st", "stones": "st",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "teaspoon": "tsp", "teaspoons": "tsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "fl.oz": "floz", "cups": "cup",
    "pint": "pt", "pints": "pt", "quart": "qt", "quarts": "qt", "gallon": "gal", "gallons": "gal",
    "m/s": "mps", "km/h": "kph", "kmh": "kph", "kmph": "kph", "mi/h": "mph", "knots": "knot", "kt": "knot", "ft/s": "fps",
    "celsius": "c", "°c": "c", "fahrenheit": "f", "°f": "f", "kelvin": "k",
}
TEMPS = {"c", "f", "k"}
COINS = {
    "btc": "bitcoin", "eth": "ethereum", "sol": "solana", "doge": "dogecoin", "ltc": "litecoin", "xrp": "ripple", "ada": "cardano",
    "bnb": "binancecoin", "dot": "polkadot", "matic": "matic-network", "usdt": "tether", "avax": "avalanche-2", "trx": "tron",
    "link": "chainlink", "shib": "shiba-inu",
}
LEET = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "A": "4", "E": "3", "I": "1", "O": "0", "S": "5", "T": "7"})
ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def fmt(value):
    if value == 0:
        return "0"
    if abs(value) >= 1e9 or abs(value) < 1e-4:
        return f"{value:.6g}"
    text = f"{value:,.4f}".rstrip("0").rstrip(".")
    return text or "0"


def parse_when(text):
    text = text.strip()
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def page_slice(items, page, per=PER_PAGE):
    pages = max(1, -(-len(items) // per))
    page = max(1, min(page, pages))
    return items[(page - 1) * per: page * per], page, pages


def to_roman(number):
    out = ""
    for value, symbol in ROMAN:
        while number >= value:
            out += symbol
            number -= value
    return out


def from_roman(text):
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for index, ch in enumerate(text):
        value = values[ch]
        if index + 1 < len(text) and values[text[index + 1]] > value:
            total -= value
        else:
            total += value
    return total if to_roman(total) == text else None


def unsafe_host(host):
    host = (host or "").lower()
    if not host or host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast


class UtilityMore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def fetch_json(self, url):
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, headers=UA) as session:
            async with session.get(url) as response:
                if response.status == 404:
                    return None
                if response.status != 200:
                    raise RuntimeError(response.status)
                return await response.json(content_type=None)

    async def member_list(self, ctx, title, members, page=1, empty="Nobody to show."):
        if not members:
            await ctx.reply(empty, mention_author=False)
            return
        chunk, page, pages = page_slice(members, page)
        start = (page - 1) * PER_PAGE
        lines = [f"**{start + i}.** {m.mention} ({discord.utils.escape_markdown(m.display_name)})" for i, m in enumerate(chunk, start=1)]
        embed = discord.Embed(title=f"{title} ({len(members)})", description="\n".join(lines), color=discord.Color.light_grey())
        embed.set_footer(text=f"Page {page} of {pages}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    async def send_text(self, ctx, title, text):
        embed = discord.Embed(title=title, description=f"```\n{text[:1900]}\n```", color=discord.Color.light_grey())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # Members and servers
    @commands.command(name="joined")
    @commands.guild_only()
    async def joined(self, ctx, member: discord.Member = None):
        """Shows when someone joined and their join position. Usage: !joined @user"""
        member = member or ctx.author
        ordered = sorted((m for m in ctx.guild.members if m.joined_at), key=lambda m: m.joined_at)
        position = next((i for i, m in enumerate(ordered, start=1) if m.id == member.id), None)
        stamp = int(member.joined_at.timestamp()) if member.joined_at else None
        embed = discord.Embed(title=member.display_name, color=discord.Color.light_grey())
        embed.add_field(name="Joined", value=f"<t:{stamp}:F> (<t:{stamp}:R>)" if stamp else "Unknown")
        embed.add_field(name="Join position", value=f"#{position:,} of {len(ordered):,}" if position else "Unknown")
        created = int(member.created_at.timestamp())
        embed.add_field(name="Account created", value=f"<t:{created}:R>")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="oldest")
    @commands.guild_only()
    async def oldest(self, ctx, page: int = 1):
        """Lists the members who joined first. Usage: !oldest 2"""
        members = sorted((m for m in ctx.guild.members if m.joined_at), key=lambda m: m.joined_at)
        await self.member_list(ctx, "Oldest members", members, page)

    @commands.command(name="newest")
    @commands.guild_only()
    async def newest(self, ctx, page: int = 1):
        """Lists the members who joined most recently. Usage: !newest"""
        members = sorted((m for m in ctx.guild.members if m.joined_at), key=lambda m: m.joined_at, reverse=True)
        await self.member_list(ctx, "Newest members", members, page)

    @commands.command(name="boosters")
    @commands.guild_only()
    async def boosters(self, ctx, page: int = 1):
        """Lists the members boosting the server. Usage: !boosters"""
        members = sorted(ctx.guild.premium_subscribers, key=lambda m: m.premium_since or datetime.now(timezone.utc))
        await self.member_list(ctx, "Boosters", members, page, empty="Nobody is boosting this server yet.")

    @commands.command(name="admins")
    @commands.guild_only()
    async def admins(self, ctx, page: int = 1):
        """Lists the members with Administrator permission. Usage: !admins"""
        members = [m for m in ctx.guild.members if not m.bot and m.guild_permissions.administrator]
        await self.member_list(ctx, "Administrators", members, page, empty="No human member has Administrator.")

    @commands.command(name="bots")
    @commands.guild_only()
    async def bots(self, ctx, page: int = 1):
        """Lists the bots in this server. Usage: !bots"""
        members = [m for m in ctx.guild.members if m.bot]
        await self.member_list(ctx, "Bots", members, page, empty="There are no bots here.")

    @commands.command(name="whohas")
    @commands.guild_only()
    async def whohas(self, ctx, role: discord.Role, page: int = 1):
        """Lists the members that have a role. Usage: !whohas @Moderators"""
        members = sorted(role.members, key=lambda m: m.display_name.lower())
        await self.member_list(ctx, f"Members with {role.name}", members, page, empty=f"Nobody has {discord.utils.escape_markdown(role.name)}.")

    # Emojis
    @commands.command(name="emojiinfo")
    async def emojiinfo(self, ctx, emoji: Union[discord.Emoji, discord.PartialEmoji]):
        """Shows details about a custom emoji. Usage: !emojiinfo :name:"""
        if emoji.id is None:
            await ctx.reply("That's a standard emoji. Try `!charinfo` for it.", mention_author=False)
            return
        embed = discord.Embed(title=emoji.name, color=discord.Color.light_grey())
        embed.set_thumbnail(url=emoji.url)
        embed.add_field(name="ID", value=str(emoji.id))
        embed.add_field(name="Animated", value="Yes" if emoji.animated else "No")
        embed.add_field(name="Created", value=f"<t:{int(emoji.created_at.timestamp())}:R>")
        embed.add_field(name="Image", value=f"[Open]({emoji.url})")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="addemoji")
    @commands.guild_only()
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def addemoji(self, ctx, name: str, url: str = None):
        """Adds a custom emoji from an image link or attachment. Usage: !addemoji party https://example.com/party.png"""
        if not re.fullmatch(r"\w{2,32}", name):
            await ctx.reply("Emoji names use 2 to 32 letters, numbers or underscores.", mention_author=False)
            return
        if ctx.message.attachments:
            url = ctx.message.attachments[0].url
        if not url:
            await ctx.reply("Attach an image or give a link, like `!addemoji party https://example.com/party.png`.", mention_author=False)
            return
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or unsafe_host(parsed.hostname):
            await ctx.reply("That link isn't allowed. Use a public http or https image link.", mention_author=False)
            return
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=UA) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise RuntimeError(response.status)
                    data = await response.content.read(262145)
        except Exception:
            await ctx.reply("I couldn't download that image.", mention_author=False)
            return
        if len(data) > 262144:
            await ctx.reply("Emoji images must be 256 KB or smaller.", mention_author=False)
            return
        if not (data.startswith(b"\x89PNG") or data.startswith(b"\xff\xd8") or data.startswith(b"GIF8") or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
            await ctx.reply("That file isn't a PNG, JPG, GIF or WebP image.", mention_author=False)
            return
        try:
            emoji = await ctx.guild.create_custom_emoji(name=name, image=data, reason=f"Added by {ctx.author}")
        except discord.HTTPException as error:
            await ctx.reply(f"Discord refused it: {str(error.text or error)[:150]}", mention_author=False)
            return
        await ctx.reply(f"Added {emoji} as `:{emoji.name}:`.", mention_author=False)

    @commands.command(name="removeemoji")
    @commands.guild_only()
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def removeemoji(self, ctx, emoji: discord.Emoji):
        """Deletes a custom emoji from this server. Usage: !removeemoji :party:"""
        if emoji.guild_id != ctx.guild.id:
            await ctx.reply("That emoji isn't from this server.", mention_author=False)
            return
        name = emoji.name
        await emoji.delete(reason=f"Removed by {ctx.author}")
        await ctx.reply(f"Deleted `:{name}:`.", mention_author=False)

    # Maths and conversions
    @commands.command(name="convert")
    async def convert(self, ctx, amount: float, source: str, *, target: str):
        """Converts length, mass, volume, speed and temperature units. Usage: !convert 10 km to mi"""
        target = target.strip()
        if target.lower().startswith("to "):
            target = target[3:].strip()
        a = ALIASES.get(source.lower(), source.lower())
        b = ALIASES.get(target.lower(), target.lower())
        if not math.isfinite(amount):
            await ctx.reply("Give a normal number.", mention_author=False)
            return
        if a in TEMPS and b in TEMPS:
            kelvin = {"c": amount + 273.15, "f": (amount - 32) * 5 / 9 + 273.15, "k": amount}[a]
            result = {"c": kelvin - 273.15, "f": (kelvin - 273.15) * 9 / 5 + 32, "k": kelvin}[b]
            if kelvin < 0:
                await ctx.reply("That's below absolute zero.", mention_author=False)
                return
            kind = "temperature"
        else:
            kind = next((name for name, table in TABLES.items() if a in table and b in table), None)
            if kind is None:
                units = ", ".join(sorted({u for table in TABLES.values() for u in table} | TEMPS))
                await ctx.reply(f"I can't convert `{source[:20]}` to `{target[:20]}`. Units must match and be one of: {units}.", mention_author=False)
                return
            result = amount * TABLES[kind][a] / TABLES[kind][b]
        embed = discord.Embed(title=kind.title(), description=f"**{fmt(amount)} {a}** = **{fmt(result)} {b}**", color=discord.Color.light_grey())
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="percent")
    async def percent(self, ctx, first: float, second: float):
        """Works out percentages between two numbers. Usage: !percent 20 150"""
        embed = discord.Embed(title="Percent", color=discord.Color.light_grey())
        embed.add_field(name=f"{fmt(first)}% of {fmt(second)}", value=fmt(first * second / 100), inline=False)
        if second != 0:
            embed.add_field(name=f"{fmt(first)} is what % of {fmt(second)}", value=f"{fmt(first / second * 100)}%", inline=False)
        if first != 0:
            embed.add_field(name=f"Change from {fmt(first)} to {fmt(second)}", value=f"{fmt((second - first) / abs(first) * 100)}%", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="average", aliases=["mean"])
    async def average(self, ctx, *numbers: float):
        """Gives the mean, median, mode, range and sum of some numbers. Usage: !average 4 8 15 16 23 42"""
        if not numbers:
            await ctx.reply("Give some numbers, like `!average 4 8 15 16 23 42`.", mention_author=False)
            return
        if len(numbers) > 200 or not all(math.isfinite(n) for n in numbers):
            await ctx.reply("Use up to 200 normal numbers.", mention_author=False)
            return
        values = list(numbers)
        modes = statistics.multimode(values)
        embed = discord.Embed(title=f"{len(values)} number(s)", color=discord.Color.light_grey())
        embed.add_field(name="Mean", value=fmt(statistics.fmean(values)))
        embed.add_field(name="Median", value=fmt(statistics.median(values)))
        embed.add_field(name="Mode", value=("None" if len(modes) == len(set(values)) and len(values) > 1 else ", ".join(fmt(m) for m in modes[:5])))
        embed.add_field(name="Smallest", value=fmt(min(values)))
        embed.add_field(name="Largest", value=fmt(max(values)))
        embed.add_field(name="Sum", value=fmt(sum(values)))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="bmi")
    async def bmi(self, ctx, weight: float, height: float, system: str = "metric"):
        """Works out body mass index from kg and cm, or lb and inches. Usage: !bmi 70 175 or !bmi 154 69 imperial"""
        system = system.lower()
        if system not in ("metric", "imperial"):
            await ctx.reply("Use `metric` (kg, cm) or `imperial` (lb, in).", mention_author=False)
            return
        if system == "metric":
            ok = 20 <= weight <= 500 and 50 <= height <= 260
            value = weight / (height / 100) ** 2 if ok else 0
        else:
            ok = 40 <= weight <= 1100 and 20 <= height <= 105
            value = weight / height ** 2 * 703 if ok else 0
        if not ok:
            await ctx.reply("Those numbers don't look right for that system.", mention_author=False)
            return
        band = "Underweight" if value < 18.5 else "Healthy range" if value < 25 else "Overweight" if value < 30 else "Obese range"
        embed = discord.Embed(title=f"BMI {value:.1f}", description=band, color=discord.Color.light_grey())
        embed.set_footer(text="BMI is a rough screening number, not medical advice.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="age")
    async def age(self, ctx, birthday: str):
        """Works out an age and the next birthday from a date. Usage: !age 2000-05-17"""
        born = parse_when(birthday)
        now = datetime.now(timezone.utc)
        if born is None or born > now or born.year < 1900:
            await ctx.reply("Use a past date like `2000-05-17`.", mention_author=False)
            return
        years = now.year - born.year - ((now.month, now.day) < (born.month, born.day))
        months = (now.month - born.month - (now.day < born.day)) % 12
        try:
            upcoming = born.replace(year=now.year)
        except ValueError:
            upcoming = born.replace(year=now.year, day=28)
        if upcoming.date() < now.date():
            try:
                upcoming = born.replace(year=now.year + 1)
            except ValueError:
                upcoming = born.replace(year=now.year + 1, day=28)
        days_left = (upcoming.date() - now.date()).days
        embed = discord.Embed(title=f"{years} years, {months} months old", color=discord.Color.light_grey())
        embed.add_field(name="Days lived", value=f"{(now.date() - born.date()).days:,}")
        embed.add_field(name="Next birthday", value="Today! 🎂" if days_left == 0 else f"in {days_left} day(s)")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="roman")
    async def roman(self, ctx, value: str):
        """Converts a number to a Roman numeral, or back. Usage: !roman 2026"""
        if value.isdigit():
            number = int(value)
            if not 1 <= number <= 3999:
                await ctx.reply("Pick a number from 1 to 3999.", mention_author=False)
                return
            await ctx.reply(embed=discord.Embed(title=to_roman(number), description=f"{number}", color=discord.Color.light_grey()), mention_author=False)
            return
        upper = value.upper()
        if not re.fullmatch(r"[IVXLCDM]{1,15}", upper) or from_roman(upper) is None:
            await ctx.reply("Give a number, or a valid Roman numeral like `MMXXVI`.", mention_author=False)
            return
        await ctx.reply(embed=discord.Embed(title=str(from_roman(upper)), description=upper, color=discord.Color.light_grey()), mention_author=False)

    # Text tools
    @commands.command(name="charinfo")
    async def charinfo(self, ctx, *, text: str):
        """Shows the Unicode name and code of each character. Usage: !charinfo é"""
        lines = []
        for ch in text[:15]:
            if ch.isspace() and ch != " ":
                continue
            name = unicodedata.name(ch, "Unknown")
            shown = ch if ch.isprintable() else " "
            lines.append(f"`U+{ord(ch):04X}` {shown} {name}")
        if not lines:
            await ctx.reply("There's nothing to look up.", mention_author=False)
            return
        embed = discord.Embed(description="\n".join(lines), color=discord.Color.light_grey())
        if len(text) > 15:
            embed.set_footer(text="Showing the first 15 characters.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="leetspeak", aliases=["leet"])
    async def leetspeak(self, ctx, *, text: str):
        """Writes text in leetspeak. Usage: !leetspeak elite hacker"""
        await self.send_text(ctx, "1337", text.translate(LEET))

    @commands.command(name="caesar")
    async def caesar(self, ctx, shift: int, *, text: str):
        """Shifts the letters of some text, a Caesar cipher. Usage: !caesar 3 hello"""
        if not -25 <= shift <= 25:
            await ctx.reply("Use a shift from -25 to 25. Shift back by the same amount to decode.", mention_author=False)
            return

        def move(ch):
            if "a" <= ch <= "z":
                return chr((ord(ch) - 97 + shift) % 26 + 97)
            if "A" <= ch <= "Z":
                return chr((ord(ch) - 65 + shift) % 26 + 65)
            return ch

        await self.send_text(ctx, f"Caesar shift {shift}", "".join(move(ch) for ch in text))

    @commands.command(name="wordcount", aliases=["wc"])
    async def wordcount(self, ctx, *, text: str):
        """Counts the words, characters and sentences in some text. Usage: !wordcount some text here"""
        words = len(text.split())
        sentences = len([s for s in re.split(r"[.!?]+", text) if s.strip()])
        minutes = words / 200
        embed = discord.Embed(title="Word count", color=discord.Color.light_grey())
        embed.add_field(name="Words", value=f"{words:,}")
        embed.add_field(name="Characters", value=f"{len(text):,}")
        embed.add_field(name="Without spaces", value=f"{len(re.sub(r'\\s', '', text)):,}")
        embed.add_field(name="Sentences", value=f"{sentences:,}")
        embed.add_field(name="Reading time", value="under a minute" if minutes < 1 else f"about {round(minutes)} min")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="uppercase", aliases=["upper"])
    async def uppercase(self, ctx, *, text: str):
        """Turns text into UPPERCASE. Usage: !uppercase hello"""
        await self.send_text(ctx, "Uppercase", text.upper())

    @commands.command(name="lowercase", aliases=["lower"])
    async def lowercase(self, ctx, *, text: str):
        """Turns text into lowercase. Usage: !lowercase HELLO"""
        await self.send_text(ctx, "Lowercase", text.lower())

    @commands.command(name="titlecase")
    async def titlecase(self, ctx, *, text: str):
        """Turns text Into Title Case. Usage: !titlecase the quick brown fox"""
        await self.send_text(ctx, "Title case", text.title())

    @commands.command(name="slugify", aliases=["slug"])
    async def slugify(self, ctx, *, text: str):
        """Turns text into a url-friendly slug. Usage: !slugify My Great Post!"""
        plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
        await self.send_text(ctx, "Slug", slug or "Nothing left after cleaning that text.")

    @commands.command(name="urlencode")
    async def urlencode(self, ctx, mode: str, *, text: str):
        """Encodes or decodes text for use in a link. Usage: !urlencode encode hello world"""
        mode = mode.lower()
        if mode == "encode":
            await self.send_text(ctx, "URL encoded", quote(text, safe=""))
        elif mode == "decode":
            await self.send_text(ctx, "URL decoded", unquote(text))
        else:
            await ctx.reply("Use `encode` or `decode`, like `!urlencode encode hello world`.", mention_author=False)

    @commands.command(name="uuid")
    async def uuid(self, ctx, count: int = 1):
        """Generates random UUIDs. Usage: !uuid 3"""
        if not 1 <= count <= 5:
            await ctx.reply("Pick from 1 to 5.", mention_author=False)
            return
        await self.send_text(ctx, "UUID", "\n".join(str(uuidlib.uuid4()) for _ in range(count)))

    # Dates
    @commands.command(name="countdown")
    async def countdown(self, ctx, *, when: str):
        """Counts down to a UTC date and time. Usage: !countdown 2026-12-25 18:00"""
        moment = parse_when(when)
        if moment is None:
            await ctx.reply("Use `YYYY-MM-DD` or `YYYY-MM-DD HH:MM` (UTC).", mention_author=False)
            return
        seconds = int((moment - datetime.now(timezone.utc)).total_seconds())
        stamp = int(moment.timestamp())
        if seconds <= 0:
            await ctx.reply(f"That moment passed <t:{stamp}:R>.", mention_author=False)
            return
        days, rest = divmod(seconds, 86400)
        hours, rest = divmod(rest, 3600)
        minutes = rest // 60
        embed = discord.Embed(title=f"{days}d {hours}h {minutes}m", description=f"Until <t:{stamp}:F> (<t:{stamp}:R>)", color=discord.Color.light_grey())
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="daysuntil")
    async def daysuntil(self, ctx, date: str):
        """Tells you how many days are left until a date. Usage: !daysuntil 2026-12-25"""
        moment = parse_when(date)
        if moment is None:
            await ctx.reply("Use a date like `2026-12-25`.", mention_author=False)
            return
        days = (moment.date() - datetime.now(timezone.utc).date()).days
        if days == 0:
            text = "That's today."
        elif days > 0:
            text = f"**{days:,}** day(s) to go."
        else:
            text = f"That was **{-days:,}** day(s) ago."
        await ctx.reply(embed=discord.Embed(description=text, color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="epoch", aliases=["unix"])
    async def epoch(self, ctx, *, value: str = "now"):
        """Converts between Unix time and a UTC date. Usage: !epoch 1798221600 or !epoch 2026-12-25 18:00"""
        value = value.strip()
        if value.lower() == "now":
            moment = datetime.now(timezone.utc)
        elif re.fullmatch(r"\d{1,11}", value):
            try:
                moment = datetime.fromtimestamp(int(value), timezone.utc)
            except (OverflowError, OSError, ValueError):
                await ctx.reply("That number is out of range.", mention_author=False)
                return
        else:
            moment = parse_when(value)
            if moment is None:
                await ctx.reply("Give `now`, a Unix number, or a UTC date like `2026-12-25 18:00`.", mention_author=False)
                return
        embed = discord.Embed(title=str(int(moment.timestamp())), description=f"{moment:%Y-%m-%d %H:%M:%S} UTC\n<t:{int(moment.timestamp())}:F>", color=discord.Color.light_grey())
        await ctx.reply(embed=embed, mention_author=False)

    # Colours
    @commands.command(name="palette")
    async def palette(self, ctx, hex_code: str):
        """Builds a five-colour palette from one hex colour. Usage: !palette #5865F2"""
        text = hex_code.lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
            await ctx.reply("Give a six-digit hex colour like `#5865F2`.", mention_author=False)
            return
        red, green, blue = (int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hue, light, sat = colorsys.rgb_to_hls(red, green, blue)

        def make(shift, lightness=None):
            r, g, b = colorsys.hls_to_rgb((hue + shift) % 1.0, light if lightness is None else lightness, sat)
            return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"

        swatches = [("Base", f"#{text.upper()}"), ("Complement", make(0.5)), ("Analogous", make(1 / 12)), ("Analogous", make(-1 / 12)), ("Lighter", make(0, min(0.9, light + 0.25)))]
        embed = discord.Embed(title="Palette", color=int(text, 16))
        for name, code in swatches:
            embed.add_field(name=name, value=f"`{code}`")
        await ctx.reply(embed=embed, mention_author=False)

    # Web lookups
    @commands.command(name="pypi")
    async def pypi(self, ctx, package: str):
        """Looks up a Python package on PyPI. Usage: !pypi requests"""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", package):
            await ctx.reply("That isn't a valid package name.", mention_author=False)
            return
        try:
            data = await self.fetch_json(f"https://pypi.org/pypi/{quote(package)}/json")
        except Exception:
            await ctx.reply("PyPI isn't answering right now. Try again soon.", mention_author=False)
            return
        if data is None:
            await ctx.reply("I couldn't find that package.", mention_author=False)
            return
        info = data.get("info", {})
        embed = discord.Embed(title=f"{info.get('name', package)} {info.get('version', '')}".strip(), description=(info.get("summary") or "No summary.")[:500], url=info.get("package_url"), color=discord.Color.light_grey())
        if info.get("author"):
            embed.add_field(name="Author", value=str(info["author"])[:200])
        if info.get("license"):
            embed.add_field(name="License", value=str(info["license"]).splitlines()[0][:100])
        if info.get("requires_python"):
            embed.add_field(name="Python", value=str(info["requires_python"])[:100])
        embed.add_field(name="Install", value=f"`pip install {info.get('name', package)}`", inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="crypto")
    async def crypto(self, ctx, coin: str = "bitcoin"):
        """Shows a cryptocurrency price in US dollars. Usage: !crypto eth"""
        key = COINS.get(coin.lower(), coin.lower())
        if not re.fullmatch(r"[a-z0-9-]{1,50}", key):
            await ctx.reply("Use a coin name like `bitcoin` or a symbol like `btc`.", mention_author=False)
            return
        try:
            data = await self.fetch_json(f"https://api.coingecko.com/api/v3/simple/price?ids={key}&vs_currencies=usd&include_24hr_change=true")
        except Exception:
            await ctx.reply("The price service isn't answering right now. Try again soon.", mention_author=False)
            return
        if not data or key not in data:
            await ctx.reply("I couldn't find that coin. Try its full name, like `ethereum`.", mention_author=False)
            return
        price = data[key].get("usd")
        change = data[key].get("usd_24h_change")
        embed = discord.Embed(title=key.replace("-", " ").title(), description=f"**${price:,.6g}**" if price is not None else "No price available.", color=discord.Color.gold())
        if change is not None:
            embed.add_field(name="24 hour change", value=f"{'📈' if change >= 0 else '📉'} {change:+.2f}%")
        embed.set_footer(text="Prices are for information only.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(UtilityMore(bot))
