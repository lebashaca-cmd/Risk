"""More utility commands: time zones, money maths, number tools, JSON, lorem ipsum and dates."""
import json
import math
import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

ZONES = {
    "utc": "UTC", "gmt": "UTC", "london": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin", "madrid": "Europe/Madrid", "rome": "Europe/Rome",
    "moscow": "Europe/Moscow", "istanbul": "Europe/Istanbul", "dubai": "Asia/Dubai", "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata", "india": "Asia/Kolkata",
    "bangkok": "Asia/Bangkok", "singapore": "Asia/Singapore", "hongkong": "Asia/Hong_Kong", "shanghai": "Asia/Shanghai", "beijing": "Asia/Shanghai", "tokyo": "Asia/Tokyo",
    "seoul": "Asia/Seoul", "sydney": "Australia/Sydney", "auckland": "Pacific/Auckland", "newyork": "America/New_York", "nyc": "America/New_York", "est": "America/New_York",
    "chicago": "America/Chicago", "cst": "America/Chicago", "cdt": "America/Chicago", "denver": "America/Denver", "mst": "America/Denver", "losangeles": "America/Los_Angeles",
    "la": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles", "toronto": "America/Toronto", "mexico": "America/Mexico_City",
    "saopaulo": "America/Sao_Paulo", "cairo": "Africa/Cairo", "lagos": "Africa/Lagos", "johannesburg": "Africa/Johannesburg", "honolulu": "Pacific/Honolulu",
}
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (10 ** 3, "thousand")]
LOREM = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud "
         "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur").split()
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def spell(n):
    if n < 0:
        return "minus " + spell(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (f" and {spell(n % 100)}" if n % 100 else "")
    for size, name in SCALES:
        if n >= size:
            rest = n % size
            return f"{spell(n // size)} {name}" + (f" {spell(rest)}" if rest else "")
    return str(n)


def to_base(n, base):
    if n == 0:
        return "0"
    out, sign = "", "-" if n < 0 else ""
    n = abs(n)
    while n:
        n, r = divmod(n, base)
        out = DIGITS[r] + out
    return sign + out


class UtilityPlus(commands.Cog, name="UtilityPlus"):
    """More utility commands."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    @commands.command(name="timein", aliases=["tz", "worldtime"])
    async def timein(self, ctx, *, place: str):
        """Shows the time somewhere. Usage: !timein tokyo, !timein America/Chicago"""
        if ZoneInfo is None:
            raise ModError("This host has no time zone data. Ask the host owner to `pip install tzdata`.")
        key = place.strip().lower().replace(" ", "").replace("_", "")
        name = ZONES.get(key) or place.strip().replace(" ", "_")
        try:
            zone = ZoneInfo(name)
        except Exception:
            raise ModError("I don't know that place. Try a city like `tokyo`, `london`, `chicago`, or a name like `America/Chicago`.")
        now = datetime.now(zone)
        await ctx.reply(f"**{name.replace('_', ' ')}**: {now.strftime('%A')}, {now.strftime('%b')} {now.day}, {now.strftime('%I:%M %p').lstrip('0')} ({now.tzname()}, UTC{now.strftime('%z')[:3]}:{now.strftime('%z')[3:]})", mention_author=False)

    @commands.command(name="tip", aliases=["tipcalc"])
    async def tip(self, ctx, bill: float, percent: float = 15, people: int = 1):
        """Works out a tip and a split bill. Usage: !tip 48.50 18 3"""
        if not (0 < bill < 1_000_000 and 0 <= percent <= 100 and 1 <= people <= 100):
            raise ModError("Use a bill above 0, a tip of 0 to 100 percent and 1 to 100 people.")
        tip = bill * percent / 100
        total = bill + tip
        lines = [f"Bill **{bill:,.2f}**, tip ({percent:g}%) **{tip:,.2f}**, total **{total:,.2f}**"]
        if people > 1:
            lines.append(f"Each of {people} pays **{total / people:,.2f}**")
        await ctx.reply("\n".join(lines), mention_author=False)

    @commands.command(name="discount", aliases=["sale"])
    async def discount(self, ctx, price: float, percent: float):
        """Shows a price after a discount. Usage: !discount 80 25"""
        if not (0 <= price < 1e9 and 0 <= percent <= 100):
            raise ModError("Use a price of 0 or more and a discount of 0 to 100 percent.")
        saved = price * percent / 100
        await ctx.reply(f"{price:,.2f} at {percent:g}% off is **{price - saved:,.2f}** (you save {saved:,.2f}).", mention_author=False)

    @commands.command(name="spellout", aliases=["numberwords"])
    async def spellout(self, ctx, number: int):
        """Writes a whole number in words. Usage: !spellout 1234567"""
        if abs(number) >= 10 ** 15:
            raise ModError("Pick a number below one quadrillion.")
        await ctx.reply(f"{number:,} is **{spell(number)}**.", mention_author=False)

    @commands.command(name="json", aliases=["prettyjson"])
    async def json_pretty(self, ctx, *, text: str):
        """Checks JSON and prints it neatly. Usage: !json {"a":1,"b":[1,2]}"""
        text = text.strip().strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        try:
            pretty = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except json.JSONDecodeError as error:
            raise ModError(f"That isn't valid JSON: {error.msg} at line {error.lineno}, column {error.colno}.")
        if len(pretty) > 1800:
            raise ModError("That JSON is too long to show here.")
        await ctx.reply(f"```json\n{pretty}\n```", mention_author=False)

    @commands.command(name="base", aliases=["radix"])
    async def base(self, ctx, number: str, from_base: int, to_base_: int):
        """Converts a number between bases 2 to 36. Usage: !base ff 16 2"""
        if not (2 <= from_base <= 36 and 2 <= to_base_ <= 36):
            raise ModError("Bases go from 2 to 36.")
        try:
            value = int(number, from_base)
        except ValueError:
            raise ModError(f"`{number[:30]}` isn't a valid base {from_base} number.")
        await ctx.reply(f"`{number[:40]}` in base {from_base} is `{to_base(value, to_base_)}` in base {to_base_} (decimal {value:,}).", mention_author=False)

    @commands.command(name="prime", aliases=["isprime"])
    async def prime(self, ctx, number: int):
        """Checks if a number is prime. Usage: !prime 97"""
        if not 0 <= number <= 10 ** 12:
            raise ModError("Pick a number from 0 to 1,000,000,000,000.")
        if number < 2:
            await ctx.reply(f"{number} is not prime.", mention_author=False)
            return
        for d in range(2, int(math.isqrt(number)) + 1):
            if number % d == 0:
                await ctx.reply(f"{number:,} is not prime ({d:,} × {number // d:,}).", mention_author=False)
                return
        await ctx.reply(f"{number:,} is **prime**.", mention_author=False)

    @commands.command(name="factors", aliases=["factor"])
    async def factors(self, ctx, number: int):
        """Shows the prime factors of a number. Usage: !factors 360"""
        if not 2 <= number <= 10 ** 12:
            raise ModError("Pick a number from 2 to 1,000,000,000,000.")
        n, found, d = number, [], 2
        while d * d <= n:
            while n % d == 0:
                found.append(d)
                n //= d
            d += 1 if d == 2 else 2
        if n > 1:
            found.append(n)
        counts = {p: found.count(p) for p in dict.fromkeys(found)}
        text = " × ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in counts.items())
        await ctx.reply(f"{number:,} = **{text}**" if len(counts) > 1 or max(counts.values()) > 1 else f"{number:,} is prime.", mention_author=False)

    @commands.command(name="gcd", aliases=["lcm"])
    async def gcd(self, ctx, a: int, b: int):
        """Shows the greatest common divisor and least common multiple. Usage: !gcd 12 18"""
        if not (0 < abs(a) < 10 ** 15 and 0 < abs(b) < 10 ** 15):
            raise ModError("Use two non-zero whole numbers below one quadrillion.")
        await ctx.reply(f"GCD of {a:,} and {b:,} is **{math.gcd(a, b):,}**, LCM is **{abs(a * b) // math.gcd(a, b):,}**.", mention_author=False)

    @commands.command(name="fibonacci", aliases=["fib"])
    async def fibonacci(self, ctx, count: int = 10):
        """Lists the first Fibonacci numbers (up to 60). Usage: !fibonacci 12"""
        if not 1 <= count <= 60:
            raise ModError("Pick between 1 and 60 numbers.")
        a, b, out = 0, 1, []
        for _ in range(count):
            out.append(a)
            a, b = b, a + b
        await ctx.reply(", ".join(f"{n:,}" for n in out)[:1900], mention_author=False)

    @commands.command(name="lorem", aliases=["loremipsum"])
    async def lorem(self, ctx, words: int = 30):
        """Makes placeholder text (up to 150 words). Usage: !lorem 40"""
        if not 1 <= words <= 150:
            raise ModError("Pick between 1 and 150 words.")
        text = " ".join(random.choice(LOREM) for _ in range(words))
        await ctx.reply(text.capitalize() + ".", mention_author=False)

    @commands.command(name="dayofweek", aliases=["weekday"])
    async def dayofweek(self, ctx, date: str):
        """Tells you the weekday of a date. Usage: !dayofweek 2026-12-25"""
        try:
            when = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ModError("Write the date as year-month-day, like `2026-12-25`.")
        today = datetime.now(timezone.utc).date()
        gap = (when.date() - today).days
        relative = "today" if gap == 0 else f"in {gap} days" if gap > 0 else f"{-gap} days ago"
        await ctx.reply(f"{when.strftime('%B')} {when.day}, {when.year} is a **{when.strftime('%A')}** ({relative}).", mention_author=False)

    @commands.command(name="sortwords", aliases=["sortlist"])
    async def sortwords(self, ctx, *, items: str):
        """Sorts a list (separate with commas or spaces). Add `desc` at the end to reverse. Usage: !sortwords pear, apple, fig"""
        parts = [p.strip() for p in (items.split(",") if "," in items else items.split()) if p.strip()]
        reverse = bool(parts) and parts[-1].lower() == "desc"
        if reverse:
            parts = parts[:-1]
        if len(parts) < 2 or len(parts) > 200:
            raise ModError("Give between 2 and 200 items.")
        try:
            ordered = sorted(parts, key=float, reverse=reverse) if all(p.replace(".", "", 1).lstrip("-").isdigit() for p in parts) else sorted(parts, key=str.lower, reverse=reverse)
        except ValueError:
            ordered = sorted(parts, key=str.lower, reverse=reverse)
        await ctx.reply(discord.utils.escape_mentions(", ".join(ordered))[:1900], mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(UtilityPlus(bot))
