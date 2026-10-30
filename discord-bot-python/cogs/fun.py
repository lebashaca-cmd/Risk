import hashlib
import html
import random
import re

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error

EIGHT_BALL = [
    "It is certain.", "Without a doubt.", "Yes, definitely.", "You can rely on it.", "Most likely.",
    "Outlook good.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.", "Don't count on it.", "My reply is no.",
    "My sources say no.", "Outlook not so good.", "Very doubtful.",
]

JOKES = [
    "Why don't scientists trust atoms? They make up everything.",
    "I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.",
    "Why did the developer go broke? He used up all his cache.",
    "There are 10 kinds of people: those who know binary and those who don't.",
    "I would tell you a UDP joke, but you might not get it.",
    "Why do Java developers wear glasses? Because they can't C#.",
    "A SQL query walks into a bar, sees two tables and asks: can I join you?",
    "Why was the math book sad? It had too many problems.",
    "What do you call a fake noodle? An impasta.",
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "How does a computer get drunk? It takes screenshots.",
    "What's a programmer's favorite hangout? The Foo Bar.",
    "Why did the bike fall over? It was two tired.",
    "I used to hate facial hair, but then it grew on me.",
]

FACTS = [
    "Honey never spoils. Edible honey has been found in ancient Egyptian tombs.",
    "Octopuses have three hearts and blue blood.",
    "A day on Venus is longer than its year.",
    "Bananas are berries, but strawberries aren't.",
    "The Eiffel Tower grows about 15 cm taller in summer because metal expands in heat.",
    "Wombat droppings are cube-shaped.",
    "There are more possible chess games than atoms in the observable universe.",
    "Sharks existed before trees.",
    "A group of flamingos is called a flamboyance.",
    "The first computer bug was a real moth found in a Harvard Mark II in 1947.",
    "Lightning strikes the Earth around 8 million times a day.",
    "Your stomach gets a new lining every few days.",
    "The shortest war in history lasted about 38 minutes.",
    "Sloths can hold their breath longer than dolphins.",
    "Scotland's national animal is the unicorn.",
]

WYR = [
    "Would you rather always be 10 minutes late or 20 minutes early?",
    "Would you rather have unlimited pizza or unlimited tacos for life?",
    "Would you rather be able to fly or be invisible?",
    "Would you rather never use social media again or never watch another movie?",
    "Would you rather fight one horse-sized duck or a hundred duck-sized horses?",
    "Would you rather lose your phone or lose your wallet?",
    "Would you rather know how you die or when you die?",
    "Would you rather only whisper or only shout?",
    "Would you rather have a rewind button or a pause button for your life?",
    "Would you rather live without music or without movies?",
]

ACTIONS = {
    "hug": ["{a} gives {b} a big hug.", "{a} wraps {b} in a warm hug."],
    "pat": ["{a} pats {b} on the head.", "{a} gently pats {b}."],
    "slap": ["{a} slaps {b} with a wet noodle.", "{a} gives {b} a dramatic slap. It was mostly air."],
    "bonk": ["{a} bonks {b}. Go to horny jail.", "{a} bonks {b} with a rubber hammer."],
    "highfive": ["{a} high-fives {b}.", "{a} and {b} share the loudest high five."],
    "poke": ["{a} pokes {b}.", "{a} pokes {b} repeatedly."],
}

NUMBER_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}
RPS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
DICE = re.compile(r"^(\d{1,2})?d(\d{1,4})([+-]\d{1,4})?$", re.I)


def stable(*parts):
    digest = hashlib.sha256("|".join(p.lower() for p in parts).encode()).digest()
    return int.from_bytes(digest[:4], "big")


class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label="​", row=y)
        self.x, self.y = x, y

    async def callback(self, interaction):
        await self.view.play(interaction, self)


class TicTacToe(discord.ui.View):
    def __init__(self, first, second):
        super().__init__(timeout=180)
        self.players = (first, second)
        self.turn = 0
        self.board = [[None] * 3 for _ in range(3)]
        self.message = None
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def status(self):
        mark = "❌" if self.turn == 0 else "⭕"
        return f"{mark} {self.players[self.turn].mention}'s turn"

    def winner(self):
        b = self.board
        lines = [*b, *zip(*b), [b[i][i] for i in range(3)], [b[i][2 - i] for i in range(3)]]
        for line in lines:
            if line[0] is not None and line[0] == line[1] == line[2]:
                return line[0]
        return None

    async def play(self, interaction, button):
        if interaction.user.id != self.players[self.turn].id:
            await interaction.response.send_message("It isn't your turn.", ephemeral=True)
            return
        self.board[button.y][button.x] = self.turn
        button.label = "X" if self.turn == 0 else "O"
        button.style = discord.ButtonStyle.danger if self.turn == 0 else discord.ButtonStyle.primary
        button.disabled = True
        won = self.winner()
        full = all(cell is not None for row in self.board for cell in row)
        if won is not None or full:
            for child in self.children:
                child.disabled = True
            text = f"🏆 {self.players[won].mention} wins!" if won is not None else "It's a draw."
            self.stop()
        else:
            self.turn = 1 - self.turn
            text = self.status()
        await interaction.response.edit_message(content=text, view=self, allowed_mentions=discord.AllowedMentions(users=True))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Game timed out.", view=self)
            except discord.HTTPException:
                pass


class TriviaView(discord.ui.View):
    def __init__(self, author, answers, correct):
        super().__init__(timeout=25)
        self.author, self.correct = author, correct
        self.message = None
        for index, answer in enumerate(answers):
            button = discord.ui.Button(label=answer[:80], style=discord.ButtonStyle.secondary, row=index // 2)
            button.callback = self.make_callback(button, answer)
            self.add_item(button)

    def make_callback(self, button, answer):
        async def callback(interaction):
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("Run your own with `!trivia`.", ephemeral=True)
                return
            right = answer == self.correct
            for child in self.children:
                child.disabled = True
                if child.label == self.correct[:80]:
                    child.style = discord.ButtonStyle.success
            if not right:
                button.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Correct!" if right else f"Nope. The answer was **{self.correct}**.")
            self.stop()
        return callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @commands.command(name="8ball")
    async def eight_ball(self, ctx, *, question: str):
        """Asks the magic 8-ball a question. Usage: !8ball will it rain"""
        await ctx.reply(f"🎱 {random.choice(EIGHT_BALL)}", mention_author=False)

    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip(self, ctx):
        """Flips a coin. Usage: !coinflip"""
        await ctx.reply(f"🪙 {random.choice(['Heads', 'Tails'])}", mention_author=False)

    @commands.command(name="roll", aliases=["dice"])
    async def roll(self, ctx, spec: str = "1d6"):
        """Rolls dice like 2d6+3, or a single number like 100. Usage: !roll 2d6+3"""
        spec = spec.replace(" ", "")
        if spec.isdigit():
            spec = f"1d{spec}"
        match = DICE.match(spec)
        if not match:
            await ctx.reply("Use something like `2d6`, `d20+4` or `100`.", mention_author=False)
            return
        count = int(match.group(1) or 1)
        sides = int(match.group(2))
        bonus = int(match.group(3) or 0)
        if not 1 <= count <= 20 or sides < 2:
            await ctx.reply("Roll 1 to 20 dice with at least 2 sides.", mention_author=False)
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + bonus
        shown = ", ".join(map(str, rolls))
        suffix = f" {bonus:+d}" if bonus else ""
        await ctx.reply(f"🎲 **{total}** ({shown}{suffix})", mention_author=False)

    @commands.command(name="choose", aliases=["pick"])
    async def choose(self, ctx, *, options: str):
        """Picks one option from a list split by | or commas. Usage: !choose pizza | tacos | sushi"""
        parts = [p.strip() for p in re.split(r"\||,", options) if p.strip()]
        if len(parts) < 2:
            await ctx.reply("Give me at least two options, split by `|` or commas.", mention_author=False)
            return
        await ctx.reply(f"I pick **{random.choice(parts)}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="rps")
    async def rps(self, ctx, choice: str):
        """Plays rock paper scissors against the bot. Usage: !rps rock"""
        choice = choice.lower()
        if choice not in RPS:
            await ctx.reply("Pick `rock`, `paper` or `scissors`.", mention_author=False)
            return
        bot_choice = random.choice(list(RPS))
        if choice == bot_choice:
            result = "It's a tie."
        elif BEATS[choice] == bot_choice:
            result = "You win!"
        else:
            result = "I win!"
        await ctx.reply(f"{RPS[choice]} vs {RPS[bot_choice]}: {result}", mention_author=False)

    @commands.command(name="rate")
    async def rate(self, ctx, *, thing: str):
        """Rates anything out of 10. Usage: !rate pineapple pizza"""
        score = stable("rate", thing) % 11
        await ctx.reply(f"I rate **{thing[:100]}** a **{score}/10**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="ship")
    async def ship(self, ctx, first: discord.Member, second: discord.Member = None):
        """Checks how well two people match. Usage: !ship @user @user"""
        second = second or ctx.author
        pair = sorted([str(first.id), str(second.id)])
        percent = stable("ship", *pair) % 101
        filled = percent // 10
        bar = "█" * filled + "░" * (10 - filled)
        await ctx.reply(f"💞 {first.display_name} + {second.display_name}\n`{bar}` **{percent}%**", mention_author=False, allowed_mentions=NO_MENTIONS)

    async def action(self, ctx, kind, member):
        if member.id == ctx.author.id:
            await ctx.reply("Pick someone else.", mention_author=False)
            return
        text = random.choice(ACTIONS[kind]).format(a=ctx.author.display_name, b=member.display_name)
        await ctx.send(text, allowed_mentions=NO_MENTIONS)

    @commands.command(name="hug")
    async def hug(self, ctx, member: discord.Member):
        """Hugs someone. Usage: !hug @user"""
        await self.action(ctx, "hug", member)

    @commands.command(name="pat")
    async def pat(self, ctx, member: discord.Member):
        """Pats someone. Usage: !pat @user"""
        await self.action(ctx, "pat", member)

    @commands.command(name="slap")
    async def slap(self, ctx, member: discord.Member):
        """Slaps someone with a wet noodle. Usage: !slap @user"""
        await self.action(ctx, "slap", member)

    @commands.command(name="bonk")
    async def bonk(self, ctx, member: discord.Member):
        """Bonks someone. Usage: !bonk @user"""
        await self.action(ctx, "bonk", member)

    @commands.command(name="highfive")
    async def highfive(self, ctx, member: discord.Member):
        """High-fives someone. Usage: !highfive @user"""
        await self.action(ctx, "highfive", member)

    @commands.command(name="poke")
    async def poke(self, ctx, member: discord.Member):
        """Pokes someone. Usage: !poke @user"""
        await self.action(ctx, "poke", member)

    @commands.command(name="joke")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def joke(self, ctx):
        """Tells a joke. Usage: !joke"""
        await ctx.reply(random.choice(JOKES), mention_author=False)

    @commands.command(name="dadjoke")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def dadjoke(self, ctx):
        """Fetches a random dad joke. Usage: !dadjoke"""
        try:
            data = await self.fetch_json("https://icanhazdadjoke.com/", headers={"Accept": "application/json", "User-Agent": "RiskBot"})
            text = data.get("joke")
        except Exception:
            text = None
        await ctx.reply(text or random.choice(JOKES), mention_author=False)

    @commands.command(name="fact")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def fact(self, ctx):
        """Shares a random fact. Usage: !fact"""
        await ctx.reply(f"💡 {random.choice(FACTS)}", mention_author=False)

    @commands.command(name="wyr")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def wyr(self, ctx):
        """Asks a would-you-rather question. Usage: !wyr"""
        message = await ctx.send(random.choice(WYR))
        for emoji in ("🅰️", "🅱️"):
            await message.add_reaction(emoji)

    @commands.command(name="reverse")
    async def reverse(self, ctx, *, text: str):
        """Reverses your text. Usage: !reverse hello"""
        await ctx.reply(text[::-1][:1900], mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="mock")
    async def mock(self, ctx, *, text: str):
        """Turns text into mOcKiNg cAsE. Usage: !mock you can't be serious"""
        out, upper = [], False
        for ch in text[:1900]:
            if ch.isalpha():
                out.append(ch.upper() if upper else ch.lower())
                upper = not upper
            else:
                out.append(ch)
        await ctx.reply("".join(out), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="clap")
    async def clap(self, ctx, *, text: str):
        """Puts claps 👏 between 👏 words. Usage: !clap nice work"""
        await ctx.reply(" 👏 ".join(text.split())[:1900], mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="emojify")
    async def emojify(self, ctx, *, text: str):
        """Turns text into big emoji letters. Usage: !emojify hello"""
        out = []
        for ch in text.lower()[:200]:
            if "a" <= ch <= "z":
                out.append(f":regional_indicator_{ch}:")
            elif ch in NUMBER_WORDS:
                out.append(f":{NUMBER_WORDS[ch]}:")
            elif ch == " ":
                out.append("   ")
            else:
                out.append(ch)
        await ctx.reply(" ".join(out)[:1900], mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="uwu")
    async def uwu(self, ctx, *, text: str):
        """Turns text into uwu speak. Usage: !uwu hello there"""
        out = re.sub(r"[rl]", "w", text[:1900])
        out = re.sub(r"[RL]", "W", out)
        await ctx.reply(out, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="compliment")
    async def compliment(self, ctx, member: discord.Member = None):
        """Gives someone a nice compliment. Usage: !compliment @user"""
        member = member or ctx.author
        lines = [
            "{n} makes every chat better.", "{n} has excellent taste.", "{n} is the kind of person people are glad to see.",
            "{n} is quietly very good at things.", "{n} would win a kindness contest.",
        ]
        await ctx.send(random.choice(lines).format(n=member.display_name), allowed_mentions=NO_MENTIONS)

    @commands.command(name="number", aliases=["rng"])
    async def number(self, ctx, low: int = 1, high: int = 100):
        """Picks a random number in a range. Usage: !number 1 100"""
        if low > high:
            low, high = high, low
        await ctx.reply(f"🔢 {random.randint(low, high)}", mention_author=False)

    @commands.command(name="say", aliases=["echo"])
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, text: str):
        """Makes the bot say something without pinging anyone. Usage: !say hello everyone"""
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(text[:1900], allowed_mentions=NO_MENTIONS)

    @commands.command(name="tictactoe", aliases=["ttt"])
    @commands.guild_only()
    async def tictactoe(self, ctx, opponent: discord.Member):
        """Starts a game of tic-tac-toe with someone. Usage: !tictactoe @user"""
        if opponent.bot or opponent.id == ctx.author.id:
            await ctx.reply("Pick another human to play against.", mention_author=False)
            return
        view = TicTacToe(ctx.author, opponent)
        view.message = await ctx.send(view.status(), view=view, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(name="trivia")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def trivia(self, ctx):
        """Asks a multiple-choice trivia question. Usage: !trivia"""
        try:
            data = await self.fetch_json("https://opentdb.com/api.php?amount=1&type=multiple")
            item = data["results"][0]
        except Exception:
            await ctx.reply("The trivia service isn't answering right now. Try again soon.", mention_author=False)
            return
        question = html.unescape(item["question"])
        correct = html.unescape(item["correct_answer"])
        answers = [html.unescape(a) for a in item["incorrect_answers"]] + [correct]
        random.shuffle(answers)
        embed = discord.Embed(title="Trivia", description=question, color=discord.Color.blurple())
        embed.set_footer(text=f"{html.unescape(item['category'])} · {item['difficulty']} · 25 seconds")
        view = TriviaView(ctx.author, answers, correct)
        view.message = await ctx.send(embed=embed, view=view)

    async def picture(self, ctx, url, key, title):
        try:
            data = await self.fetch_json(url)
            image = data[0][key] if isinstance(data, list) else data[key]
        except Exception:
            await ctx.reply("The picture service isn't answering right now.", mention_author=False)
            return
        embed = discord.Embed(title=title, color=discord.Color.light_grey())
        embed.set_image(url=image)
        await ctx.send(embed=embed)

    @commands.command(name="cat")
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def cat(self, ctx):
        """Shows a random cat picture. Usage: !cat"""
        await self.picture(ctx, "https://api.thecatapi.com/v1/images/search", "url", "Cat")

    @commands.command(name="dog")
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def dog(self, ctx):
        """Shows a random dog picture. Usage: !dog"""
        await self.picture(ctx, "https://dog.ceo/api/breeds/image/random", "message", "Dog")

    @commands.command(name="fox")
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def fox(self, ctx):
        """Shows a random fox picture. Usage: !fox"""
        await self.picture(ctx, "https://randomfox.ca/floof/", "image", "Fox")


async def setup(bot):
    await bot.add_cog(Fun(bot))
