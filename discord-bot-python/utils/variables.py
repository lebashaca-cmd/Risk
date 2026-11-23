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



def safe_math(c, arg):
    """{math:2+2*3}: + - * / % ** and brackets only, nothing else is ever evaluated."""
    import ast
    import operator
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return walk(node.operand) * (1 if isinstance(node.op, ast.UAdd) else -1)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1e6):
                raise ValueError("too big")
            return ops[type(node.op)](left, right)
        raise ValueError("not allowed")

    if not arg or len(arg) > 100:
        return None
    value = walk(ast.parse(arg.strip(), mode="eval"))
    return str(int(value)) if float(value).is_integer() and abs(value) < 1e15 else f"{value:.6g}"


def days_between(arg, forward):
    try:
        day = datetime.strptime((arg or "").strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    delta = (day - now()).days + (1 if forward else 0) if forward else (now() - day).days
    return str(max(0, delta))


def text_arg(fn):
    return lambda c, a: None if a is None else fn(a)


def extra_get(key, default=None):
    return lambda c, a: c.extra.get(key, default)


def target_of(c):
    return c.extra.get("target")


def arg_n(n):
    def run(c, a):
        args = c.extra.get("args_list")
        if args is None:
            return None
        return clean(args[n - 1]) if len(args) >= n else ""
    return run


def stored(kind):
    """{var:name} and {counter:name}: values saved by custom command actions."""
    def run(c, a):
        values = c.extra.get("vars")
        if values is None or not a:
            return None
        return clean(values.get(a.strip().lower(), "" if kind == "var" else "0"))
    return run

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
    # --- more about the member
    ("{user.nick}", "Member", "The member's server nickname, or their account name if they have none.", "Sammy", need(M)(lambda c, a: clean(getattr(c.member, "nick", None) or c.member.name))),
    ("{user.tag}", "Member", "The account name with an @ in front, safe to show without pinging.", "@sam", need(M)(lambda c, a: "@" + ZWSP + c.member.name)),
    ("{user.color}", "Member", "The color of the member's name as a hex code.", "#e91e63", need(M)(lambda c, a: str(getattr(c.member, "color", "#000000")))),
    ("{user.isbot}", "Member", "yes or no: is the member a bot.", "no", need(M)(lambda c, a: "yes" if c.member.bot else "no")),
    ("{user.boosting}", "Member", "yes or no: is the member boosting the server.", "yes", need(M)(lambda c, a: "yes" if getattr(c.member, "premium_since", None) else "no")),
    ("{user.joinedago}", "Member", "How long ago the member joined this server.", "4 months", need(M)(lambda c, a: ago(c.member.joined_at) if getattr(c.member, "joined_at", None) else "unknown")),
    ("{user.roles}", "Member", "The names of the member's roles, up to 15.", "Member, Gamer", need(M)(lambda c, a: clean(", ".join(r.name for r in reversed(getattr(c.member, "roles", [])[1:])[:15]) or "none"))),
    ("{user.permissions}", "Member", "yes or no: does the member have the Administrator permission.", "no", need(M)(lambda c, a: "yes" if getattr(getattr(c.member, "guild_permissions", None), "administrator", False) else "no")),
    # --- more about the server
    ("{server.textchannels}", "Server", "How many text channels the server has.", "20", need(G)(lambda c, a: str(len(c.guild.text_channels)))),
    ("{server.voicechannels}", "Server", "How many voice channels the server has.", "6", need(G)(lambda c, a: str(len(c.guild.voice_channels)))),
    ("{server.categories}", "Server", "How many channel categories the server has.", "5", need(G)(lambda c, a: str(len(c.guild.categories)))),
    ("{server.banner}", "Server", "A link to the server's banner.", "https://cdn.discordapp.com/…", need(G)(lambda c, a: c.guild.banner.url if c.guild.banner else "no banner")),
    ("{server.verification}", "Server", "The server's verification level.", "medium", need(G)(lambda c, a: str(c.guild.verification_level))),
    ("{server.locale}", "Server", "The server's preferred language.", "en-US", need(G)(lambda c, a: str(c.guild.preferred_locale))),
    ("{server.age}", "Server", "How old the server is.", "2 years", need(G)(lambda c, a: ago(c.guild.created_at))),
    ("{server.humanratio}", "Server", "What percent of the members are people rather than bots.", "99%", need(G)(lambda c, a: f"{round(100 * humans(c.guild) / max(1, c.guild.member_count or 1))}%")),
    # --- more about the channel
    ("{channel.id}", "Channel", "The channel's ID.", "123456789012345678", need("channel")(lambda c, a: str(c.channel.id))),
    ("{channel.topic}", "Channel", "The channel's topic.", "Chat about anything", need("channel")(lambda c, a: clean(getattr(c.channel, "topic", None) or "no topic"))),
    ("{channel.category}", "Channel", "The name of the category the channel is in.", "Text channels", need("channel")(lambda c, a: clean(getattr(getattr(c.channel, "category", None), "name", None) or "none"))),
    ("{channel.slowmode}", "Channel", "The channel's slowmode in seconds.", "5", need("channel")(lambda c, a: str(getattr(c.channel, "slowmode_delay", 0)))),
    ("{channel.created}", "Channel", "The date the channel was made.", "May 2, 2025", need("channel")(lambda c, a: stamp(getattr(c.channel, "created_at", None), "D"))),
    ("{channel.nsfw}", "Channel", "yes or no: is the channel age-restricted.", "no", need("channel")(lambda c, a: "yes" if getattr(c.channel, "nsfw", False) else "no")),
    # --- more time
    ("{hour}", "Time", "The hour in UTC, 24-hour clock.", "14", lambda c, a: f"{now():%H}"),
    ("{minute}", "Time", "The minute in UTC.", "05", lambda c, a: f"{now():%M}"),
    ("{date.iso}", "Time", "Today's date as year-month-day, in UTC.", "2026-11-08", lambda c, a: f"{now():%Y-%m-%d}"),
    ("{time.12}", "Time", "The time in UTC on a 12-hour clock.", "2:05 PM", lambda c, a: f"{now():%I:%M %p}".lstrip("0")),
    ("{until:2026-12-25}", "Time", "Whole days left until a date (year-month-day). 0 once it has passed.", "47", None),
    ("{since:2026-01-01}", "Time", "Whole days since a date (year-month-day).", "311", None),
    # --- text and numbers (put your own text after the colon)
    ("{upper:text}", "Text", "Your text in CAPITAL letters. You can put another variable inside.", "HELLO", None),
    ("{lower:text}", "Text", "Your text in small letters.", "hello", None),
    ("{title:text}", "Text", "Your text with each Word Capitalised.", "Hello World", None),
    ("{len:text}", "Text", "How many characters your text has.", "5", None),
    ("{reverse:text}", "Text", "Your text backwards.", "olleh", None),
    ("{math:2+2*3}", "Text", "Does the sum. Use + - * / % ** and brackets.", "8", None),
    ("{percent:50}", "Random", "Shows yes about that many percent of the time, otherwise no.", "yes", None),
    ("{eightball}", "Random", "A magic 8-ball answer.", "Signs point to yes.", lambda c, a: random.choice(("It is certain.", "Without a doubt.", "Yes, definitely.", "Most likely.", "Signs point to yes.", "Ask again later.", "Cannot predict now.", "Don't count on it.", "My sources say no.", "Very doubtful."))),
    ("{rps}", "Random", "rock, paper or scissors.", "paper", lambda c, a: random.choice(("rock", "paper", "scissors"))),
    ("{color}", "Random", "A random color as a hex code.", "#4caf50", lambda c, a: "#%06x" % random.randint(0, 0xFFFFFF)),
    ("{uuid}", "Random", "A short random code, handy for tickets and giveaways.", "a3f9c2", lambda c, a: "%06x" % random.randint(0, 0xFFFFFF)),
    # --- custom commands only
    ("{args}", "Custom commands", "Everything typed after the command name.", "hello there", None),
    ("{arg1}", "Custom commands", "The first word typed after the command. {arg2} to {arg9} work too.", "hello", None),
    ("{argcount}", "Custom commands", "How many words were typed after the command.", "2", None),
    ("{target}", "Custom commands", "The first member mentioned (or the first word, if it is a member's name or ID). Mentions them.", "@Alex", None),
    ("{target.name}", "Custom commands", "The target's display name, without a mention.", "Alex", None),
    ("{target.id}", "Custom commands", "The target's ID.", "123456789012345678", None),
    ("{target.avatar}", "Custom commands", "A link to the target's profile picture.", "https://cdn.discordapp.com/…", None),
    ("{command}", "Custom commands", "The name of the custom command being run.", "rules", None),
    ("{uses}", "Custom commands", "How many times this custom command has been run, including now.", "12", None),
    ("{message.id}", "Custom commands", "The ID of the message that ran the command.", "123456789012345678", None),
    ("{message.link}", "Custom commands", "A link to the message that ran the command.", "https://discord.com/channels/…", None),
    ("{var:name}", "Custom commands", "A value saved by a Set variable action. Empty if nothing is saved yet.", "blue", None),
    ("{counter:name}", "Custom commands", "A number saved by an Add to counter action. 0 if nothing is saved yet.", "3", None),
    ("{created.role}", "Custom commands", "The role a Create role action just made, as a mention.", "@Event", None),
    ("{created.channel}", "Custom commands", "The channel a Create channel action just made, as a link.", "#event", None),
    ("{invite}", "Custom commands", "The link a Create invite action just made.", "https://discord.gg/…", None),
    # --- levels (only inside level-up messages)
    ("{level}", "Levels", "The level the member just reached. Level-up messages only.", "7", None),
    ("{xp}", "Levels", "The member's total XP. Level-up messages only.", "1,540", None),
    ("{nextlevel}", "Levels", "The next level to reach. Level-up messages only.", "8", None),
    ("{messages}", "Levels", "How many messages the member has sent. Level-up messages only.", "412", None),
]

TAKES_ARGUMENT = {"random", "choose", "upper", "lower", "title", "len", "reverse", "math", "percent", "until", "since", "var", "counter"}
HANDLERS = {}
for token, _group, _desc, _example, handler in VARIABLES:
    if handler is not None:
        HANDLERS[token[1:-1].split(":")[0].lower()] = handler
HANDLERS["random"] = rand_range
HANDLERS["choose"] = choose
HANDLERS["upper"] = text_arg(lambda a: a.upper())
HANDLERS["lower"] = text_arg(lambda a: a.lower())
HANDLERS["title"] = text_arg(lambda a: a.title())
HANDLERS["len"] = text_arg(lambda a: str(len(a)))
HANDLERS["reverse"] = text_arg(lambda a: a[::-1])
HANDLERS["math"] = safe_math
HANDLERS["percent"] = lambda c, a: ("yes" if random.random() * 100 < float(a) else "no") if a and re.fullmatch(r"\s*\d{1,3}(\.\d+)?\s*", a) else None
HANDLERS["until"] = lambda c, a: days_between(a, True)
HANDLERS["since"] = lambda c, a: days_between(a, False)
HANDLERS["args"] = lambda c, a: clean(c.extra["args"]) if "args" in c.extra else None
HANDLERS["argcount"] = lambda c, a: str(len(c.extra["args_list"])) if "args_list" in c.extra else None
for _n in range(1, 10):
    HANDLERS[f"arg{_n}"] = arg_n(_n)
HANDLERS["target"] = lambda c, a: (target_of(c).mention if target_of(c) else "nobody") if "has_target" in c.extra else None
HANDLERS["target.name"] = lambda c, a: (clean(target_of(c).display_name) if target_of(c) else "nobody") if "has_target" in c.extra else None
HANDLERS["target.id"] = lambda c, a: (str(target_of(c).id) if target_of(c) else "") if "has_target" in c.extra else None
HANDLERS["target.avatar"] = lambda c, a: (target_of(c).display_avatar.url if target_of(c) else "") if "has_target" in c.extra else None
HANDLERS["command"] = extra_get("command")
HANDLERS["uses"] = lambda c, a: str(c.extra["uses"]) if "uses" in c.extra else None
HANDLERS["message.id"] = extra_get("message_id")
HANDLERS["message.link"] = extra_get("message_link")
HANDLERS["var"] = stored("var")
HANDLERS["counter"] = stored("counter")
HANDLERS["created.role"] = extra_get("created_role")
HANDLERS["created.channel"] = extra_get("created_channel")
HANDLERS["invite"] = extra_get("invite")
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
        if match.group(2) is not None and match.group(1).lower() not in TAKES_ARGUMENT:
            return match.group(0)
        try:
            out = handler(c, match.group(2))
        except Exception:
            return match.group(0)
        return match.group(0) if out is None else str(out)

    for _ in range(4):  # inside-out, so {upper:{user.name}} and {math:{counter:n}*2} work
        filled = TOKEN.sub(fill, text)
        if filled == text or "{" not in filled:
            return filled
        text = filled
    return text
