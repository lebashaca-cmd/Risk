import re
from datetime import timedelta

import discord
from discord.ext import commands

NO_MENTIONS = discord.AllowedMentions.none()

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_PART = re.compile(r"(\d+)\s*([smhdw])")


class ModError(commands.CommandError):
    pass


def parse_duration(text):
    text = (text or "").strip().lower()
    parts = _PART.findall(text)
    if not parts or _PART.sub("", text).strip():
        return None
    seconds = sum(int(n) * _UNITS[u] for n, u in parts)
    return timedelta(seconds=seconds) if seconds > 0 else None


def human_duration(value):
    seconds = int(value.total_seconds() if isinstance(value, timedelta) else value)
    out = []
    for label, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        amount, seconds = divmod(seconds, size)
        if amount:
            out.append(f"{amount}{label}")
    return " ".join(out) or "0s"


class Duration(commands.Converter):
    async def convert(self, ctx, argument):
        value = parse_duration(argument)
        if value is None:
            raise commands.BadArgument("Use a duration like `10m`, `2h` or `1d`.")
        return value


def parse_amount(text, available):
    text = text.strip().lower().replace(",", "")
    if text in ("all", "max"):
        return available
    if text == "half":
        return available // 2
    if text.isdigit():
        return int(text)
    return None


async def explain_error(ctx, error):
    error = getattr(error, "original", error) if isinstance(error, commands.CommandInvokeError) else error
    prefix = ctx.prefix or "!"
    name = ctx.command.qualified_name if ctx.command else ""

    if isinstance(error, ModError):
        message = str(error)
    elif isinstance(error, commands.MissingPermissions):
        needed = ", ".join(p.replace("_", " ").title() for p in error.missing_permissions)
        message = f"You need the **{needed}** permission to use this."
    elif isinstance(error, commands.BotMissingPermissions):
        needed = ", ".join(p.replace("_", " ").title() for p in error.missing_permissions)
        message = f"I need the **{needed}** permission to do that."
    elif isinstance(error, commands.MissingRequiredArgument):
        message = f"Missing `{error.param.name}`. Usage: `{prefix}{name} {ctx.command.signature}`"
    elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
        message = "I couldn't find that user."
    elif isinstance(error, commands.RoleNotFound):
        message = "I couldn't find that role."
    elif isinstance(error, commands.ChannelNotFound):
        message = "I couldn't find that channel."
    elif isinstance(error, (commands.BadArgument, commands.BadUnionArgument)):
        detail = str(error) if isinstance(error, commands.BadArgument) and "Converting to" not in str(error) else ""
        message = detail or f"That input isn't valid. Usage: `{prefix}{name} {ctx.command.signature}`"
    elif isinstance(error, commands.NoPrivateMessage):
        message = "This command only works in a server."
    elif isinstance(error, commands.CommandOnCooldown):
        message = f"Slow down, try again in {human_duration(error.retry_after + 0.5)}."
    elif isinstance(error, commands.NotOwner):
        message = "Only the bot owner can use this."
    elif isinstance(error, discord.Forbidden):
        message = "Discord says I don't have permission to do that. Check my role and its position."
    elif isinstance(error, discord.HTTPException):
        message = "Discord returned an error. Try again in a moment."
    elif isinstance(error, (commands.CheckFailure, commands.UserInputError)):
        message = "You can't use that here."
    else:
        return False

    try:
        await ctx.send(message, allowed_mentions=NO_MENTIONS)
    except discord.HTTPException:
        pass
    return True
