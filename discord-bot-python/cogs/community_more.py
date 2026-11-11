"""More community commands: events with RSVPs, looking-for-group posts, game lists, pronouns, a member
spotlight, anniversaries, pair-ups, bingo cards, brackets, icebreakers and a server pulse."""
import random
import re
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

ICEBREAKERS = [
    "What's the first thing you do when you wake up?", "What's a movie you can quote almost entirely?", "What's your most unpopular food opinion?",
    "If you had a theme song when you walk into a room, what would it be?", "What's the best purchase you made under $20?", "What game do you replay every year?",
    "What's something you learned recently that surprised you?", "What's your dream road trip?", "Which app do you spend the most time on?",
    "If you could have any pet, no limits, what would it be?", "What's a smell that brings back memories?", "What's the best compliment you've ever received?",
    "What's your favourite thing to cook or order?", "What's a small town or place you love that few people know?", "If you could un-invent one thing, what would it be?",
    "What were you obsessed with as a kid?", "What's the best gift you've given someone?", "Which fictional character would be your roommate?",
    "What's a talent you wish you had?", "What's the weirdest job you've ever heard of?",
]
DEBATES = [
    "Is a hot dog a sandwich?", "Pineapple on pizza: yes or no?", "Is cereal a soup?", "Should the toilet paper hang over or under?", "Is water wet?", "Cats vs dogs: who wins?",
    "Is it okay to put milk in first when making tea?", "Are video games a sport?", "Is a straw one hole or two?", "Is breakfast the best meal of the day?",
    "Would you rather have summer all year or winter all year?", "Are sequels ever better than the original?", "Is it rude to leave someone on read?", "Should you text or call?",
    "Is mint chocolate chip a good ice cream flavour?",
]
HOT_TAKES = [
    "Dark mode is better in every app.", "Breakfast food is best at night.", "Most movies are too long now.", "Group chats are worse than email.", "Everyone should learn to cook one great dish.",
    "Mornings are overrated.", "Voice messages are better than typing.", "Free time is more valuable than money.", "Remakes should be banned for ten years.", "Pickles belong on everything.",
    "Short games are better than long ones.", "Pens are better than pencils.", "Summer is the worst season.", "Music was better ten years ago.", "Phones should have buttons again.",
]
BINGO = [
    "Someone says brb", "A meme gets posted", "Off topic chat", "Someone is late", "Game recommendation", "Food photo", "Bot command spam", "An inside joke", "Voice chat starts", "Someone leaves",
    "New member joins", "Pet picture", "Tech problem", "Reply to old msg", "Someone says gg", "A poll is made", "Caps lock yelling", "Someone is AFK", "Song link shared", "Emoji overload",
    "Someone says lol", "A debate starts", "Typo war", "Someone says hi", "Weekend plans", "Coffee talk", "Server lag", "Someone learns something",
]
LFG_TTL = 2 * 60 * 60
MAX_EVENTS = 25


def parse_when(tokens):
    """Reads `in 2h30m ...` or `2026-12-01 18:00 ...` (UTC) from the start of the tokens. Returns (timestamp, rest)."""
    if tokens and tokens[0].lower() == "in":
        total, used = 0, 1
        for token in tokens[1:]:
            parts = re.findall(r"(\d+)([dhm])", token.lower())
            if not parts or "".join(f"{n}{u}" for n, u in parts) != token.lower():
                break
            for n, unit in parts:
                total += int(n) * {"d": 86400, "h": 3600, "m": 60}[unit]
            used += 1
        if total <= 0:
            raise ModError("Say how long, like `in 2h30m` or `in 3d`.")
        return int(time.time()) + total, tokens[used:]
    if len(tokens) >= 2:
        try:
            when = datetime.strptime(f"{tokens[0]} {tokens[1]}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            when = None
        if when:
            return int(when.timestamp()), tokens[2:]
    raise ModError("Say when: `in 2h30m` or `2026-12-01 18:00` (UTC time).")


class LFGView(discord.ui.View):
    def __init__(self, host, game, size, note):
        super().__init__(timeout=LFG_TTL)
        self.host, self.game, self.size, self.note = host, game, size, note
        self.players = [host.id]

    def embed(self, closed=False):
        embed = discord.Embed(title=f"🎮 Looking for group: {self.game}", color=discord.Color.light_grey() if closed else discord.Color.green())
        if self.note:
            embed.description = self.note
        embed.add_field(name=f"Players ({len(self.players)}/{self.size})", value="\n".join(f"<@{p}>" for p in self.players), inline=False)
        embed.set_footer(text="Group closed" if closed else f"Hosted by {self.host.display_name}. Press the button to join or leave.")
        return embed

    @discord.ui.button(label="Join / leave", style=discord.ButtonStyle.success)
    async def toggle(self, interaction, button):
        uid = interaction.user.id
        if uid == self.host.id:
            await interaction.response.send_message("You're the host. Use `Close` when you're done.", ephemeral=True)
            return
        if uid in self.players:
            self.players.remove(uid)
        elif len(self.players) >= self.size:
            await interaction.response.send_message("That group is full.", ephemeral=True)
            return
        else:
            self.players.append(uid)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction, button):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("Only the host can close this.", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=self.embed(closed=True), view=self)
        self.stop()


class CommunityMore(commands.Cog, name="CommunityMore"):
    """Events, looking-for-group, game lists, pronouns, spotlight and more."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("community_more")

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def guild(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {})
        data.setdefault("events", [])
        data.setdefault("next_id", 1)
        data.setdefault("games", {})
        data.setdefault("pronouns", {})
        return data

    async def say(self, ctx, text):
        await ctx.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ---------------------------------------------------------------- conversation starters
    @commands.command(name="icebreaker")
    async def icebreaker(self, ctx):
        """Posts a random icebreaker question. Usage: !icebreaker"""
        await ctx.reply(embed=discord.Embed(title="🧊 Icebreaker", description=random.choice(ICEBREAKERS), color=discord.Color.teal()), mention_author=False)

    @commands.command(name="debate")
    async def debate(self, ctx):
        """Posts a fun debate topic. Usage: !debate"""
        message = await ctx.reply(embed=discord.Embed(title="🗣️ Debate time", description=random.choice(DEBATES) + "\n\nReact 👍 or 👎 and tell us why.", color=discord.Color.orange()), mention_author=False)
        for emoji in ("👍", "👎"):
            await message.add_reaction(emoji)

    @commands.command(name="hottake")
    async def hottake(self, ctx):
        """Posts a harmless hot take to argue about. Usage: !hottake"""
        message = await ctx.reply(embed=discord.Embed(title="🌶️ Hot take", description=random.choice(HOT_TAKES) + "\n\nAgree or disagree?", color=discord.Color.red()), mention_author=False)
        for emoji in ("✅", "❌"):
            await message.add_reaction(emoji)

    @commands.command(name="shoutout")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def shoutout(self, ctx, member: discord.Member, *, message: str = "You're awesome!"):
        """Gives someone a public shoutout. Usage: !shoutout @user thanks for the help today"""
        if member.bot:
            raise ModError("Bots can't read shoutouts. Pick a person.")
        embed = discord.Embed(title="📣 Shoutout", description=f"{member.mention}\n{message[:400]}", color=discord.Color.gold())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"From {ctx.author.display_name}")
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=[member]))

    @commands.command(name="spotlight")
    async def spotlight(self, ctx):
        """Shows today's member spotlight (the same person all day). Usage: !spotlight"""
        pool = sorted((m for m in ctx.guild.members if not m.bot), key=lambda m: m.id)
        if not pool:
            raise ModError("I can't see any members to pick from.")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pick = random.Random(f"{ctx.guild.id}{today}").choice(pool)
        embed = discord.Embed(title="🌟 Member spotlight", description=f"Today's spotlight is {pick.mention}! Say hi and tell them something nice.", color=discord.Color.gold())
        embed.set_thumbnail(url=pick.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ---------------------------------------------------------------- events
    @commands.group(name="event", aliases=["events"], invoke_without_command=True)
    async def event(self, ctx):
        """Lists upcoming events. Usage: !event, !event add in 2h Movie night, !event join 3"""
        data = self.guild(ctx.guild.id)
        now = time.time()
        data["events"] = [e for e in data["events"] if e["ts"] > now - 3600]
        self.store.save()
        if not data["events"]:
            await self.say(ctx, f"No events planned. Make one with `{ctx.prefix}event add in 2h Movie night`.")
            return
        lines = [f"**#{e['id']}** {e['title']}: <t:{e['ts']}:F> (<t:{e['ts']}:R>), {len(e['going'])} going" for e in sorted(data["events"], key=lambda e: e["ts"])[:15]]
        await ctx.reply(embed=discord.Embed(title="📅 Upcoming events", description="\n".join(lines), color=discord.Color.blurple()), mention_author=False)

    @event.command(name="add", aliases=["create"])
    async def event_add(self, ctx, *, details: str):
        """Creates an event. Usage: !event add in 2h30m Movie night, or !event add 2026-12-01 18:00 Game night (UTC)"""
        data = self.guild(ctx.guild.id)
        if len(data["events"]) >= MAX_EVENTS:
            raise ModError(f"There are already {MAX_EVENTS} events. Cancel one first.")
        ts, rest = parse_when(details.split())
        title = " ".join(rest).strip()[:100]
        if not title:
            raise ModError("Give the event a title after the time.")
        if ts < time.time():
            raise ModError("That time is in the past.")
        entry = {"id": data["next_id"], "title": title, "ts": ts, "host": ctx.author.id, "going": [ctx.author.id]}
        data["next_id"] += 1
        data["events"].append(entry)
        self.store.save()
        await self.say(ctx, f"📅 Event **#{entry['id']} {title}** is set for <t:{ts}:F> (<t:{ts}:R>). Join with `{ctx.prefix}event join {entry['id']}`.")

    def find(self, ctx, number):
        for e in self.guild(ctx.guild.id)["events"]:
            if e["id"] == number:
                return e
        raise ModError(f"I can't find event #{number}. See `{ctx.prefix}event`.")

    @event.command(name="join", aliases=["rsvp"])
    async def event_join(self, ctx, number: int):
        """RSVPs to an event. Usage: !event join 3"""
        e = self.find(ctx, number)
        if ctx.author.id in e["going"]:
            raise ModError("You're already on the list.")
        e["going"].append(ctx.author.id)
        self.store.save()
        await self.say(ctx, f"✅ You're going to **{e['title']}**. {len(e['going'])} going.")

    @event.command(name="leave")
    async def event_leave(self, ctx, number: int):
        """Removes your RSVP. Usage: !event leave 3"""
        e = self.find(ctx, number)
        if ctx.author.id not in e["going"]:
            raise ModError("You weren't on the list.")
        e["going"].remove(ctx.author.id)
        self.store.save()
        await self.say(ctx, f"Removed you from **{e['title']}**.")

    @event.command(name="info", aliases=["who"])
    async def event_info(self, ctx, number: int):
        """Shows an event and who is going. Usage: !event info 3"""
        e = self.find(ctx, number)
        going = ", ".join(f"<@{u}>" for u in e["going"][:40]) or "Nobody yet"
        embed = discord.Embed(title=f"#{e['id']} {e['title']}", description=f"<t:{e['ts']}:F> (<t:{e['ts']}:R>)\nHost: <@{e['host']}>", color=discord.Color.blurple())
        embed.add_field(name=f"Going ({len(e['going'])})", value=going[:1000], inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @event.command(name="cancel", aliases=["remove"])
    async def event_cancel(self, ctx, number: int):
        """Cancels an event (the host or someone who can manage messages). Usage: !event cancel 3"""
        e = self.find(ctx, number)
        if ctx.author.id != e["host"] and not ctx.author.guild_permissions.manage_messages:
            raise ModError("Only the host or a moderator can cancel this event.")
        self.guild(ctx.guild.id)["events"].remove(e)
        self.store.save()
        await self.say(ctx, f"🗑️ Cancelled **{e['title']}**.")

    # ---------------------------------------------------------------- looking for group and game lists
    @commands.command(name="lfg")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def lfg(self, ctx, size: int, game: str, *, note: str = ""):
        """Posts a looking-for-group message with a join button. Usage: !lfg 4 Minecraft survival night, or !lfg 5 "Rocket League" ranked"""
        if not 2 <= size <= 25:
            raise ModError("Group size is 2 to 25 (including you).")
        view = LFGView(ctx.author, game[:60], size, note[:300])
        await ctx.send(embed=view.embed(), view=view)

    @commands.group(name="mygames", aliases=["games"], invoke_without_command=True)
    async def mygames(self, ctx, member: discord.Member = None):
        """Shows the games someone plays. Usage: !mygames @user, !mygames add Valorant, !mygames remove Valorant"""
        member = member or ctx.author
        games = self.guild(ctx.guild.id)["games"].get(str(member.id), [])
        await self.say(ctx, f"🎮 **{member.display_name}** plays: " + (", ".join(games) if games else f"nothing listed. Add some with `{ctx.prefix}mygames add <game>`."))

    @mygames.command(name="add")
    async def mygames_add(self, ctx, *, game: str):
        """Adds a game to your list (up to 15). Usage: !mygames add Valorant"""
        games = self.guild(ctx.guild.id)["games"].setdefault(str(ctx.author.id), [])
        game = game.strip()[:40]
        if not game:
            raise ModError("Which game?")
        if any(g.lower() == game.lower() for g in games):
            raise ModError("That game is already on your list.")
        if len(games) >= 15:
            raise ModError("You can list up to 15 games.")
        games.append(game)
        self.store.save()
        await self.say(ctx, f"Added **{game}**. You list {len(games)} game(s).")

    @mygames.command(name="remove", aliases=["delete"])
    async def mygames_remove(self, ctx, *, game: str):
        """Removes a game from your list. Usage: !mygames remove Valorant"""
        games = self.guild(ctx.guild.id)["games"].setdefault(str(ctx.author.id), [])
        match = next((g for g in games if g.lower() == game.strip().lower()), None)
        if not match:
            raise ModError("That game isn't on your list.")
        games.remove(match)
        self.store.save()
        await self.say(ctx, f"Removed **{match}**.")

    @commands.command(name="whoplays")
    async def whoplays(self, ctx, *, game: str):
        """Finds members who listed a game. Usage: !whoplays Minecraft"""
        wanted = game.strip().lower()
        found = [uid for uid, games in self.guild(ctx.guild.id)["games"].items() if any(wanted in g.lower() for g in games) and ctx.guild.get_member(int(uid))]
        if not found:
            await self.say(ctx, f"Nobody has listed **{game[:40]}** yet. Add it with `{ctx.prefix}mygames add {game[:40]}`.")
            return
        names = ", ".join(ctx.guild.get_member(int(u)).display_name for u in found[:30])
        await self.say(ctx, f"🎮 **{len(found)}** member(s) play **{game[:40]}**: {names}")

    @commands.group(name="pronouns", invoke_without_command=True)
    async def pronouns(self, ctx, member: discord.Member = None):
        """Shows someone's pronouns. Usage: !pronouns @user, !pronouns set she/her, !pronouns clear"""
        member = member or ctx.author
        value = self.guild(ctx.guild.id)["pronouns"].get(str(member.id))
        await self.say(ctx, f"**{member.display_name}**: {value}" if value else f"**{member.display_name}** hasn't set pronouns" + (f". Use `{ctx.prefix}pronouns set they/them`." if member == ctx.author else "."))

    @pronouns.command(name="set")
    async def pronouns_set(self, ctx, *, text: str):
        """Sets your pronouns. Usage: !pronouns set she/her"""
        if len(text) > 30:
            raise ModError("Keep it under 30 characters.")
        self.guild(ctx.guild.id)["pronouns"][str(ctx.author.id)] = discord.utils.escape_markdown(text.strip())
        self.store.save()
        await self.say(ctx, f"Saved: **{text.strip()}**")

    @pronouns.command(name="clear")
    async def pronouns_clear(self, ctx):
        """Removes your pronouns. Usage: !pronouns clear"""
        self.guild(ctx.guild.id)["pronouns"].pop(str(ctx.author.id), None)
        self.store.save()
        await self.say(ctx, "Cleared.")

    # ---------------------------------------------------------------- members and groups
    @commands.command(name="anniversaries")
    async def anniversaries(self, ctx):
        """Lists members whose join anniversary is this month. Usage: !anniversaries"""
        now = datetime.now(timezone.utc)
        found = sorted(((m.joined_at.day, now.year - m.joined_at.year, m) for m in ctx.guild.members if m.joined_at and m.joined_at.month == now.month and m.joined_at.year < now.year and not m.bot), key=lambda x: x[0])
        if not found:
            await self.say(ctx, "Nobody has a join anniversary this month.")
            return
        lines = [f"**{m.display_name}**: {years} year{'s' if years != 1 else ''} on {now:%B} {day}" for day, years, m in found[:20]]
        await ctx.reply(embed=discord.Embed(title=f"🎂 {now:%B} anniversaries", description="\n".join(lines), color=discord.Color.gold()), mention_author=False)

    @commands.command(name="pairup")
    async def pairup(self, ctx, role: discord.Role = None):
        """Pairs up random members from a role (or your voice channel). Usage: !pairup @role"""
        if role:
            pool = [m for m in role.members if not m.bot]
        elif ctx.author.voice and ctx.author.voice.channel:
            pool = [m for m in ctx.author.voice.channel.members if not m.bot]
        else:
            raise ModError("Give a role, or join a voice channel first.")
        if len(pool) < 2:
            raise ModError("I need at least 2 people to pair up.")
        pool = random.sample(pool, min(len(pool), 40))
        pairs = [pool[i:i + 2] for i in range(0, len(pool), 2)]
        if len(pairs[-1]) == 1:
            pairs[-2].extend(pairs.pop())
        await self.say(ctx, "🤝 **Pairs**\n" + "\n".join(" & ".join(m.display_name for m in p) for p in pairs))

    @commands.command(name="bingo")
    async def bingo(self, ctx):
        """Makes a chat bingo card to play along with. Usage: !bingo"""
        picks = random.sample(BINGO, 24)
        picks.insert(12, "FREE")
        rows = ["|".join(f"{c[:14]:^14}" for c in picks[i:i + 5]) for i in range(0, 25, 5)]
        line = "\n" + "-" * 74 + "\n"
        await self.say(ctx, f"🎯 **{ctx.author.display_name}'s bingo card**\n```\n{line.join(rows)}\n```Mark them off as they happen in chat.")

    @commands.command(name="bracket")
    async def bracket(self, ctx, *, names: str):
        """Makes a random tournament bracket. Usage: !bracket Ann, Bob, Cy, Dee"""
        entries = [n.strip()[:30] for n in re.split(r",|\n", names) if n.strip()]
        if not 2 <= len(entries) <= 32:
            raise ModError("Give 2 to 32 names separated by commas.")
        random.shuffle(entries)
        matches = [f"**{entries[i]}** vs **{entries[i + 1]}**" for i in range(0, len(entries) - 1, 2)]
        if len(entries) % 2:
            matches.append(f"**{entries[-1]}** gets a bye")
        await self.say(ctx, f"🏆 **Round 1** ({len(entries)} entries)\n" + "\n".join(f"{i}. {m}" for i, m in enumerate(matches, start=1)))

    @commands.command(name="draftorder")
    async def draftorder(self, ctx, *, names: str):
        """Shuffles names into a random order. Usage: !draftorder Ann, Bob, Cy"""
        entries = [n.strip()[:30] for n in re.split(r",|\n", names) if n.strip()]
        if not 2 <= len(entries) <= 40:
            raise ModError("Give 2 to 40 names separated by commas.")
        random.shuffle(entries)
        await self.say(ctx, "📋 **Order**\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(entries, start=1)))

    @commands.command(name="pulse")
    async def pulse(self, ctx):
        """Shows how active the server has been (messages over 1, 7 and 30 days and the busiest channels). Usage: !pulse"""
        levels = self.bot.get_cog("Levels")
        activity = levels.activity.data.get(str(ctx.guild.id), {}) if levels else {}
        days = activity.get("msgs", {})
        if not days:
            await self.say(ctx, "I haven't counted any messages yet. Activity is tracked from when the level system is on.")
            return
        now = datetime.now(timezone.utc)
        totals = {span: 0 for span in (1, 7, 30)}
        channels = {}
        for key, per in days.items():
            try:
                age = (now.date() - datetime.strptime(key, "%Y-%m-%d").date()).days
            except ValueError:
                continue
            for span in totals:
                if age < span:
                    totals[span] += sum(per.values())
            if age < 7:
                for cid, n in per.items():
                    channels[cid] = channels.get(cid, 0) + n
        top = sorted(channels.items(), key=lambda kv: kv[1], reverse=True)[:5]
        embed = discord.Embed(title=f"💓 {ctx.guild.name} pulse", color=discord.Color(0xFFB0EC))
        embed.add_field(name="Messages", value=f"Today: **{totals[1]:,}**\n7 days: **{totals[7]:,}**\n30 days: **{totals[30]:,}**")
        embed.add_field(name="Busiest channels (7 days)", value="\n".join(f"<#{cid}>: {n:,}" for cid, n in top) or "No data", inline=True)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(CommunityMore(bot))
