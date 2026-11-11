"""A second batch of utility commands: maths and statistics, money calculators, date tools, text tools,
random generators and small server lookups."""
import math
import random
import re
import secrets
import statistics
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from urllib.parse import unquote

import discord
from discord.ext import commands

from cogs.fun_more import WORDS
from utils.helpers import ModError, NO_MENTIONS, explain_error

NATO = dict(zip("abcdefghijklmnopqrstuvwxyz", "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima Mike November Oscar Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey Xray Yankee Zulu".split()))
SYNODIC = 29.530588853
NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
PHASES = [("New moon", "🌑"), ("Waxing crescent", "🌒"), ("First quarter", "🌓"), ("Waxing gibbous", "🌔"), ("Full moon", "🌕"), ("Waning gibbous", "🌖"), ("Last quarter", "🌗"), ("Waning crescent", "🌘")]


def fmt(x):
    if isinstance(x, complex):
        return f"{fmt(x.real)} {'+' if x.imag >= 0 else '-'} {fmt(abs(x.imag))}i"
    if x == int(x) and abs(x) < 1e15:
        return f"{int(x):,}"
    return f"{x:,.6g}" if abs(x) >= 1e6 or abs(x) < 1e-4 else f"{x:,.4f}".rstrip("0").rstrip(".")


def numbers(text, minimum=1, maximum=200):
    try:
        values = [float(p) for p in re.split(r"[,\s]+", (text or "").strip()) if p]
    except ValueError:
        raise ModError("Give me numbers separated by spaces or commas.")
    if not minimum <= len(values) <= maximum:
        raise ModError(f"Give me {minimum} to {maximum} numbers.")
    return values


def parse_date(text):
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ModError("Dates look like `2026-12-25` (year-month-day).")


def ordinal(n):
    n = int(n)
    return f"{n:,}" + ("th" if 10 <= abs(n) % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(abs(n) % 10, "th"))


class UtilityMore(commands.Cog, name="UtilityMore"):
    """Maths, money, dates, text tools, generators and server lookups."""

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def say(self, ctx, text):
        await ctx.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ---------------------------------------------------------------- maths
    @commands.command(name="sqrt")
    async def sqrt(self, ctx, number: float):
        """Square root of a number. Usage: !sqrt 144"""
        if number < 0:
            await self.say(ctx, f"√{fmt(number)} = **{fmt(complex(0, math.sqrt(-number)))}** (imaginary)")
            return
        await self.say(ctx, f"√{fmt(number)} = **{fmt(math.sqrt(number))}**")

    @commands.command(name="exponent", aliases=["pow", "raise"])
    async def exponent(self, ctx, base: float, exponent: float):
        """Raises a number to a power. Usage: !exponent 2 10"""
        try:
            result = base ** exponent
        except (OverflowError, ZeroDivisionError):
            raise ModError("That number is too big (or divides by zero).")
        if isinstance(result, complex) or abs(result) > 1e300:
            raise ModError("That result isn't a normal number.")
        await self.say(ctx, f"{fmt(base)} ^ {fmt(exponent)} = **{fmt(result)}**")

    @commands.command(name="factorial", aliases=["fac"])
    async def factorial(self, ctx, number: int):
        """Factorial of a whole number up to 500. Usage: !factorial 10"""
        if not 0 <= number <= 500:
            raise ModError("Pick a whole number from 0 to 500.")
        value = math.factorial(number)
        text = f"{value:,}" if len(str(value)) <= 60 else f"{str(value)[0]}.{str(value)[1:8]}e{len(str(value)) - 1} ({len(str(value))} digits)"
        await self.say(ctx, f"{number}! = **{text}**")

    @commands.command(name="ncr", aliases=["choosecount", "combinations"])
    async def ncr(self, ctx, n: int, r: int):
        """Ways to choose r things from n (order doesn't matter). Usage: !ncr 52 5"""
        if not 0 <= r <= n <= 5000:
            raise ModError("Use 0 <= r <= n <= 5000.")
        await self.say(ctx, f"C({n}, {r}) = **{math.comb(n, r):,}**")

    @commands.command(name="npr", aliases=["permutations"])
    async def npr(self, ctx, n: int, r: int):
        """Ways to arrange r things from n (order matters). Usage: !npr 10 3"""
        if not 0 <= r <= n <= 5000:
            raise ModError("Use 0 <= r <= n <= 5000.")
        await self.say(ctx, f"P({n}, {r}) = **{math.perm(n, r):,}**")

    @commands.command(name="median")
    async def median(self, ctx, *, values: str):
        """Median of some numbers. Usage: !median 3 9 1 7"""
        await self.say(ctx, f"Median of {len(numbers(values))} numbers: **{fmt(statistics.median(numbers(values)))}**")

    @commands.command(name="mode")
    async def mode(self, ctx, *, values: str):
        """Most common number(s). Usage: !mode 1 2 2 3 3 3"""
        found = statistics.multimode(numbers(values))
        await self.say(ctx, "Mode: **" + ", ".join(fmt(v) for v in found[:10]) + "**" + (" (everything appears equally often)" if len(found) == len(set(numbers(values))) and len(found) > 1 else ""))

    @commands.command(name="stdev", aliases=["deviation"])
    async def stdev(self, ctx, *, values: str):
        """Standard deviation and mean of some numbers. Usage: !stdev 2 4 4 4 5 5 7 9"""
        data = numbers(values, minimum=2)
        await self.say(ctx, f"Mean **{fmt(statistics.fmean(data))}**, population std dev **{fmt(statistics.pstdev(data))}**, sample std dev **{fmt(statistics.stdev(data))}** ({len(data)} numbers)")

    @commands.command(name="simplify", aliases=["fraction"])
    async def simplify(self, ctx, top: int, bottom: int):
        """Simplifies a fraction. Usage: !simplify 18 24"""
        if bottom == 0:
            raise ModError("The bottom number can't be 0.")
        f = Fraction(top, bottom)
        await self.say(ctx, f"{top}/{bottom} = **{f.numerator}/{f.denominator}** (decimal {fmt(top / bottom)})")

    @commands.command(name="quadratic")
    async def quadratic(self, ctx, a: float, b: float, c: float):
        """Solves ax^2 + bx + c = 0. Usage: !quadratic 1 -3 2"""
        if a == 0:
            raise ModError("`a` can't be 0 (that isn't a quadratic).")
        disc = b * b - 4 * a * c
        root = math.sqrt(disc) if disc >= 0 else complex(0, math.sqrt(-disc))
        x1, x2 = (-b + root) / (2 * a), (-b - root) / (2 * a)
        await self.say(ctx, f"Discriminant {fmt(disc)}. " + (f"x = **{fmt(x1)}**" if x1 == x2 else f"x = **{fmt(x1)}** and **{fmt(x2)}**"))

    @commands.command(name="hypot", aliases=["pythagoras"])
    async def hypot(self, ctx, a: float, b: float):
        """Length of the long side of a right triangle. Usage: !hypot 3 4"""
        await self.say(ctx, f"Hypotenuse = **{fmt(math.hypot(a, b))}**")

    @commands.command(name="circle")
    async def circle(self, ctx, radius: float):
        """Circle circumference and area from a radius. Usage: !circle 5"""
        if radius < 0:
            raise ModError("The radius can't be negative.")
        await self.say(ctx, f"Radius {fmt(radius)}: circumference **{fmt(2 * math.pi * radius)}**, area **{fmt(math.pi * radius ** 2)}**, diameter **{fmt(radius * 2)}**")

    @commands.command(name="ordinal")
    async def ordinal_cmd(self, ctx, number: int):
        """Writes a number as 1st, 2nd, 3rd. Usage: !ordinal 22"""
        await self.say(ctx, ordinal(number))

    @commands.command(name="scientific", aliases=["sci"])
    async def scientific(self, ctx, number: float):
        """Writes a number in scientific notation. Usage: !scientific 123456"""
        await self.say(ctx, f"{number:g} = **{number:.6e}**")

    # ---------------------------------------------------------------- money and fitness
    @commands.command(name="interest")
    async def interest(self, ctx, principal: float, rate: float, years: float, per_year: int = 12):
        """Compound interest. Usage: !interest 1000 5 10 (amount, yearly %, years, compounds per year)"""
        if principal < 0 or not 0 <= rate <= 1000 or not 0 < years <= 200 or not 1 <= per_year <= 365:
            raise ModError("Try something like `!interest 1000 5 10`.")
        total = principal * (1 + rate / 100 / per_year) ** (per_year * years)
        await self.say(ctx, f"{fmt(principal)} at {fmt(rate)}% for {fmt(years)} years (compounded {per_year}x a year) becomes **{fmt(total)}**, which is **{fmt(total - principal)}** of interest.")

    @commands.command(name="loan")
    async def loan(self, ctx, amount: float, rate: float, years: float):
        """Monthly payment on a loan. Usage: !loan 20000 6.5 5 (amount, yearly %, years)"""
        if amount <= 0 or not 0 <= rate <= 100 or not 0 < years <= 50:
            raise ModError("Try something like `!loan 20000 6.5 5`.")
        months, monthly = int(round(years * 12)), rate / 1200
        payment = amount / months if monthly == 0 else amount * monthly / (1 - (1 + monthly) ** -months)
        await self.say(ctx, f"Loan of {fmt(amount)} at {fmt(rate)}% over {months} months: **{fmt(payment)}** a month, {fmt(payment * months)} total, {fmt(payment * months - amount)} interest.")

    @commands.command(name="splitbill")
    async def splitbill(self, ctx, total: float, people: int, tip: float = 0):
        """Splits a bill between people with an optional tip %. Usage: !splitbill 84.50 4 18"""
        if total < 0 or not 1 <= people <= 100 or not 0 <= tip <= 100:
            raise ModError("Try something like `!splitbill 84.50 4 18`.")
        grand = total * (1 + tip / 100)
        await self.say(ctx, f"Total with {fmt(tip)}% tip: **{fmt(grand)}**, so **{fmt(grand / people)}** each for {people} people.")

    @commands.command(name="salary", aliases=["wage"])
    async def salary(self, ctx, hourly: float, hours_per_week: float = 40):
        """Turns an hourly wage into weekly, monthly and yearly pay. Usage: !salary 22.50 40"""
        if hourly < 0 or not 0 < hours_per_week <= 168:
            raise ModError("Try something like `!salary 22.50 40`.")
        weekly = hourly * hours_per_week
        await self.say(ctx, f"At {fmt(hourly)}/hour for {fmt(hours_per_week)} hours a week: **{fmt(weekly)}** a week, **{fmt(weekly * 52 / 12)}** a month, **{fmt(weekly * 52)}** a year (before tax).")

    @commands.command(name="pace")
    async def pace(self, ctx, distance: float, time: str):
        """Running pace and speed. Usage: !pace 5 27:30 (distance, time as minutes or mm:ss or h:mm:ss)"""
        parts = time.split(":")
        try:
            seconds = sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts))) if len(parts) > 1 else float(time) * 60
        except ValueError:
            raise ModError("Time looks like `27:30` or `27.5`.")
        if distance <= 0 or seconds <= 0:
            raise ModError("Distance and time must be above 0.")
        per = seconds / distance
        await self.say(ctx, f"Pace: **{int(per // 60)}:{int(per % 60):02d}** per unit of distance, speed **{fmt(distance / (seconds / 3600))}** per hour.")

    # ---------------------------------------------------------------- dates
    @commands.command(name="datediff")
    async def datediff(self, ctx, start: str, end: str):
        """Days between two dates. Usage: !datediff 2026-01-01 2026-12-25"""
        a, b = parse_date(start), parse_date(end)
        days = (b - a).days
        await self.say(ctx, f"**{abs(days):,}** days between them ({abs(days) // 7} weeks and {abs(days) % 7} days). {'The second date is earlier.' if days < 0 else ''}".strip())

    @commands.command(name="adddays", aliases=["addtime"])
    async def adddays(self, ctx, start: str, days: int):
        """Adds (or subtracts) days from a date. Usage: !adddays 2026-11-11 100, or `today` as the date"""
        a = datetime.now(timezone.utc).date() if start.lower() == "today" else parse_date(start)
        if abs(days) > 100000:
            raise ModError("That's too far away.")
        result = a + timedelta(days=days)
        await self.say(ctx, f"{a:%Y-%m-%d} {'+' if days >= 0 else '-'} {abs(days):,} days = **{result:%A, %B} {result.day}, {result.year}**")

    @commands.command(name="leapyear")
    async def leapyear(self, ctx, year: int):
        """Tells you whether a year is a leap year. Usage: !leapyear 2028"""
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        await self.say(ctx, f"{year} {'**is** a leap year (366 days).' if leap else 'is **not** a leap year (365 days).'}")

    @commands.command(name="weeknumber", aliases=["weekno"])
    async def weeknumber(self, ctx, when: str = "today"):
        """ISO week number of a date. Usage: !weeknumber 2026-12-25"""
        d = datetime.now(timezone.utc).date() if when.lower() == "today" else parse_date(when)
        iso = d.isocalendar()
        await self.say(ctx, f"{d:%A %Y-%m-%d} is in week **{iso[1]}** of {iso[0]} (day {d.timetuple().tm_yday} of the year).")

    @commands.command(name="moonphase", aliases=["moon"])
    async def moonphase(self, ctx, when: str = "today"):
        """The moon phase for a date. Usage: !moonphase 2026-12-25"""
        d = datetime.now(timezone.utc) if when.lower() == "today" else datetime.combine(parse_date(when), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
        age = ((d - NEW_MOON).total_seconds() / 86400) % SYNODIC
        name, icon = PHASES[int((age / SYNODIC * 8) + 0.5) % 8]
        lit = (1 - math.cos(2 * math.pi * age / SYNODIC)) / 2
        await self.say(ctx, f"{icon} **{name}**, about {lit * 100:.0f}% lit (moon age {age:.1f} days).")

    # ---------------------------------------------------------------- text tools
    @staticmethod
    def need(text, limit=1500):
        if not text or not text.strip():
            raise ModError("Give me some text.")
        return text.strip()[:limit]

    @commands.command(name="readtime")
    async def readtime(self, ctx, *, text: str = None):
        """How long some text takes to read aloud and silently. Usage: !readtime <text>"""
        words = len(self.need(text, 20000).split())
        await self.say(ctx, f"{words:,} words: about **{max(1, round(words / 238))} min** to read silently, **{max(1, round(words / 150))} min** aloud.")

    @commands.command(name="palindrome")
    async def palindrome(self, ctx, *, text: str = None):
        """Checks whether text reads the same backwards. Usage: !palindrome A man a plan a canal Panama"""
        cleaned = re.sub(r"[^a-z0-9]", "", self.need(text).lower())
        if not cleaned:
            raise ModError("Use some letters or numbers.")
        await self.say(ctx, "✅ That's a palindrome." if cleaned == cleaned[::-1] else "❌ Not a palindrome.")

    @commands.command(name="anagram")
    async def anagram(self, ctx, first: str, second: str):
        """Checks whether two words are anagrams. Usage: !anagram listen silent"""
        a, b = sorted(re.sub(r"[^a-z]", "", first.lower())), sorted(re.sub(r"[^a-z]", "", second.lower()))
        await self.say(ctx, "✅ Anagrams!" if a and a == b else "❌ Not anagrams.")

    @staticmethod
    def words_of(text):
        return re.findall(r"[A-Za-z0-9]+", text)

    @commands.command(name="camelcase")
    async def camelcase(self, ctx, *, text: str = None):
        """Converts text to camelCase. Usage: !camelcase hello big world"""
        w = self.words_of(self.need(text))
        await self.say(ctx, f"`{(w[0].lower() + ''.join(x.capitalize() for x in w[1:])) if w else ''}`")

    @commands.command(name="snakecase")
    async def snakecase(self, ctx, *, text: str = None):
        """Converts text to snake_case. Usage: !snakecase Hello Big World"""
        await self.say(ctx, f"`{'_'.join(x.lower() for x in self.words_of(self.need(text)))}`")

    @commands.command(name="kebabcase")
    async def kebabcase(self, ctx, *, text: str = None):
        """Converts text to kebab-case. Usage: !kebabcase Hello Big World"""
        await self.say(ctx, f"`{'-'.join(x.lower() for x in self.words_of(self.need(text)))}`")

    @commands.command(name="dedupe")
    async def dedupe(self, ctx, *, text: str = None):
        """Removes repeated words (keeping the first of each). Usage: !dedupe a b a c b"""
        seen, out = set(), []
        for word in self.need(text).split():
            if word.lower() not in seen:
                seen.add(word.lower())
                out.append(word)
        await self.say(ctx, " ".join(out))

    @commands.command(name="shuffle")
    async def shuffle(self, ctx, *, text: str = None):
        """Shuffles the words you give. Usage: !shuffle one two three four"""
        words = self.need(text).split()
        random.shuffle(words)
        await self.say(ctx, " ".join(words))

    @commands.command(name="nato")
    async def nato(self, ctx, *, text: str = None):
        """Spells text with the NATO phonetic alphabet. Usage: !nato risk"""
        out = [NATO.get(c, c) for c in self.need(text, 60).lower() if c != " "]
        await self.say(ctx, " ".join(out))

    @commands.command(name="piglatin")
    async def piglatin(self, ctx, *, text: str = None):
        """Translates to pig latin. Usage: !piglatin hello world"""
        def one(word):
            m = re.match(r"([^aeiou]*)(.*)", word, re.I)
            head, rest = m.group(1), m.group(2)
            return (word + "way") if not head else (rest + head + "ay")
        await self.say(ctx, " ".join(one(w) for w in self.need(text).lower().split()))

    @commands.command(name="atbash")
    async def atbash(self, ctx, *, text: str = None):
        """Atbash cipher (a becomes z, b becomes y). Usage: !atbash hello"""
        flip = lambda c: chr(ord("a") + 25 - (ord(c) - ord("a"))) if "a" <= c <= "z" else chr(ord("A") + 25 - (ord(c) - ord("A"))) if "A" <= c <= "Z" else c
        await self.say(ctx, "".join(flip(c) for c in self.need(text)))

    @commands.command(name="texthex")
    async def texthex(self, ctx, *, text: str = None):
        """Turns text into hex bytes. Usage: !texthex hello"""
        await self.say(ctx, f"`{self.need(text, 300).encode().hex(' ')}`")

    @commands.command(name="unhex")
    async def unhex(self, ctx, *, text: str = None):
        """Turns hex bytes back into text. Usage: !unhex 68 65 6c 6c 6f"""
        try:
            out = bytes.fromhex(self.need(text, 900)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ModError("That isn't valid hex text.")
        await self.say(ctx, out or "(empty)")

    @commands.command(name="urldecode")
    async def urldecode(self, ctx, *, text: str = None):
        """Decodes %20 style text from a link. Usage: !urldecode hello%20world"""
        await self.say(ctx, unquote(self.need(text)))

    # ---------------------------------------------------------------- generators (secrets are sent privately)
    async def private(self, ctx, text):
        try:
            await ctx.author.send(text)
            await ctx.reply("📬 I sent it to your DMs.", mention_author=False)
        except discord.HTTPException:
            await ctx.reply("I couldn't DM you. Open your DMs for this server and try again.", mention_author=False)

    @commands.command(name="passphrase")
    async def passphrase(self, ctx, words: int = 5):
        """DMs you a random passphrase of 3 to 8 words. Usage: !passphrase 5"""
        words = max(3, min(words, 8))
        await self.private(ctx, "Your passphrase: `" + "-".join(secrets.choice(WORDS) for _ in range(words)) + "`\nDon't reuse it anywhere else, and don't share it.")

    @commands.command(name="pin")
    async def pin(self, ctx, digits: int = 4):
        """DMs you a random PIN of 4 to 10 digits. Usage: !pin 6"""
        digits = max(4, min(digits, 10))
        await self.private(ctx, "Your PIN: `" + "".join(secrets.choice("0123456789") for _ in range(digits)) + "`")

    @commands.command(name="randomhex", aliases=["hextoken"])
    async def randomhex(self, ctx, length: int = 32):
        """DMs you a random hex string (8 to 64 characters). Usage: !randomhex 32"""
        await self.private(ctx, "`" + secrets.token_hex(32)[:max(8, min(length, 64))] + "`")

    @commands.command(name="randcolor", aliases=["randomcolor"])
    async def randcolor(self, ctx):
        """Picks a random colour. Usage: !randcolor"""
        value = random.randint(0, 0xFFFFFF)
        embed = discord.Embed(title=f"#{value:06X}", description=f"RGB {value >> 16}, {(value >> 8) & 255}, {value & 255}", color=discord.Color(value))
        await ctx.reply(embed=embed, mention_author=False)

    # ---------------------------------------------------------------- server lookups
    @commands.command(name="joinposition", aliases=["joinpos"])
    @commands.guild_only()
    async def joinposition(self, ctx, member: discord.Member = None):
        """Shows which number member someone was to join. Usage: !joinposition @user"""
        member = member or ctx.author
        ordered = sorted((m for m in ctx.guild.members if m.joined_at), key=lambda m: m.joined_at)
        if member not in ordered:
            raise ModError("I couldn't find when they joined.")
        await self.say(ctx, f"**{member.display_name}** was the **{ordinal(ordered.index(member) + 1)}** member to join (of {len(ordered):,} I can see).")

    @commands.command(name="createdat", aliases=["accountcreated"])
    async def createdat(self, ctx, member: discord.User = None):
        """Shows when an account was created. Usage: !createdat @user"""
        member = member or ctx.author
        stamp = int(member.created_at.timestamp())
        await self.say(ctx, f"**{member.display_name}**'s account was created <t:{stamp}:F> (<t:{stamp}:R>).")

    @commands.command(name="randommember", aliases=["randmember"])
    @commands.guild_only()
    async def randommember(self, ctx, role: discord.Role = None):
        """Picks a random member, optionally from a role. Usage: !randommember @role"""
        pool = [m for m in (role.members if role else ctx.guild.members) if not m.bot]
        if not pool:
            raise ModError("There's nobody to pick from.")
        await self.say(ctx, f"🎲 Random member: **{random.choice(pool).display_name}**")

    @commands.command(name="countrole")
    @commands.guild_only()
    async def countrole(self, ctx, *, role: discord.Role):
        """Counts the members who have a role. Usage: !countrole @Moderator"""
        humans = sum(1 for m in role.members if not m.bot)
        await self.say(ctx, f"**{role.name}** has **{len(role.members):,}** member(s), {humans:,} human and {len(role.members) - humans:,} bot.")


async def setup(bot):
    await bot.add_cog(UtilityMore(bot))
