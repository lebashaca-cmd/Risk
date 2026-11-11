"""More community commands: kudos, member intros, a quote book, daily check-in streaks, team splitting and a
question of the day."""
import random
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

QUESTIONS = [
    "What's a small thing that made you smile this week?", "If you could instantly learn any skill, what would it be?", "What's the best game you played this year?",
    "What song have you had on repeat lately?", "Would you rather have unlimited snacks or unlimited sleep?", "What's a hobby you'd like to try?",
    "What's your comfort show or movie?", "If you could live anywhere for a year, where would it be?", "What's the best advice you've ever been given?",
    "What's something you're proud of that you rarely mention?", "Morning person or night owl?", "What's a food you could eat every day?",
    "What's the last thing that made you laugh out loud?", "If you could have dinner with anyone, who would it be?", "What's a game you think more people should play?",
    "What's your most used emoji?", "What would your superhero name be?", "Which fictional world would you want to visit?",
    "What's a tiny habit that improved your day?", "If you could master one instrument overnight, which one?", "What's the best thing you've eaten recently?",
    "What's your favorite season and why?", "What's a skill you're surprisingly good at?", "What's on your wishlist right now?",
    "What did you want to be when you were a kid?", "What's one thing you want to get better at this month?", "Cats, dogs, or something more unusual?",
    "What's a place you'd love to visit someday?", "What's your go-to karaoke song?", "What's the most useful thing you own?",
]
MAX_QUOTES = 200
KUDOS_PER_DAY = 5


def day_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class CommunityPlus(commands.Cog, name="CommunityPlus"):
    """Kudos, intros, quote book, streaks, teams and daily questions."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("community_plus")

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def guild(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {})
        for key in ("kudos", "given", "intros", "quotes", "streaks"):
            data.setdefault(key, {} if key != "quotes" else [])
        return data

    # ------------------------------------------------------------------ kudos
    @commands.group(name="kudos", invoke_without_command=True)
    async def kudos(self, ctx, member: discord.Member = None, *, reason: str = ""):
        """Give someone kudos (5 a day), or see theirs. Usage: !kudos @user great help today, or !kudos to see yours"""
        data = self.guild(ctx.guild.id)
        if member is None:
            await ctx.reply(f"You have **{data['kudos'].get(str(ctx.author.id), 0)}** kudos. Give some with `{ctx.prefix}kudos @user`.", mention_author=False)
            return
        if member.bot:
            raise ModError("Bots don't need kudos.")
        if member.id == ctx.author.id:
            raise ModError("You can't give yourself kudos. Ask a friend.")
        today = day_now()
        given = data["given"].get(str(ctx.author.id), {"day": today, "n": 0})
        if given["day"] != today:
            given = {"day": today, "n": 0}
        if given["n"] >= KUDOS_PER_DAY:
            raise ModError(f"You've given {KUDOS_PER_DAY} kudos today. Come back tomorrow.")
        given["n"] += 1
        data["given"][str(ctx.author.id)] = given
        data["kudos"][str(member.id)] = data["kudos"].get(str(member.id), 0) + 1
        self.store.save()
        note = f" for: {reason[:150]}" if reason.strip() else ""
        await ctx.reply(f"{member.mention} got kudos from {ctx.author.display_name}{note}. They now have **{data['kudos'][str(member.id)]}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @kudos.command(name="top", aliases=["leaderboard", "lb"])
    async def kudos_top(self, ctx):
        """Shows who has the most kudos. Usage: !kudos top"""
        ranked = sorted(self.guild(ctx.guild.id)["kudos"].items(), key=lambda kv: kv[1], reverse=True)[:10]
        if not ranked:
            await ctx.reply("Nobody has kudos yet. Be the first to give some.", mention_author=False)
            return
        lines = []
        for index, (uid, count) in enumerate(ranked, start=1):
            member = ctx.guild.get_member(int(uid))
            lines.append(f"**{index}.** {discord.utils.escape_markdown(member.display_name) if member else 'User ' + uid}: {count}")
        await ctx.reply(embed=discord.Embed(title="Most kudos", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False)

    # ------------------------------------------------------------------ intros
    @commands.group(name="intro", invoke_without_command=True)
    async def intro(self, ctx, member: discord.Member = None):
        """Shows someone's intro. Usage: !intro @user, !intro set <text>, !intro clear"""
        member = member or ctx.author
        text = self.guild(ctx.guild.id)["intros"].get(str(member.id))
        if not text:
            hint = f" Write yours with `{ctx.prefix}intro set <text>`." if member == ctx.author else ""
            await ctx.reply(f"{member.display_name} hasn't written an intro yet.{hint}", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        embed = discord.Embed(title=f"About {member.display_name}", description=text, color=discord.Color.light_grey())
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @intro.command(name="set")
    async def intro_set(self, ctx, *, text: str):
        """Writes your intro (up to 400 characters). Usage: !intro set I love games and music"""
        if len(text) > 400:
            raise ModError("Keep your intro to 400 characters.")
        self.guild(ctx.guild.id)["intros"][str(ctx.author.id)] = discord.utils.escape_mentions(text.strip())
        self.store.save()
        await ctx.reply("Intro saved. People can see it with `intro @you`.", mention_author=False)

    @intro.command(name="clear", aliases=["remove"])
    async def intro_clear(self, ctx):
        """Removes your intro. Usage: !intro clear"""
        self.guild(ctx.guild.id)["intros"].pop(str(ctx.author.id), None)
        self.store.save()
        await ctx.reply("Your intro is gone.", mention_author=False)

    # ------------------------------------------------------------------ quote book
    @commands.group(name="quotebook", aliases=["qb"], invoke_without_command=True)
    async def quotebook(self, ctx):
        """Shows a random saved server quote. Usage: !quotebook, !quotebook add <text>, !quotebook list"""
        quotes = self.guild(ctx.guild.id)["quotes"]
        if not quotes:
            await ctx.reply(f"The quote book is empty. Add one with `{ctx.prefix}quotebook add <text>`.", mention_author=False)
            return
        number = random.randrange(len(quotes))
        entry = quotes[number]
        await ctx.reply(f"**#{number + 1}** “{entry['text']}”\n added by {entry['by']}", mention_author=False, allowed_mentions=NO_MENTIONS)

    @quotebook.command(name="add")
    async def quotebook_add(self, ctx, *, text: str):
        """Saves a quote. Usage: !quotebook add \"never skip leg day\" - Sam"""
        quotes = self.guild(ctx.guild.id)["quotes"]
        if len(text) > 300:
            raise ModError("Keep quotes to 300 characters.")
        if len(quotes) >= MAX_QUOTES:
            raise ModError(f"The quote book is full ({MAX_QUOTES}). Ask staff to remove old ones.")
        quotes.append({"text": discord.utils.escape_mentions(text.strip()), "by": ctx.author.display_name[:32]})
        self.store.save()
        await ctx.reply(f"Saved as quote **#{len(quotes)}**.", mention_author=False)

    @quotebook.command(name="list")
    async def quotebook_list(self, ctx, page: int = 1):
        """Lists saved quotes, 8 per page. Usage: !quotebook list 2"""
        quotes = self.guild(ctx.guild.id)["quotes"]
        pages = max(1, -(-len(quotes) // 8))
        page = max(1, min(page, pages))
        chunk = quotes[(page - 1) * 8: page * 8]
        if not chunk:
            await ctx.reply("No quotes saved yet.", mention_author=False)
            return
        lines = [f"**#{(page - 1) * 8 + i}** {q['text'][:110]}" for i, q in enumerate(chunk, start=1)]
        embed = discord.Embed(title="Quote book", description="\n".join(lines), color=discord.Color.light_grey())
        embed.set_footer(text=f"Page {page} of {pages}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @quotebook.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_messages=True)
    async def quotebook_remove(self, ctx, number: int):
        """Removes a quote by number (Manage Messages). Usage: !quotebook remove 3"""
        quotes = self.guild(ctx.guild.id)["quotes"]
        if not 1 <= number <= len(quotes):
            raise ModError("There's no quote with that number.")
        quotes.pop(number - 1)
        self.store.save()
        await ctx.reply(f"Removed quote **#{number}**. Later numbers moved up by one.", mention_author=False)

    # ------------------------------------------------------------------ streaks
    @commands.command(name="checkin", aliases=["daily-checkin", "streak"])
    async def checkin(self, ctx):
        """Check in once a day to build a streak. Usage: !checkin"""
        data = self.guild(ctx.guild.id)
        today = datetime.now(timezone.utc).date()
        entry = data["streaks"].get(str(ctx.author.id), {"last": "", "streak": 0, "best": 0, "total": 0})
        if entry["last"] == today.isoformat():
            await ctx.reply(f"You already checked in today. Streak: **{entry['streak']}** day(s). Come back tomorrow.", mention_author=False)
            return
        yesterday = (today - timedelta(days=1)).isoformat()
        entry["streak"] = entry["streak"] + 1 if entry["last"] == yesterday else 1
        entry["best"] = max(entry["best"], entry["streak"])
        entry["total"] += 1
        entry["last"] = today.isoformat()
        data["streaks"][str(ctx.author.id)] = entry
        self.store.save()
        await ctx.reply(f"Checked in. Streak: **{entry['streak']}** day(s), best **{entry['best']}**, **{entry['total']}** check-ins in all.", mention_author=False)

    @commands.command(name="streaks", aliases=["streakboard"])
    async def streaks(self, ctx):
        """Shows the longest current check-in streaks. Usage: !streaks"""
        today = datetime.now(timezone.utc).date()
        live = []
        for uid, e in self.guild(ctx.guild.id)["streaks"].items():
            if e["last"] in (today.isoformat(), (today - timedelta(days=1)).isoformat()):
                live.append((uid, e["streak"]))
        live.sort(key=lambda kv: kv[1], reverse=True)
        if not live:
            await ctx.reply(f"No active streaks. Start one with `{ctx.prefix}checkin`.", mention_author=False)
            return
        lines = []
        for index, (uid, n) in enumerate(live[:10], start=1):
            member = ctx.guild.get_member(int(uid))
            lines.append(f"**{index}.** {discord.utils.escape_markdown(member.display_name) if member else 'User ' + uid}: {n} day(s)")
        await ctx.reply(embed=discord.Embed(title="Check-in streaks", description="\n".join(lines), color=discord.Color.light_grey()), mention_author=False)

    # ------------------------------------------------------------------ teams and questions
    @commands.command(name="teams", aliases=["splitteams"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def teams(self, ctx, count: int, members: commands.Greedy[discord.Member]):
        """Splits people into random teams. Mention them, or join a voice channel and leave it out. Usage: !teams 2 @a @b @c @d"""
        if not 2 <= count <= 10:
            raise ModError("Pick between 2 and 10 teams.")
        people = list(dict.fromkeys(members))
        if not people and ctx.author.voice and ctx.author.voice.channel:
            people = [m for m in ctx.author.voice.channel.members if not m.bot]
        people = [m for m in people if not m.bot]
        if len(people) < count:
            raise ModError("I need at least as many people as teams. Mention them or join a voice channel.")
        random.shuffle(people)
        embed = discord.Embed(title=f"{count} teams", color=discord.Color.light_grey())
        for index in range(count):
            embed.add_field(name=f"Team {index + 1}", value="\n".join(m.display_name for m in people[index::count])[:1000], inline=True)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="qotd", aliases=["question", "conversation"])
    @commands.cooldown(1, 20, commands.BucketType.channel)
    async def qotd(self, ctx):
        """Posts a conversation starter for the channel. Usage: !qotd"""
        embed = discord.Embed(title="Question of the day", description=random.choice(QUESTIONS), color=discord.Color.light_grey())
        embed.set_footer(text="Reply in the channel to join in")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommunityPlus(bot))
