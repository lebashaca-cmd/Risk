"""Custom commands as text: plain lines are what Risk says, `(action ...)` lines make it do things, `{variable}` fills in values.

    Welcome {user}! Pick a room name after the command.
    (createchannel "{arg1}-room" type=voice private=yes)
    (addrole Member)
    (reply Done, {created.channel} is ready.)

`compile_script` turns that text into the step list utils/ccactions.py runs; `decompile` writes steps back as text, using
the current role and channel names, so what you see in the editor always matches the server.
"""
import re

from utils import ccactions

ALIASES = {"role": "add_role", "giverole": "add_role", "takerole": "remove_role", "say": "send", "announce": "send", "ban": "ban", "delete": "delete_trigger",
           "rolecolor": "role_color", "newrole": "create_role", "newchannel": "create_channel", "mute": "timeout", "unmute": "untimeout", "stop": "stop_chance",
           "var": "set_var", "counter": "add_counter", "invite": "create_invite", "clear": "purge", "xp": "add_xp", "lock": "lock_channel", "unlock": "unlock_channel",
           "hide": "hide_channel", "show": "show_channel", "topic": "set_topic", "pause": "wait", "sleep": "wait", "embed": "embed", "dm": "dm"}
KEY_ALIASES = {"type": "ctype", "kind": "ctype", "message": "text", "msg": "text", "content": "text", "min": "minutes", "sec": "seconds", "secs": "seconds", "colour": "color"}
YES = ("yes", "true", "on", "1")


class ScriptError(Exception):
    pass


def alias_of(kind):
    return kind.replace("_", "")


NAMES = {alias_of(k): k for k in ccactions.ACTIONS}
NAMES.update(ALIASES)


def positional(kind):
    """The settings a bare value can fill, in order. Dropdown and on/off settings always need name=value."""
    return [f for f in ccactions.ACTIONS[kind][3] if f["kind"] not in ("select", "bool")]


def tokens(text):
    """Splits an action's arguments on spaces, keeping "quoted text" and {variables with spaces} whole."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        start, buf, quoted = i, "", text[i] == '"'
        while i < n and (not text[i].isspace() or depth_open(text, start, i)):
            ch = text[i]
            if ch == '"':
                i += 1
                while i < n and text[i] != '"':
                    if text[i] == "\\" and i + 1 < n:
                        nxt = text[i + 1]
                        buf += {"n": "\n", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt)
                        i += 2
                    else:
                        buf += text[i]
                        i += 1
                if i >= n:
                    raise ScriptError("a quote isn't closed")
                i += 1
                continue
            buf += ch
            i += 1
        out.append((buf, quoted))
    return out


def depth_open(text, start, i):
    """True while the cursor is inside an unclosed {variable}, so spaces in {choose:a b|c} don't split the word."""
    seg = text[start:i]
    return seg.count("{") > seg.count("}")


def find_role(guild, text):
    text = text.strip()
    if text.lower() == "created":
        return "created"
    match = re.fullmatch(r"<@&(\d+)>|(\d{15,25})", text)
    if match:
        found = guild.get_role(int(match.group(1) or match.group(2)))
        if found is None:
            raise ScriptError(f"there's no role with the id {text}")
        return str(found.id)
    name = text.lstrip("@").strip().lower()
    for role in guild.roles:
        if not role.is_default() and role.name.lower() == name:
            return str(role.id)
    raise ScriptError(f"I can't find a role called \"{text}\"")


def find_channel(guild, text, kinds):
    text = text.strip()
    if text.lower() in ("created", "current"):
        return text.lower()
    if text.lower() in ("here", "this", ""):
        return ""
    match = re.fullmatch(r"<#(\d+)>|(\d{15,25})", text)
    if match:
        found = guild.get_channel(int(match.group(1) or match.group(2)))
        if found is None:
            raise ScriptError(f"there's no channel with the id {text}")
        return str(found.id)
    name = text.lstrip("#").strip().lower()
    for channel in guild.channels:
        if channel.name.lower() == name:
            return str(channel.id)
    raise ScriptError(f"I can't find a channel called \"{text}\"")


def convert(guild, kind, f, raw):
    if f["kind"] == "role":
        return find_role(guild, raw)
    if f["kind"] == "channel":
        return find_channel(guild, raw, f.get("kinds"))
    if f["kind"] == "bool":
        return raw.lower() in YES
    if f["kind"] == "number":
        try:
            return int(raw.strip())
        except ValueError:
            raise ScriptError(f"\"{raw}\" isn't a whole number for {f['key']}")
    if f["kind"] == "select":
        value = raw.strip().lower()
        for key, label in f["options"].items():
            if value in (key, label.lower()):
                return key
        raise ScriptError(f"{f['key']} must be one of: " + ", ".join(f["options"]))
    return raw


def parse_action(guild, body):
    parts = body.strip().split(None, 1)
    if not parts:
        raise ScriptError("an empty ( ) isn't an action")
    name = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    kind = NAMES.get(name)
    if kind is None:
        raise ScriptError(f"I don't know the action ({name}). Type ( to see the list")
    fields = {f["key"]: f for f in ccactions.ACTIONS[kind][3]}
    step = {"type": kind}
    free = positional(kind)
    named_form = re.search(r'(?:^|\s)\w+=', rest) is not None
    if rest.strip() and not named_form and len(free) == 1:
        # one bare setting: everything after the name belongs to it, quotes optional
        value = rest.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        step[free[0]["key"]] = convert(guild, kind, free[0], value)
        return step
    index = 0
    for word, quoted in tokens(rest):
        match = re.fullmatch(r"(\w+)=(.*)", word, re.S) if not quoted else None
        if match:
            key = KEY_ALIASES.get(match.group(1).lower(), match.group(1).lower())
            if key not in fields:
                raise ScriptError(f"({name}) has no setting called {match.group(1)}. Its settings: " + ", ".join(fields))
            step[key] = convert(guild, kind, fields[key], match.group(2))
        else:
            if index >= len(free):
                raise ScriptError(f"({name}) got an extra value \"{word[:30]}\". Use name=value for settings, and quotes around text with spaces")
            f = free[index]
            index += 1
            step[f["key"]] = convert(guild, kind, f, word)
    return step


def compile_script(script, guild):
    """Text to steps. Raises ScriptError with the line number when something doesn't make sense."""
    steps, text_lines = [], []

    def flush():
        while text_lines and not text_lines[-1].strip():
            text_lines.pop()
        if text_lines:
            steps.append({"type": "reply", "text": "\n".join(text_lines)})
        text_lines.clear()

    for number, line in enumerate(script.replace("\r\n", "\n").split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("(") and stripped.endswith(")"):
            flush()
            try:
                steps.append(parse_action(guild, stripped[1:-1]))
            except ScriptError as error:
                raise ScriptError(f"Line {number}: {error}.")
            continue
        if stripped.startswith("(") and not stripped.startswith("(("):
            raise ScriptError(f"Line {number}: an action must end with ) on the same line. To start a message with ( put a backslash before it.")
        if stripped.startswith("\\("):
            line = line.replace("\\(", "(", 1)
        if text_lines or stripped:
            text_lines.append(line)
    flush()
    return steps


def quote(value):
    value = str(value)
    if value and re.fullmatch(r"[^\s\"(){}=]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def role_name(guild, value):
    if value in ("created", ""):
        return value
    role = guild.get_role(int(value)) if str(value).isdigit() else None
    return role.name if role else str(value)


def channel_name(guild, value):
    if value in ("created", "current", ""):
        return value
    channel = guild.get_channel(int(value)) if str(value).isdigit() else None
    return channel.name if channel else str(value)


def decompile(steps, guild):
    """Steps back to text. Only settings that differ from the defaults are written."""
    lines = []
    for step in steps:
        kind = step.get("type")
        if kind == "reply":
            for line in str(step.get("text", "")).split("\n"):
                lines.append("\\" + line if line.lstrip().startswith("(") else line)
            continue
        if kind not in ccactions.ACTIONS:
            continue
        fields = ccactions.ACTIONS[kind][3]
        free = positional(kind)
        shown = []
        for f in fields:
            value = step.get(f["key"], f.get("default", ""))
            if f["kind"] == "bool":
                if value:
                    shown.append((f, "yes"))
                continue
            if f["kind"] == "role":
                value = role_name(guild, value)
            elif f["kind"] == "channel":
                value = channel_name(guild, value)
            if value in ("", None) or (f.get("default") is not None and value == f["default"] and f["kind"] != "number"):
                continue
            if f["kind"] == "number" and value == f.get("default"):
                continue
            shown.append((f, value))
        if len(free) == 1 and shown and shown[0][0] is free[0] and len(shown) == 1:
            value = str(shown[0][1])
            lines.append(f"({alias_of(kind)} {value})" if "\n" not in value and ")" not in value else f"({alias_of(kind)} {free[0]['key']}={quote(value)})")
            continue
        args = " ".join(f"{f['key']}={quote(v)}" if f["kind"] in ("select", "number") or f not in free or i >= 0 else quote(v) for i, (f, v) in enumerate(shown))
        lines.append(f"({alias_of(kind)}{' ' + args if args else ''})")
    return "\n".join(lines)


def usage(kind):
    """A one-line example of an action for the editor's list and `!customcmd actions`."""
    fields = ccactions.ACTIONS[kind][3]
    free = positional(kind)
    if len(free) == 1:
        parts = [f"<{free[0]['label'].split(' (')[0].lower()}>"] + [f"{f['key']}={'|'.join(f['options']) if f['kind'] == 'select' else 'yes' if f['kind'] == 'bool' else '...'}" for f in fields if f not in free and f['kind'] in ('select', 'bool')]
    else:
        parts = [f"{f['key']}={'|'.join(f['options']) if f['kind'] == 'select' else 'yes' if f['kind'] == 'bool' else '...'}" for f in fields]
    return f"({alias_of(kind)}{' ' + ' '.join(parts) if parts else ''})"
