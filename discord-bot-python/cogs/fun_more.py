import asyncio
import hashlib
import random
import re
import time
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error

ROASTS = [
    "{t} has the energy of a phone at 1% that still refuses to charge.",
    "{t} is proof that autocorrect isn't the only thing that needs a second try.",
    "{t} types 'lol' with a completely straight face.",
    "{t} would lose a staring contest with a screensaver.",
    "{t} has main character energy in a story nobody is reading.",
    "{t} brings a spoon to a group project and calls it teamwork.",
    "{t} still says 'brb' and comes back three days later.",
    "{t} is the reason the instructions have pictures.",
    "{t} thinks 'reply all' is a personality.",
    "{t} gets lost in a one-room house and blames the map.",
]
PICKUPS = [
    "Are you a keyboard? Because you're just my type.",
    "Are you Wi-Fi? Because I'm feeling a connection.",
    "Do you have a map? I keep getting lost in your messages.",
    "Is your name Google? Because you have everything I've been searching for.",
    "Are you a magician? Every time I read your message, everyone else disappears.",
    "If you were a command, you'd be the one I never want to forget.",
    "Are you a loading bar? Because I'd wait for you.",
    "I must be a bug, because you keep crashing into my thoughts.",
]
QUOTES = [
    "Small steps still move you forward.",
    "Start where you are, use what you have, do what you can.",
    "A calm mind finishes more than a rushed one.",
    "Progress is quiet. Keep going.",
    "The best time to begin was yesterday. The next best is now.",
    "You don't have to be fast. You only have to keep walking.",
    "Mistakes are proof that you're trying.",
    "Rest is part of the work.",
    "Be kind. Everyone is carrying something you can't see.",
    "Done is better than perfect.",
    "Courage is doing it while still nervous.",
    "Today is a good day to learn one new thing.",
]
THIS_OR_THAT = [
    ("Pizza", "Burgers"), ("Mountains", "Beach"), ("Night owl", "Early bird"), ("Cats", "Dogs"),
    ("Summer", "Winter"), ("Books", "Movies"), ("Sweet", "Salty"), ("Text", "Call"),
    ("Coffee", "Tea"), ("City", "Countryside"), ("Games on PC", "Games on console"), ("Rain", "Snow"),
    ("Save money", "Spend money"), ("Fly", "Teleport"), ("Always hot", "Always cold"),
]
NEVER_HAVE_I_EVER = [
    "Never have I ever stayed up until sunrise on a school night.", "Never have I ever sent a message to the wrong chat.",
    "Never have I ever pretended to know a song's lyrics.", "Never have I ever forgotten what I walked into a room for.",
    "Never have I ever laughed at a message and then forgotten to reply.", "Never have I ever eaten dessert before dinner.",
    "Never have I ever gotten lost with a GPS running.", "Never have I ever fallen asleep during a movie.",
    "Never have I ever rage quit a game.", "Never have I ever muted a group chat the second I was added.",
]
SENTENCES = [
    "the quick brown fox jumps over the lazy dog",
    "pack my box with five dozen liquor jugs",
    "bright vixens jump and dozy fowl quack",
    "how vexingly quick daft zebras jump",
    "sphinx of black quartz judge my vow",
    "a journey of a thousand miles begins with one step",
]
WORDS = [
    "discord", "keyboard", "server", "pixel", "dragon", "rocket", "puzzle", "thunder", "island", "coffee", "garden", "planet",
    "wizard", "castle", "jungle", "mirror", "shadow", "violin", "button", "cookie", "ocean", "canyon", "lantern", "marble",
    "python", "galaxy", "pirate", "winter", "library", "compass", "volcano", "diamond",
]
GALLOWS = [
    "  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========",
    "  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========",
]
SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"]
MOODS = ["Calm and steady", "Curious and restless", "Bold and chatty", "Quiet but sharp", "Warm and generous", "Playful and lucky"]
ADVICE = [
    "Say yes to the small invitation.", "Finish the thing you started last week.", "Answer that message you've been avoiding.",
    "Take the long way home.", "Spend less time scrolling and more time making.", "Trust the plan, but pack a backup.",
]
COLORS = ["red", "blue", "green", "gold", "violet", "teal", "orange", "silver"]
MEMBER_REQUIRED = commands.guild_only()


def stable(*parts):
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(), 16)


def today():
    return datetime.now(timezone.utc).date().isoformat()


class Connect4Button(discord.ui.Button):
    def __init__(self, column):
        super().__init__(label=str(column + 1), style=discord.ButtonStyle.secondary, row=column // 4)
        self.column = column

    async def callback(self, interaction):
        await self.view.play(interaction, self.column)


class Connect4View(discord.ui.View):
    SYMBOLS = {0: "⚪", 1: "🔴", 2: "🟡"}

    def __init__(self, first, second):
        super().__init__(timeout=180)
        self.players = [first, second]
        self.board = [[0] * 7 for _ in range(6)]
        self.turn = 0
        self.message = None
        self.finished = False
        for column in range(7):
            self.add_item(Connect4Button(column))

    def render(self, footer=None, color=None):
        rows = ["".join(self.SYMBOLS[cell] for cell in row) for row in self.board]
        header = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"
        names = f"🔴 {self.players[0].display_name} vs 🟡 {self.players[1].display_name}"
        embed = discord.Embed(title="Connect 4", description=f"{names}\n\n{header}\n" + "\n".join(rows), color=color or discord.Color.blue())
        embed.set_footer(text=footer or f"{self.players[self.turn].display_name}'s turn")
        return embed

    async def interaction_check(self, interaction):
        if interaction.user.id not in {p.id for p in self.players}:
            await interaction.response.send_message("You're not in this game.", ephemeral=True)
            return False
        if interaction.user.id != self.players[self.turn].id:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True

    def has_won(self, row, column, piece):
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            count = 1
            for sign in (1, -1):
                r, c = row + dr * sign, column + dc * sign
                while 0 <= r < 6 and 0 <= c < 7 and self.board[r][c] == piece:
                    count += 1
                    r, c = r + dr * sign, c + dc * sign
            if count >= 4:
                return True
        return False

    def finish(self):
        self.finished = True
        for item in self.children:
            item.disabled = True
        self.stop()

    async def play(self, interaction, column):
        if self.finished:
            return
        row = next((r for r in range(5, -1, -1) if self.board[r][column] == 0), None)
        if row is None:
            await interaction.response.send_message("That column is full.", ephemeral=True)
            return
        piece = self.turn + 1
        self.board[row][column] = piece
        if self.has_won(row, column, piece):
            self.finish()
            await interaction.response.edit_message(embed=self.render(f"🏆 {self.players[self.turn].display_name} wins!", discord.Color.gold()), view=self)
            return
        if all(cell for cell in self.board[0]):
            self.finish()
            await interaction.response.edit_message(embed=self.render("It's a draw.", discord.Color.light_grey()), view=self)
            return
        self.turn = 1 - self.turn
        await interaction.response.edit_message(embed=self.render(), view=self)

    async def on_timeout(self):
        if self.finished:
            return
        self.finish()
        if self.message:
            try:
                await self.message.edit(embed=self.render("Game ended: nobody moved in time.", discord.Color.light_grey()), view=self)
            except discord.HTTPException:
                pass


class DuelView(discord.ui.View):
    def __init__(self, first, second):
        super().__init__(timeout=180)
        self.players = [first, second]
        self.hp = [100, 100]
        self.guard = [False, False]
        self.heals = [2, 2]
        self.turn = 0
        self.log = "The duel begins."
        self.message = None
        self.finished = False

    def render(self, color=None):
        embed = discord.Embed(title="⚔️ Duel", description=self.log, color=color or discord.Color.red())
        for index, player in enumerate(self.players):
            filled = max(0, self.hp[index]) // 10
            bar = "█" * filled + "░" * (10 - filled)
            guard = " 🛡️" if self.guard[index] else ""
            embed.add_field(name=player.display_name, value=f"`{bar}` {max(0, self.hp[index])} HP{guard}")
        if not self.finished:
            embed.set_footer(text=f"{self.players[self.turn].display_name}'s turn")
        return embed

    async def interaction_check(self, interaction):
        if interaction.user.id not in {p.id for p in self.players}:
            await interaction.response.send_message("You're not in this duel.", ephemeral=True)
            return False
        if interaction.user.id != self.players[self.turn].id:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True

    async def advance(self, interaction):
        other = 1 - self.turn
        if self.hp[other] <= 0:
            self.finished = True
            for item in self.children:
                item.disabled = True
            self.log += f"\n🏆 **{self.players[self.turn].display_name}** wins!"
            self.stop()
            await interaction.response.edit_message(embed=self.render(discord.Color.gold()), view=self)
            return
        self.turn = other
        await interaction.response.edit_message(embed=self.render(), view=self)

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger)
    async def attack(self, interaction, button):
        me, other = self.turn, 1 - self.turn
        damage = random.randint(10, 25)
        note = ""
        if self.guard[other]:
            damage //= 2
            self.guard[other] = False
            note = " (blocked half)"
        self.hp[other] -= damage
        self.log = f"{self.players[me].display_name} hits {self.players[other].display_name} for {damage}{note}."
        await self.advance(interaction)

    @discord.ui.button(label="Guard", style=discord.ButtonStyle.primary)
    async def guard_button(self, interaction, button):
        self.guard[self.turn] = True
        self.log = f"{self.players[self.turn].display_name} raises a shield."
        await self.advance(interaction)

    @discord.ui.button(label="Heal", style=discord.ButtonStyle.success)
    async def heal(self, interaction, button):
        me = self.turn
        if self.heals[me] <= 0:
            await interaction.response.send_message("You're out of heals.", ephemeral=True)
            return
        self.heals[me] -= 1
        amount = random.randint(10, 20)
        self.hp[me] = min(100, self.hp[me] + amount)
        self.log = f"{self.players[me].display_name} heals {amount} HP ({self.heals[me]} heal(s) left)."
        await self.advance(interaction)

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        for item in self.children:
            item.disabled = True
        if self.message:
            self.log += "\nThe duel ended: nobody moved in time."
            try:
                await self.message.edit(embed=self.render(discord.Color.light_grey()), view=self)
            except discord.HTTPException:
                pass


class ReactionView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.author = author
        self.ready_at = None
        self.done = False
        self.message = None

    @discord.ui.button(label="Wait for it...", style=discord.ButtonStyle.secondary)
    async def press(self, interaction, button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This test belongs to someone else.", ephemeral=True)
            return
        self.done = True
        button.disabled = True
        self.stop()
        if self.ready_at is None:
            await interaction.response.edit_message(embed=discord.Embed(title="Too early!", description="You clicked before it turned green.", color=discord.Color.red()), view=self)
            return
        elapsed = int((time.monotonic() - self.ready_at) * 1000)
        rating = "Lightning" if elapsed < 250 else "Quick" if elapsed < 400 else "Average" if elapsed < 600 else "Sleepy"
        await interaction.response.edit_message(embed=discord.Embed(title=f"⚡ {elapsed} ms", description=f"{rating}.", color=discord.Color.green()), view=self)

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=discord.Embed(title="Timed out", color=discord.Color.light_grey()), view=self)
            except discord.HTTPException:
                pass


class FunMore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.busy = set()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Rating style commands
    @commands.command(name="roast")
    async def roast(self, ctx, member: discord.Member = None):
        """Roasts someone, all in good fun. Usage: !roast @user"""
        target = (member or ctx.author).display_name
        embed = discord.Embed(description=random.choice(ROASTS).format(t=f"**{discord.utils.escape_markdown(target)}**"), color=discord.Color.orange())
        embed.set_footer(text="Just a joke. Be kind out there.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="pickup", aliases=["pickupline"])
    async def pickup(self, ctx):
        """Sends a cheesy pickup line. Usage: !pickup"""
        await ctx.reply(embed=discord.Embed(title="💘 Pickup line", description=random.choice(PICKUPS), color=discord.Color.from_rgb(255, 105, 180)), mention_author=False)

    @commands.command(name="iq")
    async def iq(self, ctx, member: discord.Member = None):
        """Reveals someone's completely made-up IQ. Usage: !iq @user"""
        member = member or ctx.author
        score = 60 + stable("iq", member.id) % 121
        embed = discord.Embed(title="🧠 IQ test", description=f"**{discord.utils.escape_markdown(member.display_name)}** scored **{score}**.", color=discord.Color.blue())
        embed.set_footer(text="Not a real test. Not even close.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="luck")
    async def luck(self, ctx, member: discord.Member = None):
        """Shows how lucky someone is today. Usage: !luck @user"""
        member = member or ctx.author
        percent = stable("luck", member.id, today()) % 101
        filled = percent // 10
        bar = "🍀" * filled + "▫️" * (10 - filled)
        embed = discord.Embed(title="🍀 Luck today", description=f"{bar}\n**{discord.utils.escape_markdown(member.display_name)}** is **{percent}%** lucky.", color=discord.Color.green())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="vibe")
    async def vibe(self, ctx, member: discord.Member = None):
        """Checks someone's vibe for today. Usage: !vibe @user"""
        member = member or ctx.author
        percent = stable("vibe", member.id, today()) % 101
        label = "Immaculate" if percent >= 90 else "Great" if percent >= 70 else "Fine" if percent >= 40 else "Needs a snack" if percent >= 15 else "Do not disturb"
        embed = discord.Embed(title="✨ Vibe check", description=f"**{discord.utils.escape_markdown(member.display_name)}**: **{percent}%**, {label}.", color=discord.Color.purple())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="howcute")
    async def howcute(self, ctx, member: discord.Member = None):
        """Rates how cute someone is. Usage: !howcute @user"""
        member = member or ctx.author
        percent = stable("cute", member.id) % 51 + 50
        embed = discord.Embed(title="🥺 Cuteness meter", description=f"**{discord.utils.escape_markdown(member.display_name)}** is **{percent}%** cute.", color=discord.Color.from_rgb(255, 182, 193))
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="horoscope", aliases=["zodiac"])
    async def horoscope(self, ctx, sign: str):
        """Reads today's horoscope for a zodiac sign. Usage: !horoscope leo"""
        key = sign.lower()
        if key not in SIGNS:
            await ctx.reply("Pick a sign: " + ", ".join(SIGNS) + ".", mention_author=False)
            return
        seed = stable("horoscope", key, today())
        embed = discord.Embed(title=f"🔮 {key.title()} today", color=discord.Color.purple())
        embed.add_field(name="Mood", value=MOODS[seed % len(MOODS)])
        embed.add_field(name="Lucky number", value=str(seed // 7 % 99 + 1))
        embed.add_field(name="Lucky color", value=COLORS[seed // 11 % len(COLORS)])
        embed.add_field(name="Advice", value=ADVICE[seed // 13 % len(ADVICE)], inline=False)
        embed.set_footer(text="For fun only.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="quote", aliases=["inspire"])
    async def quote(self, ctx):
        """Shares a short inspirational line. Usage: !quote"""
        await ctx.reply(embed=discord.Embed(description=f"*{random.choice(QUOTES)}*", color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="catfact")
    async def catfact(self, ctx):
        """Tells a random cat fact. Usage: !catfact"""
        text = None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://catfact.ninja/fact") as response:
                    if response.status == 200:
                        text = (await response.json(content_type=None)).get("fact")
        except Exception:
            text = None
        text = text or "Cats sleep for about two thirds of their lives."
        await ctx.reply(embed=discord.Embed(title="🐱 Cat fact", description=text[:1000], color=discord.Color.orange()), mention_author=False)

    # Pranks and text tricks
    @commands.command(name="fakeban")
    async def fakeban(self, ctx, member: discord.Member):
        """Pretends to ban someone (nobody is banned). Usage: !fakeban @user"""
        embed = discord.Embed(title="🔨 Member banned", description=f"**{discord.utils.escape_markdown(member.display_name)}** has been banned by {discord.utils.escape_markdown(ctx.author.display_name)}.", color=discord.Color.red())
        embed.set_footer(text="Just kidding. Nobody was banned.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="hack")
    async def hack(self, ctx, member: discord.Member):
        """Runs a pretend hacking animation (all fake, nothing happens). Usage: !hack @user"""
        name = discord.utils.escape_markdown(member.display_name)
        steps = [
            f"Finding {name}'s IP address...",
            "IP: `999.999.999.999` (not real)",
            "Reading the secret diary... 📖",
            f"Email: `{re.sub(r'[^a-z0-9]', '', member.display_name.lower()) or 'user'}@example.invalid`",
            "Password: `hunter2` (just kidding)",
            "Stealing the last cookie... 🍪",
            "✅ Hack complete.\n*This was a joke. Nothing was hacked and nothing was read.*",
        ]
        message = await ctx.reply(embed=discord.Embed(title="💻 Hacking...", description=steps[0], color=discord.Color.dark_green()), mention_author=False, allowed_mentions=NO_MENTIONS)
        for index in range(1, len(steps)):
            await asyncio.sleep(1.2)
            embed = discord.Embed(title="💻 Hacking..." if index < len(steps) - 1 else "💻 Done", description="\n".join(steps[: index + 1]), color=discord.Color.dark_green())
            try:
                await message.edit(embed=embed, allowed_mentions=NO_MENTIONS)
            except discord.HTTPException:
                return

    @commands.command(name="lenny")
    async def lenny(self, ctx, *, text: str = ""):
        """Adds a lenny face to your message. Usage: !lenny nice"""
        await ctx.send(f"{text[:300]} ( ͡° ͜ʖ ͡°)".strip(), allowed_mentions=NO_MENTIONS)

    @commands.command(name="shrug")
    async def shrug(self, ctx, *, text: str = ""):
        """Adds a shrug to your message. Usage: !shrug no idea"""
        await ctx.send(f"{text[:300]} ¯\\\\\\_(ツ)\\_/¯".strip(), allowed_mentions=NO_MENTIONS)

    @commands.command(name="tableflip")
    async def tableflip(self, ctx, *, text: str = ""):
        """Flips a table. Usage: !tableflip so annoying"""
        await ctx.send(f"{text[:300]} (╯°□°）╯︵ ┻━┻".strip(), allowed_mentions=NO_MENTIONS)

    @commands.command(name="unflip")
    async def unflip(self, ctx, *, text: str = ""):
        """Puts the table back. Usage: !unflip sorry"""
        await ctx.send(f"{text[:300]} ┬─┬ ノ( ゜-゜ノ)".strip(), allowed_mentions=NO_MENTIONS)

    @commands.command(name="shout")
    async def shout(self, ctx, *, text: str):
        """Shouts your message in capital letters. Usage: !shout hello everyone"""
        await ctx.send(f"📢 **{text[:300].upper()}!!!**", allowed_mentions=NO_MENTIONS)

    @commands.command(name="spoiler")
    async def spoiler(self, ctx, *, text: str):
        """Hides each word of your message behind a spoiler. Usage: !spoiler the butler did it"""
        words = [word.replace("|", "") for word in text[:1500].split()]
        words = [word for word in words if word]
        if not words:
            await ctx.reply("Give some text to hide.", mention_author=False)
            return
        await ctx.send(" ".join(f"||{word}||" for word in words)[:1990], allowed_mentions=NO_MENTIONS)

    @commands.command(name="bubble", aliases=["bubblewrap"])
    async def bubble(self, ctx, *, text: str):
        """Turns your message into bubble wrap, one pop per letter. Usage: !bubble pop me"""
        text = text[:300]
        result = " ".join("".join(f"||{ch}||" if not ch.isspace() and ch != "|" else (" " if ch.isspace() else "") for ch in word) for word in text.split())
        if not result:
            await ctx.reply("Give some text to wrap.", mention_author=False)
            return
        await ctx.send(result[:1990], allowed_mentions=NO_MENTIONS)

    @commands.command(name="wheel")
    async def wheel(self, ctx, *, options: str):
        """Spins a wheel with your comma-separated options. Usage: !wheel pizza, sushi, tacos"""
        choices = []
        for part in options.split(","):
            part = part.strip()
            if part and part not in choices:
                choices.append(part[:80])
        if not 2 <= len(choices) <= 25:
            await ctx.reply("Give between 2 and 25 different options, separated by commas.", mention_author=False)
            return
        picked = random.choice(choices)
        embed = discord.Embed(title="🎡 The wheel lands on...", description=f"**{discord.utils.escape_markdown(picked)}**", color=discord.Color.gold())
        embed.set_footer(text=f"{len(choices)} options")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="russianroulette", aliases=["rroulette"])
    async def russianroulette(self, ctx):
        """Pulls the trigger in a harmless game of chance. Usage: !russianroulette"""
        chamber = random.randint(1, 6)
        if chamber == 1:
            embed = discord.Embed(title="💥 Bang!", description=f"{discord.utils.escape_markdown(ctx.author.display_name)} lost this round. (Nothing happens in real life.)", color=discord.Color.red())
        else:
            embed = discord.Embed(title="🔫 Click.", description=f"{discord.utils.escape_markdown(ctx.author.display_name)} survived. Chamber {chamber} was empty.", color=discord.Color.green())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="neverhaveiever", aliases=["nhie"])
    async def neverhaveiever(self, ctx):
        """Posts a Never Have I Ever prompt. Usage: !neverhaveiever"""
        message = await ctx.send(embed=discord.Embed(title="🙈 Never have I ever", description=random.choice(NEVER_HAVE_I_EVER), color=discord.Color.light_grey()))
        for emoji in ("✅", "❌"):
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                break

    @commands.command(name="thisorthat", aliases=["tot"])
    async def thisorthat(self, ctx):
        """Asks a this-or-that question with reactions. Usage: !thisorthat"""
        first, second = random.choice(THIS_OR_THAT)
        embed = discord.Embed(title="🤔 This or that?", description=f"🅰️ **{first}**\n🅱️ **{second}**", color=discord.Color.light_grey())
        message = await ctx.send(embed=embed)
        for emoji in ("🅰️", "🅱️"):
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                break

    # Chat games
    @commands.command(name="hangman")
    async def hangman(self, ctx):
        """Plays hangman: type single letters or the whole word in chat. Usage: !hangman"""
        key = ("hangman", ctx.channel.id)
        if key in self.busy:
            await ctx.reply("There's already a hangman game in this channel.", mention_author=False)
            return
        self.busy.add(key)
        try:
            word = random.choice(WORDS)
            guessed, wrong = [], 0

            def render(footer):
                shown = " ".join(ch if ch in guessed else "_" for ch in word)
                embed = discord.Embed(title="Hangman", description=f"```\n{GALLOWS[wrong]}\n```\n`{shown}`", color=discord.Color.dark_orange())
                embed.add_field(name="Guessed", value=" ".join(guessed) or "none")
                embed.set_footer(text=footer)
                return embed

            message = await ctx.send(embed=render("Type a letter or the full word. 6 misses and it's over."))

            def check(m):
                text = m.content.strip().lower()
                return m.channel.id == ctx.channel.id and not m.author.bot and text.isalpha() and (len(text) == 1 or len(text) == len(word))

            while True:
                try:
                    guess_message = await self.bot.wait_for("message", check=check, timeout=60)
                except asyncio.TimeoutError:
                    await message.edit(embed=render(f"Time's up. The word was {word}."))
                    return
                guess = guess_message.content.strip().lower()
                if len(guess) == 1:
                    if guess in guessed:
                        continue
                    guessed.append(guess)
                    if guess not in word:
                        wrong += 1
                elif guess == word:
                    guessed.extend(ch for ch in word if ch not in guessed)
                else:
                    wrong += 1
                if all(ch in guessed for ch in word):
                    await message.edit(embed=render(f"🎉 {guess_message.author.display_name} solved it: {word}!"))
                    return
                if wrong >= 6:
                    await message.edit(embed=render(f"Game over. The word was {word}."))
                    return
                await message.edit(embed=render(f"{6 - wrong} miss(es) left."))
        finally:
            self.busy.discard(key)

    @commands.command(name="typing", aliases=["typerace"])
    async def typing(self, ctx):
        """Race to type a sentence exactly. First to finish wins. Usage: !typing"""
        key = ("typing", ctx.channel.id)
        if key in self.busy:
            await ctx.reply("A typing race is already running here.", mention_author=False)
            return
        self.busy.add(key)
        try:
            sentence = random.choice(SENTENCES)
            await ctx.send(embed=discord.Embed(title="⌨️ Typing race", description=f"First to type this exactly wins (30 seconds):\n\n`{sentence}`", color=discord.Color.blue()))
            started = time.monotonic()

            def check(m):
                return m.channel.id == ctx.channel.id and not m.author.bot and m.content.strip() == sentence

            try:
                winner = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send("Nobody typed it in time.")
                return
            seconds = max(0.1, time.monotonic() - started)
            wpm = round(len(sentence.split()) / (seconds / 60))
            await winner.reply(f"🏁 {discord.utils.escape_markdown(winner.author.display_name)} won in {seconds:.1f}s (about {wpm} WPM).", mention_author=False, allowed_mentions=NO_MENTIONS)
        finally:
            self.busy.discard(key)

    @commands.command(name="mathrace")
    async def mathrace(self, ctx):
        """Race to solve a math problem. First correct answer wins. Usage: !mathrace"""
        key = ("math", ctx.channel.id)
        if key in self.busy:
            await ctx.reply("A math race is already running here.", mention_author=False)
            return
        self.busy.add(key)
        try:
            a, b = random.randint(2, 30), random.randint(2, 30)
            op = random.choice("+-*")
            answer = a + b if op == "+" else a - b if op == "-" else a * b
            symbol = "×" if op == "*" else op
            await ctx.send(embed=discord.Embed(title="🧮 Math race", description=f"What is **{a} {symbol} {b}**? (20 seconds)", color=discord.Color.blue()))

            def check(m):
                return m.channel.id == ctx.channel.id and not m.author.bot and m.content.strip() == str(answer)

            try:
                winner = await self.bot.wait_for("message", check=check, timeout=20)
            except asyncio.TimeoutError:
                await ctx.send(f"Nobody got it. The answer was **{answer}**.")
                return
            await winner.reply(f"✅ {discord.utils.escape_markdown(winner.author.display_name)} got it: **{answer}**.", mention_author=False, allowed_mentions=NO_MENTIONS)
        finally:
            self.busy.discard(key)

    @commands.command(name="reactiontest", aliases=["reaction"])
    async def reactiontest(self, ctx):
        """Tests your reaction time with a button. Usage: !reactiontest"""
        view = ReactionView(ctx.author)
        view.message = await ctx.reply(embed=discord.Embed(title="⚡ Reaction test", description="Wait until the button turns green, then click it. Don't click early.", color=discord.Color.blue()), view=view, mention_author=False)
        await asyncio.sleep(random.uniform(2, 6))
        if view.done:
            return
        button = view.children[0]
        button.label = "CLICK!"
        button.style = discord.ButtonStyle.success
        view.ready_at = time.monotonic()
        try:
            await view.message.edit(view=view)
        except discord.HTTPException:
            view.ready_at = None

    @commands.command(name="connect4", aliases=["c4"])
    async def connect4(self, ctx, opponent: discord.Member):
        """Plays Connect 4 against another member with buttons. Usage: !connect4 @user"""
        if opponent.bot or opponent.id == ctx.author.id:
            await ctx.reply("Pick another member to play against.", mention_author=False)
            return
        view = Connect4View(ctx.author, opponent)
        view.message = await ctx.send(embed=view.render(), view=view, allowed_mentions=NO_MENTIONS)

    @commands.command(name="duel")
    async def duel(self, ctx, opponent: discord.Member):
        """Fights another member in a turn-based button duel. Usage: !duel @user"""
        if opponent.bot or opponent.id == ctx.author.id:
            await ctx.reply("Pick another member to duel.", mention_author=False)
            return
        view = DuelView(ctx.author, opponent)
        view.message = await ctx.send(embed=view.render(), view=view, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(FunMore(bot))
