"""More fun commands: moods, slots, a pet, emoji quizzes, higher/lower and silly generators."""
import asyncio
import hashlib
import random
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error

MOODS = [("Sunny", "feeling bright and ready for anything"), ("Chaotic", "unpredictable, proceed with caution"), ("Sleepy", "running on a very low battery"), ("Hyped", "bouncing off the walls"),
         ("Chill", "completely unbothered"), ("Dramatic", "everything is a big deal today"), ("Cozy", "blanket, snacks and good vibes"), ("Focused", "locked in and productive"),
         ("Goofy", "laughing at things that aren't funny"), ("Mysterious", "keeping everyone guessing")]
POWERS = ["can talk to houseplants", "never loses a sock again", "always picks the fastest checkout line", "can pause time for exactly 5 seconds", "turns any food into pizza",
          "is never on hold for more than a minute", "can hear Wi-Fi signal strength", "always finds the TV remote", "can fly, but only 2 feet off the ground", "knows what song is stuck in your head"]
WEAKNESSES = ["gets distracted by every dog", "can't whisper", "laughs at the wrong moments", "forgets why they walked into a room", "is afraid of spoilers",
              "needs 12 hours of sleep", "can't resist one more episode", "loses every game of rock paper scissors", "always says 'you too' when the waiter says enjoy"]
PET_KINDS = [("fox", "🦊"), ("cat", "🐱"), ("dog", "🐶"), ("panda", "🐼"), ("frog", "🐸"), ("owl", "🦉"), ("dragon", "🐲"), ("bunny", "🐰"), ("penguin", "🐧"), ("axolotl", "🦎")]
PET_NAMES = ["Biscuit", "Pixel", "Nova", "Mochi", "Juniper", "Waffles", "Comet", "Pickle", "Echo", "Sprout", "Pudding", "Zigzag"]
PET_TRAITS = ["loves naps", "steals snacks", "hates mondays", "is a great listener", "chases shadows", "collects shiny things", "sings off key", "is secretly very smart"]
ADJECTIVES = ["Sneaky", "Mighty", "Wobbly", "Cosmic", "Fluffy", "Grumpy", "Turbo", "Sleepy", "Spicy", "Legendary", "Tiny", "Electric"]
NOUNS = ["Noodle", "Falcon", "Muffin", "Wizard", "Pickle", "Goblin", "Penguin", "Toaster", "Ninja", "Walrus", "Bandit", "Potato"]
ACRONYM_WORDS = {
    "a": ["Awesome", "Angry", "Absolutely", "Amazing"], "b": ["Banana", "Big", "Bouncy", "Brave"], "c": ["Cats", "Cookies", "Chaos", "Cozy"], "d": ["Donuts", "Dancing", "Dramatic", "Dreamy"],
    "e": ["Eating", "Energetic", "Elephants", "Epic"], "f": ["Fluffy", "Friends", "Fries", "Funky"], "g": ["Giant", "Goblins", "Gaming", "Giggly"], "h": ["Happy", "Hamsters", "Hungry", "Hot"],
    "i": ["Ice cream", "Itchy", "Invisible", "Incredible"], "j": ["Jumping", "Jelly", "Jolly", "Jazzy"], "k": ["Kittens", "Kind", "Kicking", "Karaoke"], "l": ["Lazy", "Llamas", "Laughing", "Lucky"],
    "m": ["Memes", "Mighty", "Moonlit", "Muffins"], "n": ["Ninjas", "Noodles", "Nice", "Nervous"], "o": ["Octopus", "Odd", "Orange", "Obvious"], "p": ["Pizza", "Penguins", "Playing", "Peppy"],
    "q": ["Quiet", "Quacking", "Quirky", "Quick"], "r": ["Robots", "Running", "Rainbow", "Ridiculous"], "s": ["Sleepy", "Snacks", "Sneaky", "Spinning"], "t": ["Tacos", "Tiny", "Turtles", "Tickling"],
    "u": ["Unicorns", "Ugly", "Unusual", "Upbeat"], "v": ["Very", "Vampires", "Vibing", "Velvet"], "w": ["Wizards", "Waffles", "Wobbly", "Wild"], "x": ["Xtra", "X-ray", "Xylophone", "Xenial"],
    "y": ["Yelling", "Yummy", "Yawning", "Yodeling"], "z": ["Zebras", "Zany", "Zooming", "Zombies"],
}
EMOJI_QUIZ = [("🦁👑", ["lion king", "the lion king"]), ("🕷️🧑", ["spiderman", "spider-man", "spider man"]), ("🚢🧊", ["titanic"]), ("🐠🔍", ["finding nemo", "nemo"]),
              ("🧙‍♂️💍", ["lord of the rings", "the lord of the rings"]), ("🍎📱", ["apple", "iphone"]), ("🐀👨‍🍳", ["ratatouille"]), ("⚡👓🧹", ["harry potter"]),
              ("❄️👸", ["frozen"]), ("🦇🧑", ["batman"]), ("🏴‍☠️🦜", ["pirates of the caribbean", "pirate"]), ("🤖❤️🌱", ["wall-e", "walle", "wall e"]),
              ("🥶🍦", ["ice cream"]), ("🌧️☂️", ["umbrella", "rain"]), ("🔥🐉", ["dragon"]), ("🎅🦌", ["santa", "santa claus", "reindeer"])]
SUS_LINES = ["{t} was not the impostor.", "{t} was the impostor.", "{t} was seen venting. Very suspicious.", "{t} said 'trust me' way too fast.", "{t} was doing tasks (probably).", "{t} acted way too calm during the meeting."]
SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎", "7️⃣"]
BIG = {c: f":regional_indicator_{c}:" for c in "abcdefghijklmnopqrstuvwxyz"}
BIG.update({"0": ":zero:", "1": ":one:", "2": ":two:", "3": ":three:", "4": ":four:", "5": ":five:", "6": ":six:", "7": ":seven:", "8": ":eight:", "9": ":nine:", " ": "   ", "!": ":exclamation:", "?": ":question:"})


def seeded(user_id, topic):
    """A number that is the same for one person, one topic and one day, so results don't change on every try."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return int(hashlib.sha256(f"{user_id}:{topic}:{day}".encode()).hexdigest()[:12], 16)


class HigherLower(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=45)
        self.author_id = author_id
        self.number = random.randint(1, 100)
        self.streak = 0
        self.message = None

    def text(self, note=""):
        return f"{note}\nThe number is **{self.number}** (1 to 100). Is the next one higher or lower? Streak: **{self.streak}**".strip()

    async def guess(self, interaction, higher):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This game is for someone else. Start your own with `hilo`.", ephemeral=True)
            return
        new = random.randint(1, 100)
        if new == self.number or (new > self.number) == higher:
            self.streak += 1
            note = f"Correct, it was **{new}**."
            self.number = new
            await interaction.response.edit_message(content=self.text(note), view=self)
        else:
            for child in self.children:
                child.disabled = True
            self.stop()
            await interaction.response.edit_message(content=f"It was **{new}**. Game over with a streak of **{self.streak}**.", view=self)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.secondary)
    async def higher(self, interaction, button):
        await self.guess(interaction, True)

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.secondary)
    async def lower(self, interaction, button):
        await self.guess(interaction, False)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class FunPlus(commands.Cog, name="FunPlus"):
    """More fun commands."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    @commands.command(name="mood")
    async def mood(self, ctx, member: discord.Member = None):
        """Reads someone's mood of the day (it stays the same all day). Usage: !mood @user"""
        member = member or ctx.author
        name, line = MOODS[seeded(member.id, "mood") % len(MOODS)]
        await ctx.reply(f"{member.display_name}'s mood today: **{name}**, {line}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="freespin", aliases=["spin"])
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def freespin(self, ctx):
        """Pulls a slot machine just for fun, no coins needed. Usage: !freespin"""
        reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        if len(set(reels)) == 1:
            result = "Jackpot! Three of a kind."
        elif len(set(reels)) == 2:
            result = "Two of a kind. So close."
        else:
            result = "No match. Try again."
        await ctx.reply(f"🎰 | {' | '.join(reels)} |\n{result}", mention_author=False)

    @commands.command(name="acronym")
    async def acronym(self, ctx, *, word: str):
        """Makes a silly acronym out of a word. Usage: !acronym risk"""
        letters = list(word.lower().replace(" ", ""))[:12]
        if not letters or any(c not in ACRONYM_WORDS for c in letters):
            raise ModError("Use a word made of the letters a to z (up to 12 letters).")
        expanded = " ".join(random.choice(ACRONYM_WORDS[c]) for c in letters)
        await ctx.reply(f"**{''.join(letters).upper()}**: {expanded}", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="superpower", aliases=["power"])
    async def superpower(self, ctx, member: discord.Member = None):
        """Gives someone a superpower and a weakness for the day. Usage: !superpower @user"""
        member = member or ctx.author
        seed = seeded(member.id, "power")
        await ctx.reply(f"**{member.display_name}** {POWERS[seed % len(POWERS)]}, but {WEAKNESSES[(seed // 7) % len(WEAKNESSES)]}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="nickgen", aliases=["funnick"])
    async def nickgen(self, ctx, member: discord.Member = None):
        """Suggests a silly nickname. Usage: !nickgen @user"""
        member = member or ctx.author
        await ctx.reply(f"{member.display_name} could be **{random.choice(ADJECTIVES)} {random.choice(NOUNS)}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="pet")
    async def pet(self, ctx, member: discord.Member = None):
        """Shows the pet that picked you (the same one all day). Usage: !pet @user"""
        member = member or ctx.author
        seed = seeded(member.id, "pet")
        kind, emoji = PET_KINDS[seed % len(PET_KINDS)]
        name = PET_NAMES[(seed // 11) % len(PET_NAMES)]
        trait = PET_TRAITS[(seed // 131) % len(PET_TRAITS)]
        stats = {"Energy": seed % 100, "Cuteness": (seed // 3) % 100, "Chaos": (seed // 5) % 100}
        embed = discord.Embed(title=f"{emoji} {name} the {kind}", description=f"{name} {trait}.", color=discord.Color.light_grey())
        for label, value in stats.items():
            embed.add_field(name=label, value=f"{value}/100")
        embed.set_footer(text=f"{member.display_name}'s pet for today")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="emojiquiz", aliases=["eq"])
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def emojiquiz(self, ctx):
        """Guess the movie, thing or character from emoji. Usage: !emojiquiz"""
        emojis, answers = random.choice(EMOJI_QUIZ)
        await ctx.send(f"What does this mean? {emojis}\nYou have 20 seconds. Type your answer.")

        def check(message):
            return message.channel == ctx.channel and not message.author.bot and message.content.lower().strip() in answers

        try:
            winner = await self.bot.wait_for("message", check=check, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send(f"Time's up. It was **{answers[0]}**.")
            return
        await ctx.send(f"{winner.author.mention} got it: **{answers[0]}**!", allowed_mentions=discord.AllowedMentions(users=[winner.author]))

    @commands.command(name="hilo", aliases=["higherlower"])
    async def hilo(self, ctx):
        """Guess if the next number is higher or lower, with buttons. Usage: !hilo"""
        view = HigherLower(ctx.author.id)
        view.message = await ctx.send(view.text("Let's play."), view=view)

    @commands.command(name="aesthetic", aliases=["vapor"])
    async def aesthetic(self, ctx, *, text: str):
        """Writes text in wide aesthetic letters. Usage: !aesthetic good vibes"""
        wide = "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else ("　" if c == " " else c) for c in text[:150])
        await ctx.reply(wide, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="bigtext", aliases=["bigletters"])
    async def bigtext(self, ctx, *, text: str):
        """Writes text in big emoji letters. Usage: !bigtext hello"""
        text = text.lower()[:25]
        if not any(c in BIG and c != " " for c in text):
            raise ModError("Use letters, numbers, `!` or `?`.")
        await ctx.reply(" ".join(BIG.get(c, "") for c in text if c in BIG), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="sus")
    async def sus(self, ctx, member: discord.Member = None):
        """Says how suspicious someone is. Usage: !sus @user"""
        member = member or ctx.author
        line = SUS_LINES[seeded(member.id, "sus") % len(SUS_LINES)].format(t=member.display_name)
        await ctx.reply(f"📮 {line}", mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(FunPlus(bot))
