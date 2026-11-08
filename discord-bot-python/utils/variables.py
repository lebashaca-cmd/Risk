"""The {variables} Risk fills in inside welcome messages, level messages, auto-replies, custom commands and more.

Every variable is listed once in VARIABLES, which is also what the docs site and `!variables` show, so the
list people read can't drift from what actually works. A token that isn't listed is left exactly as typed.

Variables that come from a member or server are cleaned so a name like "@everyone" can't ping anyone.
"""
import random
import re
import time
from datetime import datetime, timezone

TOKEN = re.compile(r"\{([A-Za-z][A-Za-z0-9_.]*)(?::([^{}]{0,300}))?\}")
ZWSP = "​"

EMOJI = {
    "check": "✅", "cross": "❌", "star": "⭐", "party": "🎉", "wave": "👋", "heart": "❤️",
    "fire": "🔥", "crown": "👑", "sparkles": "✨",
}


class Ctx:
    """What a variable can look at. Any part may be missing (a test message has no real channel, say)."""

    def __init__(self, member=None, guild=None, channel=None, extra=None):
        self.member = member
        self.guild = guild or getattr(member, "guild", None)
        self.channel = channel
        self.extra = extra or {}


def clean(text):
    """Break @mentions apart so user-controlled text can never ping."""
    return str(text).replace("@", "@" + ZWSP)


def ago(moment):
    """'3 years', '5 months', '12 days' ... the largest whole unit, since a moment in the past."""
    seconds = max(0, int((datetime.now(timezone.utc) - moment).total_seconds()))
    for name, size in (("year", 31536000), ("month", 2592000), ("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = seconds // size
            return f"{n} {name}{'' if n == 1 else 's'}"
    return "less than a minute"


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def stamp(moment, style):
    return f"<t:{int(moment.timestamp())}:{style}>" if moment else "unknown"


def now():
    return datetime.now(timezone.utc)


def bot_count(guild):
    return sum(1 for m in guild.members if m.bot)


def humans(guild):
    return max(0, (guild.member_count or 0) - bot_count(guild))


def top_role(member):
    role = getattr(member, "top_role", None)
    return role.name if role is not None and role.name != "@everyone" else "none"


def position(member):
    guild = member.guild
    ordered = sorted((m for m in guild.members if m.joined_at), key=lambda m: m.joined_at)
    for i, m in enumerate(ordered, 1):
        if m.id == member.id:
            return i
    return guild.member_count or 0


def need(*names):
    """Wrap a function so it answers None (token left alone) when what it needs is missing."""
    def wrap(fn):
        def run(c, arg):
            for name in names:
                if getattr(c, name, None) is None:
                    return None
            return fn(c, arg)
        return run
    return wrap


def rand_range(c, arg):
    match = re.fullmatch(r"\s*(-?\d{1,9})\s*-\s*(-?\d{1,9})\s*", arg or "")
    if not match:
        return None
    low, high = sorted((int(match.group(1)), int(match.group(2))))
    return str(random.randint(low, high))


def choose(c, arg):
    options = [o.strip() for o in (arg or "").split("|") if o.strip()]
    return random.choice(options) if options else None


# (token, group, description, example, handler). A handler takes (ctx, argument) and returns text or None.
M, G = "member", "guild"
VARIABLES = [
    # --- the original few
    ("{user}", "Member", "Mentions the member in a normal message, and shows their bold name inside an {embed}.", "@Sam", None),
    ("{name}", "Member", "The member's display name, without a mention.", "Sam", need(M)(lambda c, a: clean(c.member.display_name))),
    ("{server}", "Server", "The server's name.", "Risk HQ", need(G)(lambda c, a: clean(c.guild.name))),
    ("{embed}", "Layout", "Put it at the very start and very end of a message to send the whole message as an embed.", "{embed}Hello!{embed}", None),
    # --- member
    ("{username}", "Member", "The member's account name, not their server nickname.", "sam", need(M)(lambda c, a: clean(c.member.name))),
    ("{user.id}", "Member", "The member's Discord ID.", "123456789012345678", need(M)(lambda c, a: str(c.member.id))),
    ("{user.mention}", "Member", "Always a mention, even inside an embed.", "@Sam", need(M)(lambda c, a: c.member.mention)),
    ("{user.avatar}", "Member", "A link to the member's profile picture.", "https://cdn.discordapp.com/…", need(M)(lambda c, a: c.member.display_avatar.url)),
    ("{user.created}", "Member", "The date the account was made, shown in each reader's own time zone.", "March 4, 2021", need(M)(lambda c, a: stamp(c.member.created_at, "D"))),
    ("{user.age}", "Member", "How old the account is.", "3 years", need(M)(lambda c, a: ago(c.member.created_at))),
    ("{user.joined}", "Member", "The date the member joined this server.", "June 1, 2026", need(M)(lambda c, a: stamp(getattr(c.member, "joined_at", None), "D"))),
    ("{user.toprole}", "Member", "The name of the member's highest role.", "Moderator", need(M)(lambda c, a: clean(top_role(c.member)))),
    ("{user.rolecount}", "Member", "How many roles the member has.", "4", need(M)(lambda c, a: str(max(0, len(getattr(c.member, "roles", [])) - 1)))),
    ("{ordinal}", "Member", "The member's join position with its ending: 1st, 2nd, 3rd...", "1,204th", need(M)(lambda c, a: ordinal(position(c.member)))),
    ("{position}", "Member", "The member's join position as a plain number.", "1204", need(M)(lambda c, a: str(position(c.member)))),
    # --- server
    ("{server.id}", "Server", "The server's ID.", "987654321098765432", need(G)(lambda c, a: str(c.guild.id))),
    ("{server.owner}", "Server", "The server owner's display name.", "Alex", need(G)(lambda c, a: clean(c.guild.owner.display_name) if c.guild.owner else "unknown")),
    ("{server.members}", "Server", "How many members the server has, bots included.", "1,204", need(G)(lambda c, a: f"{c.guild.member_count or 0:,}")),
    ("{server.humans}", "Server", "How many members are people, not bots.", "1,190", need(G)(lambda c, a: f"{humans(c.guild):,}")),
    ("{server.bots}", "Server", "How many members are bots.", "14", need(G)(lambda c, a: f"{bot_count(c.guild):,}")),
    ("{server.channels}", "Server", "How many channels the server has.", "32", need(G)(lambda c, a: str(len(c.guild.channels)))),
    ("{server.roles}", "Server", "How many roles the server has.", "18", need(G)(lambda c, a: str(max(0, len(c.guild.roles) - 1)))),
    ("{server.boosts}", "Server", "How many boosts the server has.", "9", need(G)(lambda c, a: str(c.guild.premium_subscription_count or 0))),
    ("{server.boostlevel}", "Server", "The server's boost level, 0 to 3.", "2", need(G)(lambda c, a: str(c.guild.premium_tier))),
    ("{server.created}", "Server", "The date the server was made.", "January 9, 2020", need(G)(lambda c, a: stamp(c.guild.created_at, "D"))),
    ("{server.icon}", "Server", "A link to the server's icon.", "https://cdn.discordapp.com/…", need(G)(lambda c, a: c.guild.icon.url if c.guild.icon else "no icon")),
    ("{server.description}", "Server", "The server's community description.", "A friendly place to chat", need(G)(lambda c, a: clean(c.guild.description or "no description"))),
    ("{server.emojis}", "Server", "How many custom emojis the server has.", "25", need(G)(lambda c, a: str(len(c.guild.emojis)))),
    # --- channel and bot
    ("{channel}", "Channel", "The name of the channel the message is sent in.", "general", need("channel")(lambda c, a: clean(getattr(c.channel, "name", "") or "unknown"))),
    ("{channel.mention}", "Channel", "A clickable link to the channel.", "#general", need("channel")(lambda c, a: getattr(c.channel, "mention", "#" + str(getattr(c.channel, "name", "unknown"))))),
    ("{bot}", "Channel", "The bot's name.", "Risk", lambda c, a: clean(c.guild.me.display_name) if c.guild is not None and getattr(c.guild, "me", None) else "Risk"),
    # --- time (UTC)
    ("{date}", "Time", "Today's date in UTC.", "8 November 2026", lambda c, a: f"{now().day} {now():%B %Y}"),
    ("{time}", "Time", "The current time in UTC.", "14:05 UTC", lambda c, a: f"{now():%H:%M} UTC"),
    ("{day}", "Time", "The day of the week in UTC.", "Sunday", lambda c, a: f"{now():%A}"),
    ("{month}", "Time", "The month name in UTC.", "November", lambda c, a: f"{now():%B}"),
    ("{year}", "Time", "The year in UTC.", "2026", lambda c, a: str(now().year)),
    ("{timestamp}", "Time", "The current Unix timestamp, in seconds.", "1794233100", lambda c, a: str(int(time.time()))),
    ("{now}", "Time", "The current date and time, shown in each reader's own time zone.", "November 8, 2026 2:05 PM", lambda c, a: stamp(now(), "f")),
    ("{now.relative}", "Time", "'just now' that keeps counting for readers. Best for a message that stays on screen.", "a few seconds ago", lambda c, a: stamp(now(), "R")),
    # --- random
    ("{random:1-100}", "Random", "A random whole number between the two you give. Use any range, such as {random:1-6}.", "42", None),
    ("{choose:a|b|c}", "Random", "One of your options, picked at random. Separate them with |.", "b", None),
    ("{coin}", "Random", "Heads or tails.", "Heads", lambda c, a: random.choice(("Heads", "Tails"))),
    ("{dice}", "Random", "A six-sided dice roll.", "4", lambda c, a: str(random.randint(1, 6))),
    # --- layout
    ("{newline}", "Layout", "A line break. Useful in places that only take one line, like the dashboard's text boxes.", "", lambda c, a: "\n"),
    # --- emoji shortcuts
    *[("{" + name + "}", "Emoji", f"The {name} emoji.", emoji, (lambda e: lambda c, a: e)(emoji)) for name, emoji in EMOJI.items()],
    # --- levels (only inside level-up messages)
    ("{level}", "Levels", "The level the member just reached. Level-up messages only.", "7", None),
    ("{xp}", "Levels", "The member's total XP. Level-up messages only.", "1,540", None),
    ("{nextlevel}", "Levels", "The next level to reach. Level-up messages only.", "8", None),
    ("{messages}", "Levels", "How many messages the member has sent. Level-up messages only.", "412", None),
]

HANDLERS = {}
for token, _group, _desc, _example, handler in VARIABLES:
    if handler is not None:
        HANDLERS[token[1:-1].split(":")[0].lower()] = handler
HANDLERS["random"] = rand_range
HANDLERS["choose"] = choose
HANDLERS["xp"] = lambda c, a: c.extra.get("xp")
HANDLERS["nextlevel"] = lambda c, a: c.extra.get("nextlevel")
HANDLERS["messages"] = lambda c, a: c.extra.get("messages")
HANDLERS["level"] = lambda c, a: c.extra.get("level")


def catalog():
    """The variables as plain dicts, for the docs and `!variables`."""
    return [{"token": t, "group": g, "description": d, "example": e} for t, g, d, e, _h in VARIABLES]


def expand(text, member=None, guild=None, channel=None, extra=None):
    """Fill in every known {variable}. `extra` supplies level values: level, xp, nextlevel, messages."""
    if not text or "{" not in text:
        return text
    c = Ctx(member, guild, channel, extra)

    def fill(match):
        handler = HANDLERS.get(match.group(1).lower())
        if handler is None:
            return match.group(0)
        if match.group(2) is not None and match.group(1).lower() not in ("random", "choose"):
            return match.group(0)
        try:
            out = handler(c, match.group(2))
        except Exception:
            return match.group(0)
        return match.group(0) if out is None else str(out)

    return TOKEN.sub(fill, text)
