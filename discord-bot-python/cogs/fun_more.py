"""Even more fun commands: reaction gifs-in-words, text styles, name makers, tarot and a few small games
(Wordle, minesweeper, quick draw, flag and capital quizzes, rock paper scissors lizard spock)."""
import asyncio
import random

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error

WORDS = (
    "about above actor adapt adult after again agent agree ahead alarm album alert alike alive allow alone along alter amaze angel anger angle angry apple apply arena argue arise armor aside "
    "asset avoid awake award aware badge baker basic beach beard beast begin being below bench berry birth black blade blame blank blast blaze bleed blend bless blind block blood bloom board boast "
    "bonus boost booth brain brake brand brave bread break brick bride brief bring broad brown brush build bunch burst cabin cable candy carry catch cause chain chair charm chase cheap check cheek "
    "cheer chest chief child chill choir chose civil claim class clean clear clerk click cliff climb clock close cloud coach coast color couch count court cover craft crane crash crazy cream crisp "
    "crowd crown curve cycle daily dance dealt death debut delay depth dirty doubt dozen draft drain drama dream dress drift drink drive eager early earth eight elite empty enemy enjoy enter equal "
    "error event every exact exist extra faith false fancy fault feast fence fever field fifth fifty fight final first flame flash fleet floor flour fluid focus force forge forth found frame fresh "
    "front fruit funny ghost giant given glass globe glory grace grade grain grand grant grape grass great green greet grind group grown guard guess guest guide habit happy harsh heart heavy hello "
    "honey honor horse hotel house human humor ideal image index inner input issue jelly joint judge juice knife known label large laser later laugh layer learn least leave legal lemon level light "
    "limit local logic loose lover lower lucky lunch magic major maker march match maybe mayor media mercy metal meter might minor minus model money month moral motor mount mouse mouth movie music "
    "nasty naval nerve never newly night noble noise north novel nurse ocean offer often olive onion opera orbit order other ought outer owner paint panel paper party pasta patch pause peace pearl "
    "phase phone photo piano piece pilot pitch pizza place plain plane plant plate point polar pound power press price pride prime print prize proof proud pulse punch queen quest quick quiet quite "
    "radio raise range rapid ratio reach ready realm rebel refer relax reply rider ridge right rival river robot rocky rough round route royal rural salad sauce scale scene scope score sense serve "
    "seven shade shake shape share sharp sheep sheet shelf shell shift shine shirt shock shoot short shown sight silly since sixth skill sleep slice slide small smart smile smoke snake solid solve "
    "sorry sound south space spare speak speed spend spice spike split spoke sport spray squad stack staff stage stair stamp stand start state steam steel stick still stock stone store storm story "
    "strip study style sugar suite sunny super sweet swift swing sword table taste teach thank theme there thick thing think third those three throw thumb tiger tight title toast today tooth topic "
    "total touch tough tower trace track trade trail train treat trend trial tribe trick troop truck truly trust truth twice uncle under union unity until upper upset urban usage usual valid value "
    "video virus visit vital vocal voice waste watch water weigh wheel where which while white whole whose woman world worry worth would wound write wrong young youth zebra"
).split()
LIZARD = {"rock": ["scissors", "lizard"], "paper": ["rock", "spock"], "scissors": ["paper", "lizard"], "lizard": ["spock", "paper"], "spock": ["scissors", "rock"]}
LIZARD_ICON = {"rock": "🪨", "paper": "📄", "scissors": "✂️", "lizard": "🦎", "spock": "🖖"}
COUNTRIES = {
    "US": ("United States", ["usa", "america", "united states of america"], "Washington"), "CA": ("Canada", [], "Ottawa"), "MX": ("Mexico", [], "Mexico City"),
    "BR": ("Brazil", [], "Brasilia"), "AR": ("Argentina", [], "Buenos Aires"), "GB": ("United Kingdom", ["uk", "britain", "england"], "London"), "FR": ("France", [], "Paris"),
    "DE": ("Germany", [], "Berlin"), "ES": ("Spain", [], "Madrid"), "IT": ("Italy", [], "Rome"), "PT": ("Portugal", [], "Lisbon"), "NL": ("Netherlands", ["holland"], "Amsterdam"),
    "SE": ("Sweden", [], "Stockholm"), "NO": ("Norway", [], "Oslo"), "FI": ("Finland", [], "Helsinki"), "PL": ("Poland", [], "Warsaw"), "GR": ("Greece", [], "Athens"),
    "TR": ("Turkey", [], "Ankara"), "RU": ("Russia", [], "Moscow"), "UA": ("Ukraine", [], "Kyiv"), "EG": ("Egypt", [], "Cairo"), "NG": ("Nigeria", [], "Abuja"),
    "KE": ("Kenya", [], "Nairobi"), "ZA": ("South Africa", [], "Pretoria"), "IN": ("India", [], "New Delhi"), "CN": ("China", [], "Beijing"), "JP": ("Japan", [], "Tokyo"),
    "KR": ("South Korea", ["korea"], "Seoul"), "TH": ("Thailand", [], "Bangkok"), "VN": ("Vietnam", [], "Hanoi"), "ID": ("Indonesia", [], "Jakarta"), "PH": ("Philippines", [], "Manila"),
    "AU": ("Australia", [], "Canberra"), "NZ": ("New Zealand", [], "Wellington"), "SA": ("Saudi Arabia", [], "Riyadh"), "IE": ("Ireland", [], "Dublin"), "CH": ("Switzerland", [], "Bern"),
    "AT": ("Austria", [], "Vienna"), "CL": ("Chile", [], "Santiago"), "CO": ("Colombia", [], "Bogota"), "PE": ("Peru", [], "Lima"), "CU": ("Cuba", [], "Havana"),
}
TAROT = [
    ("The Fool", "a fresh start and a leap of faith", "recklessness or hesitation"), ("The Magician", "skill and making things happen", "tricks or wasted talent"),
    ("The High Priestess", "intuition and quiet knowing", "ignored instincts"), ("The Empress", "growth, comfort and care", "smothering or neglect"),
    ("The Emperor", "structure and steady leadership", "rigidity or control"), ("The Lovers", "a meaningful choice or bond", "a mismatch or hard choice"),
    ("The Chariot", "drive and winning through focus", "losing direction"), ("Strength", "calm courage", "self-doubt"), ("The Hermit", "reflection and finding your own answers", "isolation"),
    ("Wheel of Fortune", "luck turning your way", "a bumpy patch that will pass"), ("Justice", "fairness and honest outcomes", "unfair treatment or avoiding blame"),
    ("The Hanged Man", "seeing things from a new angle", "stalling for no reason"), ("Temperance", "balance and patience", "excess or impatience"), ("The Tower", "sudden change that clears the way", "resisting a needed change"),
    ("The Star", "hope and renewal", "lost hope"), ("The Moon", "mystery and following your gut", "confusion clearing up"), ("The Sun", "joy and success", "joy delayed"),
    ("Judgement", "a wake-up call and a fresh chance", "ignoring the call"), ("The World", "finishing something big", "one last loose end"),
]
ANIMALS = ["wolf", "fox", "owl", "bear", "otter", "dolphin", "raven", "tiger", "deer", "eagle", "turtle", "panther", "hummingbird", "octopus", "lynx", "falcon", "hedgehog", "koala", "whale", "red panda"]
PIRATE_A = ["Captain", "Salty", "One-Eyed", "Barnacle", "Black", "Mad", "Rusty", "Dread", "Iron", "Scurvy", "Golden", "Stormy"]
PIRATE_B = ["Pete", "Anne", "Jack", "Bones", "Beard", "Morgan", "Hook", "Mary", "Tom", "Coral", "Silver", "Rose"]
PIRATE_C = ["the Bold", "of the Deep", "Sharktooth", "the Unlucky", "Seabreeze", "the Terrible", "Cutlass", "the Lost", "Rumrunner", "the Kind"]
BAND_A = ["Electric", "Velvet", "Midnight", "Neon", "Paper", "Crimson", "Silent", "Atomic", "Lunar", "Broken", "Cosmic", "Wild", "Glass", "Hollow", "Rusty"]
BAND_B = ["Pirates", "Llamas", "Giants", "Echoes", "Tigers", "Ghosts", "Robots", "Wolves", "Dreams", "Engines", "Parade", "Garden", "Rebels", "Satellites", "Pancakes"]
SYL_A = ["Ael", "Bar", "Cal", "Dor", "El", "Fen", "Gal", "Hal", "Is", "Kor", "Lur", "Mar", "Nor", "Or", "Pyr", "Quin", "Ran", "Syl", "Thal", "Vor", "Wyn", "Zan"]
SYL_B = ["a", "e", "i", "o", "an", "en", "or", "ith", "ara", "iel", "und"]
SYL_C = ["dor", "las", "mir", "thas", "wen", "ric", "nar", "vyn", "gorn", "dis", "rel", "wyn", "bar"]
SCRIPT_UP, SCRIPT_LOW = 0x1D4D0, 0x1D4EA
SMALL_CAPS = dict(zip("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"))
TINY = dict(zip("abcdefghijklmnopqrstuvwxyz", "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ"))
ZALGO = [chr(c) for c in list(range(0x300, 0x315)) + list(range(0x316, 0x31A)) + list(range(0x33D, 0x345))]
NUMBERS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


class FunMore(commands.Cog, name="FunMore"):
    """Reactions, text styles, name makers and small games."""

    def __init__(self, bot):
        self.bot = bot
        self.playing = set()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def act(self, ctx, member, verb, emoji, alone):
        if member is None or member.id == ctx.author.id:
            await ctx.reply(f"{emoji} {alone}", mention_author=False, allowed_mentions=NO_MENTIONS)
        else:
            await ctx.reply(f"{emoji} **{ctx.author.display_name}** {verb} **{member.display_name}**", mention_author=False, allowed_mentions=NO_MENTIONS)

    # ---------------------------------------------------------------- reactions
    @commands.command(name="boop")
    async def boop(self, ctx, member: discord.Member = None):
        """Boops someone on the nose. Usage: !boop @user"""
        await self.act(ctx, member, "boops", "👉", "You boop the air. It doesn't mind.")

    @commands.command(name="yeet")
    async def yeet(self, ctx, member: discord.Member = None):
        """Yeets someone into the distance. Usage: !yeet @user"""
        await self.act(ctx, member, "yeets", "🚀", "You yeet yourself. Nobody saw that.")

    @commands.command(name="nom")
    async def nom(self, ctx, member: discord.Member = None):
        """Nibbles on someone (gently). Usage: !nom @user"""
        await self.act(ctx, member, "nibbles on", "😋", "You nom on a snack.")

    @commands.command(name="stare")
    async def stare(self, ctx, member: discord.Member = None):
        """Stares at someone. Usage: !stare @user"""
        await self.act(ctx, member, "stares at", "👀", "You stare into the void.")

    @commands.command(name="facepalm")
    async def facepalm(self, ctx, member: discord.Member = None):
        """Facepalms at someone. Usage: !facepalm @user"""
        await self.act(ctx, member, "facepalms at", "🤦", "You facepalm so hard.")

    @commands.command(name="salute")
    async def salute(self, ctx, member: discord.Member = None):
        """Salutes someone. Usage: !salute @user"""
        await self.act(ctx, member, "salutes", "🫡", "You salute the room.")

    @commands.command(name="cheer")
    async def cheer(self, ctx, member: discord.Member = None):
        """Cheers someone on. Usage: !cheer @user"""
        await self.act(ctx, member, "cheers on", "📣", "You cheer for yourself. Go you.")

    @commands.command(name="fistbump")
    async def fistbump(self, ctx, member: discord.Member = None):
        """Fist bumps someone. Usage: !fistbump @user"""
        await self.act(ctx, member, "fist bumps", "🤜", "You fist bump the air.")

    @commands.command(name="wink")
    async def wink(self, ctx, member: discord.Member = None):
        """Winks at someone. Usage: !wink @user"""
        await self.act(ctx, member, "winks at", "😉", "You wink at nobody in particular.")

    @commands.command(name="laugh")
    async def laugh(self, ctx, member: discord.Member = None):
        """Laughs (with someone, not at them). Usage: !laugh @user"""
        await self.act(ctx, member, "laughs with", "😂", "You burst out laughing.")

    @commands.command(name="snuggle")
    async def snuggle(self, ctx, member: discord.Member = None):
        """Snuggles up to someone. Usage: !snuggle @user"""
        await self.act(ctx, member, "snuggles up to", "🧸", "You snuggle a pillow.")

    @commands.command(name="cookie")
    async def cookie(self, ctx, member: discord.Member = None):
        """Gives someone a cookie. Usage: !cookie @user"""
        await self.act(ctx, member, "gives a cookie to", "🍪", "You eat a cookie. Crunchy.")

    @commands.command(name="pizza")
    async def pizza(self, ctx, member: discord.Member = None):
        """Shares a slice of pizza. Usage: !pizza @user"""
        await self.act(ctx, member, "shares a slice of pizza with", "🍕", "You eat a whole pizza.")

    @commands.command(name="coffee")
    async def coffee(self, ctx, member: discord.Member = None):
        """Hands someone a coffee. Usage: !coffee @user"""
        await self.act(ctx, member, "hands a coffee to", "☕", "You make yourself a coffee.")

    # ---------------------------------------------------------------- text styles
    @staticmethod
    def need(text):
        if not text or not text.strip():
            raise ModError("Give me some text.")
        return text.strip()[:300]

    @commands.command(name="fancy", aliases=["cursive"])
    async def fancy(self, ctx, *, text: str = None):
        """Writes text in fancy script letters. Usage: !fancy hello there"""
        out = "".join(chr(SCRIPT_UP + ord(c) - 65) if "A" <= c <= "Z" else chr(SCRIPT_LOW + ord(c) - 97) if "a" <= c <= "z" else c for c in self.need(text))
        await ctx.reply(out, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="smallcaps")
    async def smallcaps(self, ctx, *, text: str = None):
        """Writes text in small capitals. Usage: !smallcaps hello there"""
        await ctx.reply("".join(SMALL_CAPS.get(c, c) for c in self.need(text).lower()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="tiny", aliases=["superscript"])
    async def tiny(self, ctx, *, text: str = None):
        """Writes text in tiny raised letters. Usage: !tiny hello there"""
        await ctx.reply("".join(TINY.get(c, c) for c in self.need(text).lower()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="zalgo", aliases=["glitch"])
    async def zalgo(self, ctx, *, text: str = None):
        """Makes text look cursed and glitchy. Usage: !zalgo hello"""
        source = self.need(text)[:120]
        out = "".join(c + "".join(random.choice(ZALGO) for _ in range(random.randint(2, 5))) if c.strip() else c for c in source)
        await ctx.reply(out, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="whisper")
    async def whisper(self, ctx, *, text: str = None):
        """Says something quietly. Usage: !whisper i have a secret"""
        await ctx.reply(f"🤫 *{self.need(text).lower()}*", mention_author=False, allowed_mentions=NO_MENTIONS)

    # ---------------------------------------------------------------- name makers and fortunes
    @commands.command(name="tarot")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def tarot(self, ctx):
        """Draws three tarot cards for past, present and future (just for fun). Usage: !tarot"""
        cards = random.sample(TAROT, 3)
        lines = []
        for label, (name, up, rev) in zip(("Past", "Present", "Future"), cards):
            reversed_card = random.random() < 0.3
            lines.append(f"**{label}: {name}{' (reversed)' if reversed_card else ''}**: {rev if reversed_card else up}")
        embed = discord.Embed(title="🔮 Your tarot draw", description="\n".join(lines), color=discord.Color.purple())
        embed.set_footer(text="For fun only. You write your own future.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="spiritanimal", aliases=["spirit"])
    async def spiritanimal(self, ctx, member: discord.Member = None):
        """Finds someone's spirit animal (it never changes). Usage: !spiritanimal @user"""
        member = member or ctx.author
        animal = ANIMALS[(member.id * 2654435761 >> 7) % len(ANIMALS)]
        await ctx.reply(f"🐾 **{member.display_name}**'s spirit animal is the **{animal}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="pirate", aliases=["piratename"])
    async def pirate(self, ctx):
        """Gives you a pirate name. Usage: !pirate"""
        name = f"{random.choice(PIRATE_A)} {random.choice(PIRATE_B)} {random.choice(PIRATE_C)}"
        await ctx.reply(f"🏴‍☠️ Ye shall be known as **{name}**.", mention_author=False)

    @commands.command(name="bandname", aliases=["band"])
    async def bandname(self, ctx):
        """Makes up a band name. Usage: !bandname"""
        await ctx.reply(f"🎸 Your band is called **{random.choice(BAND_A)} {random.choice(BAND_B)}**.", mention_author=False)

    @commands.command(name="fantasyname", aliases=["elfname"])
    async def fantasyname(self, ctx):
        """Makes up a fantasy character name. Usage: !fantasyname"""
        name = random.choice(SYL_A) + random.choice(SYL_B) + random.choice(SYL_C)
        await ctx.reply(f"🧝 Your character is **{name.capitalize()}**.", mention_author=False)

    # ---------------------------------------------------------------- games
    @commands.command(name="rpsls")
    async def rpsls(self, ctx, choice: str):
        """Rock paper scissors lizard spock against the bot. Usage: !rpsls spock"""
        choice = choice.lower()
        if choice not in LIZARD:
            raise ModError("Pick one of: " + ", ".join(LIZARD) + ".")
        bot_choice = random.choice(list(LIZARD))
        if choice == bot_choice:
            result = "It's a tie."
        elif bot_choice in LIZARD[choice]:
            result = "You win!"
        else:
            result = "I win!"
        await ctx.reply(f"You: {LIZARD_ICON[choice]} {choice}  vs  Me: {LIZARD_ICON[bot_choice]} {bot_choice}\n**{result}**", mention_author=False)

    @commands.command(name="minesweeper", aliases=["mines"])
    async def minesweeper(self, ctx, size: int = 8, mines: int = 0):
        """Plays minesweeper with spoiler tiles: click a tile to reveal it. Usage: !minesweeper 8 10"""
        size = max(4, min(size, 9))
        mines = mines or max(3, size * size // 6)
        mines = max(1, min(mines, size * size // 2))
        grid = [[0] * size for _ in range(size)]
        for spot in random.sample(range(size * size), mines):
            grid[spot // size][spot % size] = -1
        for r in range(size):
            for c in range(size):
                if grid[r][c] != -1:
                    grid[r][c] = sum(1 for dr in (-1, 0, 1) for dc in (-1, 0, 1) if 0 <= r + dr < size and 0 <= c + dc < size and grid[r + dr][c + dc] == -1)
        rows = ["".join(f"||{'💣' if cell == -1 else NUMBERS[cell]}||" for cell in row) for row in grid]
        await ctx.reply(f"💣 **Minesweeper** {size}x{size}, {mines} mines. Click tiles to reveal them, avoid the bombs.\n" + "\n".join(rows), mention_author=False)

    @commands.command(name="wordle")
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def wordle(self, ctx):
        """Plays Wordle: guess the 5-letter word in 6 tries by sending guesses in chat. Usage: !wordle (type stop to quit)"""
        if ctx.author.id in self.playing:
            raise ModError("You're already playing a game.")
        self.playing.add(ctx.author.id)
        secret = random.choice(WORDS)
        rows = []
        try:
            await ctx.reply("🟩 **Wordle!** I picked a 5-letter word. Type your guess in this channel. 6 tries, 60 seconds each. 🟩 right spot, 🟨 wrong spot, ⬛ not in the word. Type `stop` to quit.", mention_author=False)
            for attempt in range(1, 7):
                def check(m):
                    return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and (m.content.strip().lower() == "stop" or (len(m.content.strip()) == 5 and m.content.strip().isalpha()))
                try:
                    message = await self.bot.wait_for("message", check=check, timeout=60)
                except asyncio.TimeoutError:
                    await ctx.send(f"⏰ Time's up. The word was **{secret}**.")
                    return
                guess = message.content.strip().lower()
                if guess == "stop":
                    await ctx.send(f"Stopped. The word was **{secret}**.")
                    return
                marks = ["⬛"] * 5
                left = list(secret)
                for i, ch in enumerate(guess):
                    if ch == secret[i]:
                        marks[i] = "🟩"
                        left.remove(ch)
                for i, ch in enumerate(guess):
                    if marks[i] != "🟩" and ch in left:
                        marks[i] = "🟨"
                        left.remove(ch)
                rows.append("".join(marks) + f"  `{guess.upper()}`")
                if guess == secret:
                    await ctx.send("\n".join(rows) + f"\n🎉 You got it in **{attempt}**!")
                    return
                await ctx.send("\n".join(rows) + f"\n{6 - attempt} tries left.")
            await ctx.send(f"Out of tries. The word was **{secret}**.")
        finally:
            self.playing.discard(ctx.author.id)

    @commands.command(name="quickdraw")
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def quickdraw(self, ctx, opponent: discord.Member):
        """Western duel: when I say DRAW, type bang first. Typing it early loses. Usage: !quickdraw @user"""
        if opponent.bot or opponent.id == ctx.author.id:
            raise ModError("Pick another member to duel.")
        players = {ctx.author.id: ctx.author, opponent.id: opponent}

        def check(m):
            return m.author.id in players and m.channel.id == ctx.channel.id and m.content.strip().lower() == "bang"
        await ctx.reply(f"🤠 {ctx.author.mention} vs {opponent.mention}. Wait for the signal, then type `bang`. Too early and you lose.", mention_author=False, allowed_mentions=discord.AllowedMentions(users=True))
        try:
            early = await self.bot.wait_for("message", check=check, timeout=random.uniform(3, 8))
            loser = early.author
            winner = next(p for pid, p in players.items() if pid != loser.id)
            await ctx.send(f"💨 {loser.display_name} fired too early. **{winner.display_name}** wins!", allowed_mentions=NO_MENTIONS)
            return
        except asyncio.TimeoutError:
            pass
        await ctx.send("🔫 **DRAW!** Type `bang`!")
        try:
            message = await self.bot.wait_for("message", check=check, timeout=8)
        except asyncio.TimeoutError:
            await ctx.send("Nobody fired. Both gunslingers went home.")
            return
        await ctx.send(f"🏆 **{message.author.display_name}** was fastest!", allowed_mentions=NO_MENTIONS)

    async def quiz(self, ctx, question, answers, reveal):
        await ctx.reply(question + " (20 seconds, anyone can answer)", mention_author=False)
        accepted = {a.lower() for a in answers}

        def check(m):
            return m.channel.id == ctx.channel.id and not m.author.bot and m.content.strip().lower() in accepted
        try:
            message = await self.bot.wait_for("message", check=check, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up. It was **{reveal}**.")
            return
        await message.add_reaction("✅")
        await ctx.send(f"🎉 **{message.author.display_name}** got it: **{reveal}**.", allowed_mentions=NO_MENTIONS)

    @commands.command(name="flagquiz")
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def flagquiz(self, ctx):
        """Shows a flag; the first person to name the country wins. Usage: !flagquiz"""
        code = random.choice(list(COUNTRIES))
        name, extra, _ = COUNTRIES[code]
        await self.quiz(ctx, f"{flag(code)} Which country's flag is this?", [name, *extra], name)

    @commands.command(name="capitalquiz")
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def capitalquiz(self, ctx):
        """Names a country; the first person to give its capital wins. Usage: !capitalquiz"""
        code = random.choice(list(COUNTRIES))
        name, _, capital = COUNTRIES[code]
        answers = [capital] + (["washington dc", "washington d.c.", "washington, d.c."] if code == "US" else []) + (["kiev"] if code == "UA" else [])
        await self.quiz(ctx, f"{flag(code)} What is the capital of **{name}**?", answers, capital)


async def setup(bot):
    await bot.add_cog(FunMore(bot))
