import asyncio
import random
import re

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error

LINES = {
    "kiss": "{a} kisses {b}.",
    "cuddle": "{a} cuddles {b}.",
    "bite": "{a} bites {b}.",
    "kick": "{a} kicks {b}.",
    "punch": "{a} punches {b}.",
    "tickle": "{a} tickles {b}.",
    "wave": "{a} waves hello.",
    "dance": "{a} breaks into a dance.",
    "cry": "{a} bursts into tears.",
    "blush": "{a} blushes.",
}
TRUTHS = [
    "What's the most embarrassing thing you've done in a voice chat?", "What's a song you're secretly obsessed with?",
    "What's the last lie you told?", "Who in this server would you trust with your phone?",
    "What's a habit you'd never admit to in public?", "What's the weirdest thing you've googled this week?",
    "What's your most unpopular opinion?", "What was your most awkward text mix-up?",
]
DARES = [
    "Change your nickname to whatever the next person picks for 10 minutes.", "Send the last emoji you used five times in a row.",
    "Type your next three messages with your eyes closed.", "Post the 5th photo in your camera roll (keep it safe for work).",
    "Say something nice about every person who has spoken in the last hour.", "Speak only in questions for the next five minutes.",
]
TOPICS = [
    "What's the best meal you've ever had?", "If you could live anywhere for a year, where?", "What's a skill you wish you had?",
    "What's the last show you couldn't stop watching?", "Which game deserves a remake?", "What's your go-to comfort food?",
    "What would you do with a free day and no plans?", "What's the best advice you've ever received?",
]
FORTUNES = [
    "A small risk will pay off soon.", "Someone is about to message you with good news.", "Today is a good day to start the thing you've been putting off.",
    "You'll find what you lost where you least expect it.", "Patience will do more than speed this week.", "A friend needs a message from you.",
    "Expect a pleasant surprise before the weekend.", "Your next idea is a good one. Write it down.",
]
ADVICE = [
    "Drink some water.", "Back up your files today.", "Take a short walk and come back to the problem.",
    "Write down the next step, then do only that.", "Sleep on big decisions.", "Ask the question. Someone else is wondering too.",
]
RIDDLES = [
    ("What has keys but can't open locks?", "piano"), ("What gets wetter the more it dries?", "towel"),
    ("What has hands but can't clap?", "clock"), ("What can you catch but not throw?", "cold"),
    ("What has a neck but no head?", "bottle"), ("What has one eye but can't see?", "needle"), ("The more you take, the more you leave behind. What am I?", "footsteps"),
    ("What runs but never walks?", "river"), ("What can travel the world while staying in a corner?", "stamp"),
]
WORDS = [
    "discord", "keyboard", "server", "pixel", "dragon", "rocket", "puzzle", "thunder", "island", "coffee", "garden", "planet",
    "wizard", "castle", "jungle", "mirror", "shadow", "violin", "button", "cookie", "ocean", "canyon", "lantern", "marble",
]
HITS = ["lands a heavy punch", "swings a chair", "throws a surprise kick", "uses a flying elbow", "slips in a quick jab", "drops a frying pan"]


class FunExtra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def gif(self, kind):
        timeout = aiohttp.ClientTimeout(total=10)
        urls = [(f"https://nekos.best/api/v2/{kind}", "nekos"), (f"https://api.waifu.pics/sfw/{kind}", "waifu")]
        for url, source in urls:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue
                        data = await response.json(content_type=None)
                if source == "nekos":
                    item = data["results"][0]
                    return item["url"], item.get("anime_name")
                return data["url"], None
            except Exception:
                continue
        return None, None

    async def act(self, ctx, kind, member=None):
        if member is not None and member.id == ctx.author.id:
            await ctx.reply("Pick someone else.", mention_author=False)
            return
        text = LINES[kind].format(a=ctx.author.display_name, b=member.display_name if member else "")
        url, credit = await self.gif(kind)
        if not url:
            await ctx.send(text, allowed_mentions=NO_MENTIONS)
            return
        embed = discord.Embed(description=f"**{text}**", color=discord.Color.light_grey())
        embed.set_image(url=url)
        if credit:
            embed.set_footer(text=credit)
        await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)

    @commands.command(name="kiss")
    async def kiss(self, ctx, member: discord.Member):
        """Kisses someone. Usage: !kiss @user"""
        await self.act(ctx, "kiss", member)

    @commands.command(name="cuddle")
    async def cuddle(self, ctx, member: discord.Member):
        """Cuddles someone. Usage: !cuddle @user"""
        await self.act(ctx, "cuddle", member)

    @commands.command(name="bite")
    async def bite(self, ctx, member: discord.Member):
        """Bites someone. Usage: !bite @user"""
        await self.act(ctx, "bite", member)

    @commands.command(name="boot", aliases=["kickgif"])
    async def boot(self, ctx, member: discord.Member):
        """Kicks someone with a GIF. Usage: !boot @user"""
        await self.act(ctx, "kick", member)

    @commands.command(name="punch")
    async def punch(self, ctx, member: discord.Member):
        """Punches someone. Usage: !punch @user"""
        await self.act(ctx, "punch", member)

    @commands.command(name="tickle")
    async def tickle(self, ctx, member: discord.Member):
        """Tickles someone. Usage: !tickle @user"""
        await self.act(ctx, "tickle", member)

    @commands.command(name="wave")
    async def wave(self, ctx):
        """Waves hello. Usage: !wave"""
        await self.act(ctx, "wave")

    @commands.command(name="dance")
    async def dance(self, ctx):
        """Dances. Usage: !dance"""
        await self.act(ctx, "dance")

    @commands.command(name="cry")
    async def cry(self, ctx):
        """Cries. Usage: !cry"""
        await self.act(ctx, "cry")

    @commands.command(name="blush")
    async def blush(self, ctx):
        """Blushes. Usage: !blush"""
        await self.act(ctx, "blush")

    @commands.command(name="fight")
    async def fight(self, ctx, member: discord.Member):
        """Starts a silly fight with someone. Usage: !fight @user"""
        if member.bot or member.id == ctx.author.id:
            await ctx.reply("Pick another member to fight.", mention_author=False)
            return
        names = [ctx.author.display_name, member.display_name]
        hp = [100, 100]
        turn = random.randint(0, 1)
        log = []
        while min(hp) > 0:
            damage = random.randint(8, 25)
            hp[1 - turn] = max(0, hp[1 - turn] - damage)
            log.append(f"**{names[turn]}** {random.choice(HITS)} for {damage}.")
            turn = 1 - turn
        winner = 0 if hp[0] > 0 else 1
        embed = discord.Embed(title=f"{names[0]} vs {names[1]}", description="\n".join(log[-6:]), color=discord.Color.red())
        embed.add_field(name="Winner", value=f"🏆 {names[winner]} with {hp[winner]} HP left")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="truth")
    async def truth(self, ctx):
        """Gives a truth question. Usage: !truth"""
        await ctx.reply(embed=discord.Embed(title="Truth", description=random.choice(TRUTHS), color=discord.Color.blue()), mention_author=False)

    @commands.command(name="dare")
    async def dare(self, ctx):
        """Gives a dare. Usage: !dare"""
        await ctx.reply(embed=discord.Embed(title="Dare", description=random.choice(DARES), color=discord.Color.orange()), mention_author=False)

    @commands.command(name="topic")
    async def topic(self, ctx):
        """Starts a conversation with a random topic. Usage: !topic"""
        await ctx.reply(embed=discord.Embed(title="Chat topic", description=random.choice(TOPICS), color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="fortune")
    async def fortune(self, ctx):
        """Reads your fortune. Usage: !fortune"""
        await ctx.reply(embed=discord.Embed(title="🔮 Your fortune", description=random.choice(FORTUNES), color=discord.Color.purple()), mention_author=False)

    @commands.command(name="advice")
    async def advice(self, ctx):
        """Gives a piece of advice. Usage: !advice"""
        text = random.choice(ADVICE)
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://api.adviceslip.com/advice") as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        text = data["slip"]["advice"]
        except Exception:
            pass
        await ctx.reply(embed=discord.Embed(title="Advice", description=text[:500], color=discord.Color.light_grey()), mention_author=False)

    @commands.command(name="guess")
    async def guess(self, ctx):
        """Guess a number from 1 to 100 in six tries. Usage: !guess"""
        number = random.randint(1, 100)
        await ctx.reply("I'm thinking of a number from 1 to 100. You have 6 tries. Type your guesses in this channel.", mention_author=False)

        def check(message):
            return message.author.id == ctx.author.id and message.channel.id == ctx.channel.id and message.content.strip().isdigit()

        for attempt in range(1, 7):
            try:
                message = await self.bot.wait_for("message", check=check, timeout=45)
            except asyncio.TimeoutError:
                await ctx.send(f"Time's up. The number was **{number}**.")
                return
            value = int(message.content.strip())
            if value == number:
                await ctx.send(f"🎉 Correct! It was **{number}**, found in {attempt} {'try' if attempt == 1 else 'tries'}.")
                return
            left = 6 - attempt
            hint = "higher" if value < number else "lower"
            await ctx.send(f"Go {hint}. {left} {'try' if left == 1 else 'tries'} left." if left else f"Out of tries. The number was **{number}**.")

    async def wait_for_answer(self, ctx, answer, prompt):
        await ctx.send(prompt)

        def check(message):
            return message.channel.id == ctx.channel.id and not message.author.bot and answer in re.findall(r"[a-z]+", message.content.lower())

        try:
            message = await self.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send(f"Nobody got it. The answer was **{answer}**.")
            return
        await message.reply(f"✅ {message.author.display_name} got it: **{answer}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="riddle")
    async def riddle(self, ctx):
        """Asks a riddle. First correct answer in 30 seconds wins. Usage: !riddle"""
        question, answer = random.choice(RIDDLES)
        await self.wait_for_answer(ctx, answer, f"🧩 {question}")

    @commands.command(name="scramble")
    async def scramble(self, ctx):
        """Unscramble a word. First correct answer in 30 seconds wins. Usage: !scramble"""
        word = random.choice(WORDS)
        letters = list(word)
        while "".join(letters) == word:
            random.shuffle(letters)
        await self.wait_for_answer(ctx, word, f"🧩 Unscramble this word: **{''.join(letters)}**")


async def setup(bot):
    await bot.add_cog(FunExtra(bot))
