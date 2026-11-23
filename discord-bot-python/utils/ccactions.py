"""The steps a custom command can run: send things, hand out roles, make channels, moderate and more.

Every step type is listed once in ACTIONS. That list is what the dashboard editor draws, so what people can pick and
what Risk really does can't drift apart. A command is a list of steps run in order.

Safety, because anyone allowed to run a command runs it with the bot's permissions:
- A command whose steps change roles, channels or members must be limited to moderators or to chosen roles (see needs_gate).
- Roles with moderator permissions are never handed out, and nobody above the bot (or above the person running it) can be targeted.
- Steps are capped (MAX_STEPS, MAX_CREATES), the whole run has a time limit, and every risky step is written to the VIP log.
"""
import asyncio
import random
import re
import time
from datetime import timedelta

import discord

from utils.variables import expand

MAX_STEPS = 15
MAX_CREATES = 5
MAX_WAIT_TOTAL = 15
RUN_TIMEOUT = 40
RISKY = ("administrator", "manage_guild", "manage_roles", "manage_channels", "manage_webhooks", "ban_members", "kick_members", "mention_everyone", "manage_messages", "moderate_members", "manage_nicknames")
CHANNEL_TYPES = {"text": "Text channel", "voice": "Voice channel", "category": "Category", "announcement": "Announcement channel", "forum": "Forum", "stage": "Stage channel"}

WHO = {"kind": "select", "key": "who", "label": "Who it affects", "options": {"user": "The person who ran the command", "target": "The member they mentioned"}, "default": "user"}


def field(key, label, kind="text", **extra):
    return {"key": key, "label": label, "kind": kind, **extra}


CHANNEL_CUR = field("channel", "Channel", "channel", hint="Leave on 'This channel' to use the channel the command was typed in.")
REASON = field("reason", "Reason (shown in the audit log)", "name", default="Custom command")

# type: (label, group, danger, fields). danger means it changes the server and needs a moderator-only command.
ACTIONS = {
    # ---- messages
    "reply": ("Reply", "Messages", False, [field("text", "Message", "text")]),
    "send": ("Send to a channel", "Messages", False, [field("channel", "Channel", "channel", hint="Pick where the message goes."), field("text", "Message", "text")]),
    "embed": ("Send an embed", "Messages", False, [field("channel", "Channel (blank for this one)", "channel"), field("title", "Title", "name"), field("text", "Description", "text"), field("color", "Color (hex like #5865f2)", "name"), field("footer", "Footer", "name"), field("image", "Image link", "name"), field("thumbnail", "Small image link", "name")]),
    "dm": ("Send a DM", "Messages", False, [{**WHO, "default": "user"}, field("text", "Message", "text")]),
    "react": ("React to the message", "Messages", False, [field("emoji", "Emoji", "name", hint="Type the emoji itself.")]),
    "delete_trigger": ("Delete the message that ran it", "Messages", False, []),
    "pin": ("Pin the message that ran it", "Messages", True, []),
    "thread": ("Start a thread on the message", "Messages", False, [field("name", "Thread name", "name", default="{user}'s thread")]),
    "wait": ("Wait", "Flow", False, [field("seconds", "Seconds (1 to 10)", "number", min=1, max=10, default=2)]),
    # ---- flow
    "stop_unless_role": ("Stop unless they have a role", "Flow", False, [field("role", "Role", "role")]),
    "stop_if_role": ("Stop if they have a role", "Flow", False, [field("role", "Role", "role")]),
    "stop_unless_args": ("Stop unless they typed enough words", "Flow", False, [field("count", "Words needed", "number", min=1, max=9, default=1), field("text", "Message if they didn't (optional)", "text")]),
    "stop_unless_target": ("Stop unless they mentioned a member", "Flow", False, [field("text", "Message if they didn't (optional)", "text")]),
    "stop_chance": ("Only continue some of the time", "Flow", False, [field("percent", "Chance to continue (%)", "number", min=1, max=100, default=50)]),
    # ---- saved values
    "set_var": ("Save a variable", "Saved values", False, [field("name", "Name", "name", hint="Letters and numbers. Read it later with {var:name}."), field("value", "Value", "text")]),
    "add_counter": ("Add to a counter", "Saved values", False, [field("name", "Name", "name", hint="Read it later with {counter:name}."), field("amount", "Add (can be negative)", "number", min=-1000, max=1000, default=1)]),
    "reset_var": ("Clear a variable or counter", "Saved values", False, [field("name", "Name", "name")]),
    # ---- roles
    "add_role": ("Give a role", "Roles", False, [WHO, field("role", "Role", "role")]),
    "remove_role": ("Take a role", "Roles", False, [WHO, field("role", "Role", "role")]),
    "toggle_role": ("Toggle a role", "Roles", False, [WHO, field("role", "Role", "role")]),
    "create_role": ("Create a role", "Roles", True, [field("name", "Name", "name"), field("color", "Color (hex)", "name"), field("hoist", "Show separately in the member list", "bool"), field("mentionable", "Anyone can mention it", "bool"), field("give", "Give it to", "select", options={"none": "Nobody", "user": "The person who ran the command", "target": "The member they mentioned"}, default="user")]),
    "delete_role": ("Delete a role", "Roles", True, [field("role", "Role", "role")]),
    "rename_role": ("Rename a role", "Roles", True, [field("role", "Role", "role"), field("name", "New name", "name")]),
    "role_color": ("Change a role's color", "Roles", True, [field("role", "Role", "role"), field("color", "Color (hex)", "name")]),
    # ---- channels
    "create_channel": ("Create a channel", "Channels", True, [field("name", "Name", "name"), field("ctype", "Type", "select", options=CHANNEL_TYPES, default="text"), field("category", "Put it in category", "channel", kinds=["category"]), field("topic", "Topic (text channels)", "name"), field("private", "Private: only the person who ran it and moderators can see it", "bool")]),
    "delete_channel": ("Delete a channel", "Channels", True, [field("channel", "Channel", "channel", kinds=["any"])]),
    "rename_channel": ("Rename a channel", "Channels", True, [field("channel", "Channel", "channel", kinds=["any"]), field("name", "New name", "name")]),
    "set_topic": ("Set a channel topic", "Channels", True, [CHANNEL_CUR, field("text", "Topic", "name")]),
    "slowmode": ("Set slowmode", "Channels", True, [CHANNEL_CUR, field("seconds", "Seconds (0 turns it off)", "number", min=0, max=21600, default=5)]),
    "lock_channel": ("Lock a channel", "Channels", True, [CHANNEL_CUR]),
    "unlock_channel": ("Unlock a channel", "Channels", True, [CHANNEL_CUR]),
    "hide_channel": ("Hide a channel from everyone", "Channels", True, [field("channel", "Channel", "channel", kinds=["any"])]),
    "show_channel": ("Show a hidden channel again", "Channels", True, [field("channel", "Channel", "channel", kinds=["any"])]),
    "clone_channel": ("Copy a channel", "Channels", True, [field("channel", "Channel", "channel", kinds=["any"]), field("name", "Name for the copy", "name")]),
    "voice_limit": ("Set a voice channel's user limit", "Channels", True, [field("channel", "Voice channel", "channel", kinds=["voice", "stage"]), field("limit", "Limit (0 is no limit)", "number", min=0, max=99, default=0)]),
    "create_invite": ("Create an invite link", "Channels", False, [CHANNEL_CUR, field("hours", "Lasts (hours, 0 is forever)", "number", min=0, max=168, default=24), field("uses", "Max uses (0 is unlimited)", "number", min=0, max=100, default=1)]),
    "purge": ("Delete recent messages", "Channels", True, [CHANNEL_CUR, field("count", "How many (1 to 100)", "number", min=1, max=100, default=10)]),
    # ---- members (always the mentioned member)
    "nickname": ("Change a nickname", "Members", False, [WHO, field("text", "Nickname (blank resets it)", "name")]),
    "timeout": ("Time out the mentioned member", "Members", True, [field("minutes", "Minutes", "number", min=1, max=40320, default=10), REASON]),
    "untimeout": ("End the mentioned member's timeout", "Members", True, [REASON]),
    "kick": ("Kick the mentioned member", "Members", True, [REASON]),
    "ban": ("Ban the mentioned member", "Members", True, [field("days", "Delete their messages from the last (days)", "number", min=0, max=7, default=0), REASON]),
    "move_voice": ("Move the mentioned member to a voice channel", "Members", True, [field("channel", "Voice channel", "channel", kinds=["voice", "stage"])]),
    "disconnect_voice": ("Disconnect the mentioned member from voice", "Members", True, []),
    "add_xp": ("Give or take XP", "Members", True, [WHO, field("amount", "XP (can be negative)", "number", min=-5000, max=5000, default=50)]),
}


def catalog():
    """The step types as plain data for the dashboard and !customcmd actions."""
    out = []
    for key, (label, group, danger, fields) in ACTIONS.items():
        out.append({"type": key, "label": label, "group": group, "danger": danger, "fields": fields})
    return out


def is_danger(step):
    """True when a step changes the server or someone else, so only moderators (or chosen roles) may run it."""
    info = ACTIONS.get(step.get("type"))
    if info is None:
        return False
    if info[2]:
        return True
    if step.get("type") in ("add_role", "remove_role", "toggle_role", "nickname", "dm") and step.get("who") == "target":
        return step["type"] != "dm"
    return False


def needs_gate(steps):
    return any(is_danger(s) for s in steps)


def clean_steps(raw, error):
    """Validates the steps a person saved. `error(message)` raises the caller's own kind of error."""
    if not isinstance(raw, list):
        error("Steps must be a list.")
    if len(raw) > MAX_STEPS:
        error(f"A command can have up to {MAX_STEPS} steps.")
    out = []
    for i, step in enumerate(raw, 1):
        if not isinstance(step, dict) or step.get("type") not in ACTIONS:
            error(f"Step {i} isn't a step Risk knows.")
        label, _group, _danger, fields = ACTIONS[step["type"]]
        clean = {"type": step["type"]}
        for f in fields:
            value = step.get(f["key"], f.get("default"))
            kind = f["kind"]
            if kind == "number":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = f.get("default", f["min"])
                value = max(f["min"], min(f["max"], value))
            elif kind == "bool":
                value = bool(value)
            elif kind == "select":
                value = value if value in f["options"] else f["default"]
            elif kind in ("channel", "role"):
                value = str(value or "")
                if value and not (value.isdigit() or value in ("created", "current")):
                    error(f"Step {i} ({label}): pick a {kind} from the list.")
            else:
                value = str(value if value is not None else "")[:1900 if kind == "text" else 200]
            if value == "" and f.get("required"):
                error(f"Step {i} ({label}): {f['label']} is needed.")
            clean[f["key"]] = value
        out.append(clean)
    return out


class Stop(Exception):
    """A flow step decided the command should end here, quietly."""


class StepFailed(Exception):
    pass


def hex_colour(text):
    text = (text or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return discord.Color(int(text, 16))
    return None


class Run:
    """One run of one custom command by one person."""

    def __init__(self, bot, message, name, command, args, uses, values):
        self.bot, self.message, self.name, self.command = bot, message, name, command
        self.guild, self.author, self.channel = message.guild, message.author, message.channel
        self.args = args
        self.values = values  # the server's saved variables, changed by steps
        self.target = None
        self.creates = 0
        self.waited = 0
        self.log = []
        self.problems = []
        self.touched = False
        self.touched_values = False
        words = args.split()
        self.extra = {"args": args, "args_list": words, "has_target": True, "target": None, "command": name, "uses": uses, "message_id": str(message.id),
                      "message_link": message.jump_url, "vars": values}

    # ---------------------------------------------------------------- text and lookups
    def fmt(self, text, name=False):
        """Fills in {variables}. In places that can't hold a mention (names, topics) {user} is the plain name."""
        text = text or ""
        text = text.replace("{user}", self.author.display_name if name else self.author.mention)
        out = expand(text, member=self.author, guild=self.guild, channel=self.channel, extra=self.extra)
        return out.replace("@everyone", "@​everyone").replace("@here", "@​here")

    async def find_target(self):
        mentioned = [m for m in self.message.mentions if hasattr(m, "top_role")]
        if mentioned:
            self.target = mentioned[0]
        elif self.args.split():
            word = self.args.split()[0].strip("<@!>")
            member = None
            if word.isdigit():
                member = self.guild.get_member(int(word))
            if member is None:
                low = word.lower()
                member = discord.utils.find(lambda m: low in (m.name.lower(), m.display_name.lower()), self.guild.members)
            self.target = member
        self.extra["target"] = self.target

    def member(self, step):
        if step.get("who") == "target" or step["type"] in ("timeout", "untimeout", "kick", "ban", "move_voice", "disconnect_voice"):
            if self.target is None:
                raise StepFailed("mention a member for that one")
            return self.target
        return self.author

    def check_target(self, member):
        """Moderation steps refuse owners, the bot and anyone who outranks the bot or the person running the command."""
        if member.id == self.guild.owner_id or member.id == self.guild.me.id:
            raise StepFailed("I can't do that to the server owner or to myself")
        if member.top_role >= self.guild.me.top_role:
            raise StepFailed(f"{member.display_name} ranks at or above my highest role")
        if member != self.author and self.author.id != self.guild.owner_id and member.top_role >= self.author.top_role:
            raise StepFailed(f"{member.display_name} ranks at or above you")

    def role(self, step, key="role"):
        value = step.get(key)
        role = self.extra.get("_role") if value == "created" else self.guild.get_role(int(value)) if value and value.isdigit() else None
        if role is None:
            raise StepFailed("the role isn't there any more")
        return role

    def channel_of(self, step, key="channel"):
        value = step.get(key)
        if value in ("", None, "current"):
            return self.channel
        if value == "created":
            channel = self.extra.get("_channel")
        else:
            channel = self.guild.get_channel(int(value)) if value.isdigit() else None
        if channel is None:
            raise StepFailed("the channel isn't there any more")
        return channel

    def safe_role(self, role):
        if role.is_default() or role.managed:
            raise StepFailed(f"@{role.name} can't be handed out")
        if role >= self.guild.me.top_role:
            raise StepFailed(f"@{role.name} is above my highest role")
        if any(getattr(role.permissions, p) for p in RISKY):
            raise StepFailed(f"@{role.name} has moderator permissions, so custom commands never give it out")

    # ---------------------------------------------------------------- running
    async def go(self, steps):
        await self.find_target()
        started = time.monotonic()
        for index, step in enumerate(steps, 1):
            if time.monotonic() - started > RUN_TIMEOUT:
                self.problems.append("The command took too long and was stopped.")
                break
            label = ACTIONS[step["type"]][0]
            try:
                await getattr(self, "do_" + step["type"])(step)
                if is_danger(step):
                    self.touched = True
            except Stop:
                break
            except StepFailed as error:
                self.problems.append(f"Step {index} ({label}): {error}.")
                break
            except discord.Forbidden:
                self.problems.append(f"Step {index} ({label}): I'm missing a permission for that. Check my role and the channel's permissions.")
                break
            except discord.HTTPException as error:
                self.problems.append(f"Step {index} ({label}): Discord refused ({error.text or error.status}).")
                break

    async def say(self, channel, content=None, embed=None):
        allowed = discord.AllowedMentions(users=[self.author] + ([self.target] if self.target else []), roles=False, everyone=False)
        return await channel.send(content=content[:2000] if content else None, embed=embed, allowed_mentions=allowed)

    # ---------------------------------------------------------------- messages
    async def do_reply(self, s):
        await self.say(self.channel, self.fmt(s["text"]) or "​")

    async def do_send(self, s):
        channel = self.channel_of(s)
        if not isinstance(channel, discord.abc.Messageable) or isinstance(channel, (discord.VoiceChannel, discord.CategoryChannel)) and not hasattr(channel, "send"):
            raise StepFailed("that channel can't take messages")
        if not channel.permissions_for(self.guild.me).send_messages:
            raise StepFailed(f"I can't send messages in #{channel.name}")
        await self.say(channel, self.fmt(s["text"]) or "​")

    async def do_embed(self, s):
        channel = self.channel_of(s)
        embed = discord.Embed(title=self.fmt(s["title"], True)[:256] or None, description=self.fmt(s["text"])[:4000] or None, color=hex_colour(self.fmt(s["color"])) or discord.Color.blurple())
        if s["footer"]:
            embed.set_footer(text=self.fmt(s["footer"], True)[:200])
        for key, setter in (("image", embed.set_image), ("thumbnail", embed.set_thumbnail)):
            url = self.fmt(s[key]).strip()
            if re.fullmatch(r"https?://\S{4,500}", url):
                setter(url=url)
        if not (embed.title or embed.description or embed.image or embed.thumbnail):
            raise StepFailed("the embed is empty")
        await self.say(channel, None, embed)

    async def do_dm(self, s):
        member = self.member(s)
        try:
            await member.send(self.fmt(s["text"])[:2000] or "​")
        except discord.Forbidden:
            raise StepFailed(f"{member.display_name} has DMs closed")

    async def do_react(self, s):
        emoji = s["emoji"].strip()
        try:
            await self.message.add_reaction(discord.PartialEmoji.from_str(emoji) if emoji.startswith("<") else emoji)
        except discord.HTTPException:
            raise StepFailed("that emoji didn't work")

    async def do_delete_trigger(self, s):
        try:
            await self.message.delete()
        except discord.HTTPException:
            pass

    async def do_pin(self, s):
        await self.message.pin(reason=f"Custom command {self.name}")

    async def do_thread(self, s):
        await self.message.create_thread(name=(self.fmt(s["name"], True) or "Thread")[:90], auto_archive_duration=1440)

    async def do_wait(self, s):
        seconds = max(1, min(10, int(s["seconds"])))
        if self.waited + seconds > MAX_WAIT_TOTAL:
            raise StepFailed("waits can add up to 15 seconds at most")
        self.waited += seconds
        await asyncio.sleep(seconds)

    # ---------------------------------------------------------------- flow
    async def do_stop_unless_role(self, s):
        if self.role(s) not in getattr(self.author, "roles", []):
            raise Stop

    async def do_stop_if_role(self, s):
        if self.role(s) in getattr(self.author, "roles", []):
            raise Stop

    async def do_stop_unless_args(self, s):
        if len(self.args.split()) < int(s["count"]):
            if s.get("text"):
                await self.say(self.channel, self.fmt(s["text"]))
            raise Stop

    async def do_stop_unless_target(self, s):
        if self.target is None:
            if s.get("text"):
                await self.say(self.channel, self.fmt(s["text"]))
            raise Stop

    async def do_stop_chance(self, s):
        if random.random() * 100 >= int(s["percent"]):
            raise Stop

    # ---------------------------------------------------------------- saved values
    @staticmethod
    def key(text):
        key = re.sub(r"[^a-z0-9_]", "", (text or "").lower())[:30]
        if not key:
            raise StepFailed("a saved value needs a name with letters or numbers")
        return key

    async def do_set_var(self, s):
        key = self.key(s["name"])
        if key not in self.values and len(self.values) >= 100:
            raise StepFailed("a server can keep 100 saved values")
        self.values[key] = self.fmt(s["value"])[:500]
        self.touched_values = True

    async def do_add_counter(self, s):
        key = self.key(s["name"])
        if key not in self.values and len(self.values) >= 100:
            raise StepFailed("a server can keep 100 saved values")
        try:
            current = int(self.values.get(key, 0))
        except ValueError:
            current = 0
        self.values[key] = str(max(-10**9, min(10**9, current + int(s["amount"]))))
        self.touched_values = True

    async def do_reset_var(self, s):
        self.values.pop(self.key(s["name"]), None)
        self.touched_values = True

    # ---------------------------------------------------------------- roles
    def why(self):
        return f"Custom command {self.name}, run by {self.author}"

    async def do_add_role(self, s):
        member, role = self.member(s), self.role(s)
        self.safe_role(role)
        if member != self.author:
            self.check_target(member)
        await member.add_roles(role, reason=self.why())

    async def do_remove_role(self, s):
        member, role = self.member(s), self.role(s)
        self.safe_role(role)
        if member != self.author:
            self.check_target(member)
        await member.remove_roles(role, reason=self.why())

    async def do_toggle_role(self, s):
        member, role = self.member(s), self.role(s)
        self.safe_role(role)
        if member != self.author:
            self.check_target(member)
        if role in member.roles:
            await member.remove_roles(role, reason=self.why())
        else:
            await member.add_roles(role, reason=self.why())

    def count_create(self):
        self.creates += 1
        if self.creates > MAX_CREATES:
            raise StepFailed(f"a command can create up to {MAX_CREATES} things per run")
        if len(self.guild.roles) >= 240 or len(self.guild.channels) >= 480:
            raise StepFailed("the server is close to Discord's limit")

    async def do_create_role(self, s):
        self.count_create()
        name = self.fmt(s["name"], True)[:100]
        if not name.strip():
            raise StepFailed("the role needs a name")
        role = await self.guild.create_role(name=name, colour=hex_colour(self.fmt(s["color"])) or discord.Color.default(), hoist=bool(s["hoist"]), mentionable=bool(s["mentionable"]), reason=self.why())
        self.extra["_role"], self.extra["created_role"] = role, role.mention
        self.log.append(f"created role @{role.name}")
        if s["give"] in ("user", "target"):
            member = self.author if s["give"] == "user" else self.target
            if member is None:
                raise StepFailed("mention a member to give the new role to")
            if member != self.author:
                self.check_target(member)
            await member.add_roles(role, reason=self.why())

    async def do_delete_role(self, s):
        role = self.role(s)
        self.safe_role(role)
        self.log.append(f"deleted role @{role.name}")
        await role.delete(reason=self.why())

    async def do_rename_role(self, s):
        role = self.role(s)
        self.safe_role(role)
        name = self.fmt(s["name"], True)[:100]
        if not name.strip():
            raise StepFailed("give the role a name")
        self.log.append(f"renamed role @{role.name} to {name}")
        await role.edit(name=name, reason=self.why())

    async def do_role_color(self, s):
        role = self.role(s)
        self.safe_role(role)
        colour = hex_colour(self.fmt(s["color"]))
        if colour is None:
            raise StepFailed("the color must look like #5865f2")
        await role.edit(colour=colour, reason=self.why())

    # ---------------------------------------------------------------- channels
    def everyone(self):
        return self.guild.default_role

    async def do_create_channel(self, s):
        self.count_create()
        name = self.fmt(s["name"], True)[:100]
        if not name.strip():
            raise StepFailed("the channel needs a name")
        category = None
        if s.get("category"):
            category = self.guild.get_channel(int(s["category"])) if s["category"].isdigit() else self.extra.get("_channel") if s["category"] == "created" else None
            if not isinstance(category, discord.CategoryChannel):
                raise StepFailed("the category isn't there any more")
        overwrites = {}
        if s["private"]:
            overwrites = {self.everyone(): discord.PermissionOverwrite(view_channel=False), self.author: discord.PermissionOverwrite(view_channel=True, send_messages=True), self.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)}
            if self.target is not None:
                overwrites[self.target] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        common = {"reason": self.why(), "overwrites": overwrites} if overwrites else {"reason": self.why()}
        kind = s["ctype"]
        topic = self.fmt(s["topic"], True)[:1000] or None
        if kind == "voice":
            channel = await self.guild.create_voice_channel(name, category=category, **common)
        elif kind == "category":
            channel = await self.guild.create_category(name, **common)
        elif kind == "forum":
            channel = await self.guild.create_forum(name, category=category, topic=topic, **common)
        elif kind == "stage":
            channel = await self.guild.create_stage_channel(name, category=category, **common)
        else:
            channel = await self.guild.create_text_channel(name, category=category, topic=topic, news=(kind == "announcement"), **common)
        self.extra["_channel"], self.extra["created_channel"] = channel, channel.mention
        self.log.append(f"created {kind} channel #{channel.name}")

    async def do_delete_channel(self, s):
        channel = self.channel_of(s)
        self.log.append(f"deleted channel #{channel.name}")
        await channel.delete(reason=self.why())

    async def do_rename_channel(self, s):
        channel = self.channel_of(s)
        name = self.fmt(s["name"], True)[:100]
        if not name.strip():
            raise StepFailed("give the channel a name")
        self.log.append(f"renamed #{channel.name} to {name}")
        await channel.edit(name=name, reason=self.why())

    async def do_set_topic(self, s):
        channel = self.channel_of(s)
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            raise StepFailed("only text channels have a topic")
        await channel.edit(topic=self.fmt(s["text"], True)[:1000], reason=self.why())

    async def do_slowmode(self, s):
        channel = self.channel_of(s)
        if not isinstance(channel, discord.TextChannel):
            raise StepFailed("slowmode is for text channels")
        await channel.edit(slowmode_delay=int(s["seconds"]), reason=self.why())

    async def set_overwrite(self, channel, **perms):
        overwrite = channel.overwrites_for(self.everyone())
        overwrite.update(**perms)
        await channel.set_permissions(self.everyone(), overwrite=overwrite, reason=self.why())

    async def do_lock_channel(self, s):
        channel = self.channel_of(s)
        await self.set_overwrite(channel, send_messages=False)
        self.log.append(f"locked #{channel.name}")

    async def do_unlock_channel(self, s):
        channel = self.channel_of(s)
        await self.set_overwrite(channel, send_messages=None)
        self.log.append(f"unlocked #{channel.name}")

    async def do_hide_channel(self, s):
        channel = self.channel_of(s)
        await self.set_overwrite(channel, view_channel=False)
        self.log.append(f"hid #{channel.name}")

    async def do_show_channel(self, s):
        channel = self.channel_of(s)
        await self.set_overwrite(channel, view_channel=None)
        self.log.append(f"showed #{channel.name}")

    async def do_clone_channel(self, s):
        self.count_create()
        channel = self.channel_of(s)
        name = self.fmt(s["name"], True)[:100] or None
        copy = await channel.clone(name=name, reason=self.why())
        self.extra["_channel"], self.extra["created_channel"] = copy, copy.mention
        self.log.append(f"copied #{channel.name} to #{copy.name}")

    async def do_voice_limit(self, s):
        channel = self.channel_of(s)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            raise StepFailed("that isn't a voice channel")
        await channel.edit(user_limit=int(s["limit"]), reason=self.why())

    async def do_create_invite(self, s):
        channel = self.channel_of(s)
        if not hasattr(channel, "create_invite"):
            raise StepFailed("can't make an invite for that channel")
        invite = await channel.create_invite(max_age=int(s["hours"]) * 3600, max_uses=int(s["uses"]), unique=True, reason=self.why())
        self.extra["invite"] = invite.url

    async def do_purge(self, s):
        channel = self.channel_of(s)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            raise StepFailed("that channel can't be cleared")
        deleted = await channel.purge(limit=int(s["count"]) + (1 if channel.id == self.channel.id else 0), reason=self.why())
        self.log.append(f"deleted {len(deleted)} messages in #{channel.name}")

    # ---------------------------------------------------------------- members
    async def do_nickname(self, s):
        member = self.member(s)
        self.check_target(member)
        text = self.fmt(s["text"], True)[:32].strip()
        await member.edit(nick=text or None, reason=self.why())

    async def do_timeout(self, s):
        member = self.member(s)
        self.check_target(member)
        await member.timeout(timedelta(minutes=int(s["minutes"])), reason=self.fmt(s["reason"], True)[:200] or self.why())
        self.log.append(f"timed out {member} for {s['minutes']} minutes")

    async def do_untimeout(self, s):
        member = self.member(s)
        self.check_target(member)
        await member.timeout(None, reason=self.why())

    async def do_kick(self, s):
        member = self.member(s)
        self.check_target(member)
        self.log.append(f"kicked {member}")
        await member.kick(reason=self.fmt(s["reason"], True)[:200] or self.why())

    async def do_ban(self, s):
        member = self.member(s)
        self.check_target(member)
        self.log.append(f"banned {member}")
        await member.ban(reason=self.fmt(s["reason"], True)[:200] or self.why(), delete_message_days=int(s["days"]))

    async def do_move_voice(self, s):
        member = self.member(s)
        self.check_target(member)
        channel = self.channel_of(s)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            raise StepFailed("that isn't a voice channel")
        if member.voice is None:
            raise StepFailed(f"{member.display_name} isn't in a voice channel")
        await member.move_to(channel, reason=self.why())

    async def do_disconnect_voice(self, s):
        member = self.member(s)
        self.check_target(member)
        if member.voice is None:
            raise StepFailed(f"{member.display_name} isn't in a voice channel")
        await member.move_to(None, reason=self.why())

    async def do_add_xp(self, s):
        member = self.member(s)
        levels = self.bot.get_cog("Levels")
        if levels is None:
            raise StepFailed("levels aren't loaded")
        entry = levels.entry(self.guild.id, member.id)
        entry["xp"] = max(0, entry["xp"] + int(s["amount"]))
        levels.store.save()
        self.log.append(f"changed {member}'s XP by {s['amount']}")
