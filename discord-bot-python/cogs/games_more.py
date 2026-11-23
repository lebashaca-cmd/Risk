"""More games to play in chat. Everything here is for fun and keeps no coins or permanent data.

highcard, mastermind, cups, hotcold, drawduel and memory.
"""
import asyncio
import random
import time

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error

CARD_NAMES = {11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}
SUITS = ["♠️", "♥️", "♦️", "♣️"]
COLOURS = {"r": "\U0001F7E5", "o": "\U0001F7E7", "y": "\U0001F7E8", "g": "\U0001F7E9", "b": "\U0001F7E6", "p": "\U0001F7EA"}
MEMORY_ICONS = ["\U0001F34E", "\U0001F680", "\U0001F433", "⚽", "\U0001F3B2", "\U0001F525", "\U0001F319", "\U0001F31F", "\U0001F355", "\U0001F3B8"]


def card(value):
    return f"{CARD_NAMES.get(value, value)}{random.choice(SUITS)}"


class GamesMore(commands.Cog, name="GamesMore"):
    """Quick chat games: cards, code breaking, a shell game and reaction duels."""

    def __init__(self, bot):
        self.bot = bot
        self.mind = {}  # (guild, user) -> {"code": str, "tries": int, "log": [str]}
        self.hot = {}  # (guild, user) -> {"number": int, "tries": int}
        self.busy = set()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # ------------------------------------------------------------------ highcard
    @commands.command(name="highcard")
    @commands.guild_only()
    async def highcard(self, ctx, opponent: discord.Member = None):
        """Draws a card each against Risk or another member. Higher card wins, ace is high. Usage: !highcard | !highcard @user"""
        if opponent is not None and (opponent.bot or opponent.id == ctx.author.id):
            raise ModError("Pick another member, or leave it blank to play Risk.")
        name = opponent.display_name if opponent else "Risk"
        mine, theirs = random.randint(2, 14), random.randint(2, 14)
        result = f"**{ctx.author.display_name}** wins!" if mine > theirs else f"**{name}** wins!" if theirs > mine else "It's a tie. Draw again!"
        embed = discord.Embed(title="High card", description=f"{ctx.author.display_name}: {card(mine)}\n{name}: {card(theirs)}\n\n{result}", color=discord.Color.gold())
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ------------------------------------------------------------------ mastermind
    @commands.group(name="mastermind", invoke_without_command=True)
    @commands.guild_only()
    async def mastermind(self, ctx):
        """Break a secret 4-colour code in 10 tries. Colours: r o y g b p. Usage: !mastermind start | !mastermind guess rgby | !mastermind quit"""
        await ctx.reply(f"Crack the 4-colour code in 10 tries with `{ctx.clean_prefix}mastermind start`, then `{ctx.clean_prefix}mastermind guess rgby`. Colours: " + " ".join(f"{k}={v}" for k, v in COLOURS.items()) + ". ⚫ = right colour, right place. ⚪ = right colour, wrong place.", mention_author=False)

    @mastermind.command(name="start")
    async def mastermind_start(self, ctx):
        """Starts a new Mastermind game. Usage: !mastermind start"""
        self.mind[(ctx.guild.id, ctx.author.id)] = {"code": "".join(random.choices(list(COLOURS), k=4)), "tries": 0, "log": []}
        await ctx.reply(f"I picked a code of 4 colours (they can repeat). Guess with `{ctx.clean_prefix}mastermind guess rgby`. Colours: " + " ".join(f"{k}={v}" for k, v in COLOURS.items()), mention_author=False)

    @mastermind.command(name="guess")
    async def mastermind_guess(self, ctx, code: str):
        """Guesses the code. Usage: !mastermind guess rgby"""
        game = self.mind.get((ctx.guild.id, ctx.author.id))
        if game is None:
            raise ModError(f"You have no game. Start one with `{ctx.clean_prefix}mastermind start`.")
        code = code.lower()
        if len(code) != 4 or any(c not in COLOURS for c in code):
            raise ModError("A guess is 4 letters from: " + " ".join(COLOURS))
        exact = sum(a == b for a, b in zip(code, game["code"]))
        common = sum(min(code.count(c), game["code"].count(c)) for c in COLOURS)
        game["tries"] += 1
        game["log"].append("".join(COLOURS[c] for c in code) + "  " + "⚫" * exact + "⚪" * (common - exact))
        board = "\n".join(game["log"])
        if exact == 4:
            del self.mind[(ctx.guild.id, ctx.author.id)]
            await ctx.reply(f"{board}\n\n\U0001F389 Cracked in {game['tries']} {'try' if game['tries'] == 1 else 'tries'}!", mention_author=False)
        elif game["tries"] >= 10:
            del self.mind[(ctx.guild.id, ctx.author.id)]
            await ctx.reply(f"{board}\n\nOut of tries. The code was {''.join(COLOURS[c] for c in game['code'])}.", mention_author=False)
        else:
            await ctx.reply(f"{board}\n\n{10 - game['tries']} tries left.", mention_author=False)

    @mastermind.command(name="quit")
    async def mastermind_quit(self, ctx):
        """Gives up and shows the code. Usage: !mastermind quit"""
        game = self.mind.pop((ctx.guild.id, ctx.author.id), None)
        if game is None:
            raise ModError("You have no game running.")
        await ctx.reply(f"The code was {''.join(COLOURS[c] for c in game['code'])}.", mention_author=False)

    # ------------------------------------------------------------------ cups
    @commands.command(name="cups")
    @commands.guild_only()
    async def cups(self, ctx, pick: int):
        """The shell game: a ball is under one of 3 cups. Pick 1, 2 or 3. Usage: !cups 2"""
        if pick not in (1, 2, 3):
            raise ModError("Pick cup 1, 2 or 3.")
        ball = random.randint(1, 3)
        row = " ".join("⚽" if i == ball else "\U0001F964" for i in (1, 2, 3))
        await ctx.reply(f"{row}\n" + ("\U0001F389 You found it!" if pick == ball else f"Nope, the ball was under cup {ball}."), mention_author=False)

    # ------------------------------------------------------------------ hotcold
    @commands.group(name="hotcold", invoke_without_command=True)
    @commands.guild_only()
    async def hotcold(self, ctx):
        """Find a secret number from 1 to 100 with hot and cold hints. Usage: !hotcold start | !hotcold guess 42"""
        await ctx.reply(f"Start with `{ctx.clean_prefix}hotcold start`, then `{ctx.clean_prefix}hotcold guess 50`.", mention_author=False)

    @hotcold.command(name="start")
    async def hotcold_start(self, ctx):
        """Starts a hot-and-cold game. Usage: !hotcold start"""
        self.hot[(ctx.guild.id, ctx.author.id)] = {"number": random.randint(1, 100), "tries": 0}
        await ctx.reply(f"I'm thinking of a number from 1 to 100. Guess with `{ctx.clean_prefix}hotcold guess 50`.", mention_author=False)

    @hotcold.command(name="guess")
    async def hotcold_guess(self, ctx, number: int):
        """Guesses the number. Usage: !hotcold guess 42"""
        game = self.hot.get((ctx.guild.id, ctx.author.id))
        if game is None:
            raise ModError(f"You have no game. Start one with `{ctx.clean_prefix}hotcold start`.")
        if not 1 <= number <= 100:
            raise ModError("Guess a number from 1 to 100.")
        game["tries"] += 1
        gap = abs(number - game["number"])
        if gap == 0:
            del self.hot[(ctx.guild.id, ctx.author.id)]
            await ctx.reply(f"\U0001F389 Yes, it was **{number}**! You got it in {game['tries']} {'try' if game['tries'] == 1 else 'tries'}.", mention_author=False)
            return
        hint = "\U0001F525 Burning hot" if gap <= 3 else "\U0001F975 Hot" if gap <= 8 else "\U0001F642 Warm" if gap <= 20 else "\U0001F976 Cold" if gap <= 40 else "\U0001F9CA Freezing"
        await ctx.reply(f"{hint}. Try {'higher' if number < game['number'] else 'lower'}.", mention_author=False)

    # ------------------------------------------------------------------ drawduel
    @commands.command(name="drawduel")
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def drawduel(self, ctx, opponent: discord.Member):
        """Reaction duel: wait for the signal, then type BANG first. Typing early loses. Usage: !drawduel @user"""
        if opponent.bot or opponent.id == ctx.author.id:
            raise ModError("Pick another member to duel.")
        players = {ctx.author.id: ctx.author, opponent.id: opponent}
        await ctx.send(f"\U0001F920 {ctx.author.display_name} vs {opponent.display_name}. When I say **DRAW**, the first to type `bang` wins. Typing early loses.", allowed_mentions=NO_MENTIONS)
        end = time.monotonic() + random.uniform(3, 8)

        def early(m):
            return m.channel == ctx.channel and m.author.id in players and m.content.lower().strip() == "bang"

        try:
            cheat = await self.bot.wait_for("message", check=early, timeout=max(0.1, end - time.monotonic()))
            other = next(p for i, p in players.items() if i != cheat.author.id)
            await ctx.send(f"Too early! **{cheat.author.display_name}** loses. **{other.display_name}** wins.", allowed_mentions=NO_MENTIONS)
            return
        except asyncio.TimeoutError:
            pass
        await ctx.send("**DRAW!**")
        start = time.monotonic()
        try:
            winner = await self.bot.wait_for("message", check=early, timeout=8)
        except asyncio.TimeoutError:
            await ctx.send("Nobody drew. It's a draw.")
            return
        await ctx.send(f"\U0001F3C6 **{winner.author.display_name}** wins in {time.monotonic() - start:.2f}s!", allowed_mentions=NO_MENTIONS)

    # ------------------------------------------------------------------ memory
    @commands.command(name="memory")
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.user)
    async def memory(self, ctx, length: int = 5):
        """Memorise a row of emoji, then type them back in order. Usage: !memory | !memory 8 (3 to 8 emoji)"""
        length = max(3, min(length, 8))
        icons = [random.choice(MEMORY_ICONS) for _ in range(length)]
        shown = await ctx.reply("Remember: " + " ".join(icons), mention_author=False)
        await asyncio.sleep(1.2 * length)
        try:
            await shown.edit(content="Now type them back, with spaces between. (Emoji names don't count, paste the emoji.)")
        except discord.HTTPException:
            pass

        def mine(m):
            return m.author.id == ctx.author.id and m.channel == ctx.channel

        try:
            answer = await self.bot.wait_for("message", check=mine, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(f"Time's up. It was {' '.join(icons)}")
            return
        right = answer.content.split() == icons
        await answer.reply("\U0001F389 Perfect memory!" if right else f"Not quite. It was {' '.join(icons)}", mention_author=False)


async def setup(bot):
    await bot.add_cog(GamesMore(bot))
