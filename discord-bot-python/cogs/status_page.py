"""What the website's status page shows: buttons the owner chooses, a notice, incidents, usage and uptime.

The owner edits it from the control panel app or the website's staff panel. The website reads `public()` through
the bot's /dash/status-page route. Nothing private is in it: counts, command names and the owner's own text.

Uptime is kept as 48 half-hour slots per day. Every five minutes the bot marks the current slot as up, so a
slot with no mark means the bot was down for that half hour. Days before the bot first ran show as no data.
"""
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from utils.store import JsonStore

SLOTS = 48
KEEP_DAYS = 90
SHOW_DAYS = 30
MAX_BUTTONS = 8
MAX_INCIDENTS = 30
LEVELS = ("info", "good", "warn", "bad")
STYLES = ("primary", "quiet")
TOKEN_URL = re.compile(r"\{(invite|site|docs|dashboard|vip|status)\}(/[^\s]*)?")
DEFAULT_BUTTONS = [
    {"label": "Add to server", "url": "{invite}", "style": "primary"},
    {"label": "Website", "url": "{site}", "style": "quiet"},
    {"label": "Docs", "url": "{docs}", "style": "quiet"},
]
USER_ERRORS = (commands.CommandNotFound, commands.UserInputError, commands.CheckFailure, commands.CommandOnCooldown, commands.DisabledCommand)


class PageError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def today(now=None):
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")


def valid_url(url):
    if not isinstance(url, str) or len(url) > 500 or any(c.isspace() for c in url):
        return False
    return url.startswith("https://") or (url.startswith("/") and not url.startswith("//")) or bool(TOKEN_URL.fullmatch(url))


class StatusPage(commands.Cog, name="StatusPage"):
    """Data behind the website's status page."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("status_page")
        for key, empty in (("buttons", None), ("notice", {"on": False, "level": "info", "text": ""}), ("incidents", []), ("usage", {"days": {}, "commands": {}, "total": 0}), ("slots", {}), ("first_seen", int(time.time()))):
            self.store.data.setdefault(key, empty)
        self.started = time.time()
        self.dirty = False

    async def cog_load(self):
        self.tick.start()

    async def cog_unload(self):
        self.tick.cancel()
        self.store.save()

    # ------------------------------------------------------------------ counting
    def bump(self, field, name=None):
        usage = self.store.data["usage"]
        day = usage["days"].setdefault(today(), {"commands": 0, "errors": 0})
        day[field] += 1
        if field == "commands":
            usage["total"] += 1
            if name:
                counts = usage["commands"]
                counts[name] = counts.get(name, 0) + 1
                if len(counts) > 600:
                    for key in sorted(counts, key=counts.get)[:100]:
                        del counts[key]
        self.dirty = True

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        self.bump("commands", (ctx.command.root_parent or ctx.command).name if ctx.command else None)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if not isinstance(error, USER_ERRORS) and getattr(ctx, "command", None) is not None:
            self.bump("errors")

    @tasks.loop(minutes=5)
    async def tick(self):
        now = datetime.now(timezone.utc)
        slot = now.hour * 2 + (1 if now.minute >= 30 else 0)
        slots = self.store.data["slots"]
        slots[today(now)] = slots.get(today(now), 0) | (1 << slot)
        cutoff = today(now - timedelta(days=KEEP_DAYS))
        for table in (slots, self.store.data["usage"]["days"]):
            for day in [d for d in table if d < cutoff]:
                del table[day]
        self.store.save()
        self.dirty = False

    @tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ reading
    def buttons(self):
        return self.store.data["buttons"] if self.store.data["buttons"] is not None else [dict(b) for b in DEFAULT_BUTTONS]

    def uptime(self):
        now = datetime.now(timezone.utc)
        first = datetime.fromtimestamp(self.store.data["first_seen"], timezone.utc)
        days = []
        up_total = seen_total = 0
        for back in range(SHOW_DAYS - 1, -1, -1):
            moment = now - timedelta(days=back)
            day = today(moment)
            if day < today(first):
                days.append({"date": day, "percent": None})
                continue
            mask = self.store.data["slots"].get(day, 0)
            start = first.hour * 2 + (1 if first.minute >= 30 else 0) if day == today(first) else 0
            end = (now.hour * 2 + (1 if now.minute >= 30 else 0)) if day == today(now) else SLOTS - 1
            possible = max(1, end - start + 1)
            up = sum(1 for s in range(start, end + 1) if mask >> s & 1)
            days.append({"date": day, "percent": round(100 * min(up, possible) / possible, 1)})
            up_total += min(up, possible)
            seen_total += possible
        return {"days": days, "percent": round(100 * up_total / seen_total, 2) if seen_total else None}

    def usage(self):
        usage = self.store.data["usage"]
        now = datetime.now(timezone.utc)
        week = sum(usage["days"].get(today(now - timedelta(days=i)), {}).get("commands", 0) for i in range(7))
        day = usage["days"].get(today(now), {"commands": 0, "errors": 0})
        top = sorted(usage["commands"].items(), key=lambda kv: kv[1], reverse=True)[:8]
        return {"today": day["commands"], "week": week, "total": usage["total"], "errorsToday": day["errors"], "top": [{"name": n, "count": c} for n, c in top]}

    def public(self):
        data = self.store.data
        incidents = sorted(data["incidents"], key=lambda i: i["at"], reverse=True)[:10]
        return {
            "buttons": self.buttons(), "notice": dict(data["notice"]), "incidents": incidents,
            "usage": self.usage(), "uptime": self.uptime(), "sinceSeconds": int(time.time() - self.started),
        }

    def editable(self):
        """Everything the panels edit, including the full incident list."""
        out = self.public()
        out["incidents"] = sorted(self.store.data["incidents"], key=lambda i: i["at"], reverse=True)
        out["customButtons"] = self.store.data["buttons"] is not None
        out["defaults"] = [dict(b) for b in DEFAULT_BUTTONS]
        return out

    # ------------------------------------------------------------------ changing
    def set_buttons(self, items):
        if items is None:
            self.store.data["buttons"] = None
        else:
            if not isinstance(items, list) or len(items) > MAX_BUTTONS:
                raise PageError(400, f"Send a list of up to {MAX_BUTTONS} buttons.")
            clean = []
            for item in items:
                if not isinstance(item, dict):
                    raise PageError(400, "Each button needs a label and a link.")
                label = str(item.get("label", "")).strip()
                url = str(item.get("url", "")).strip()
                style = item.get("style", "quiet")
                if not 1 <= len(label) <= 30:
                    raise PageError(400, "A button label must be 1 to 30 characters.")
                if not valid_url(url):
                    raise PageError(400, f"The link for {label} must start with https://, or be a path like /vip, or be one of {{invite}}, {{site}}, {{docs}}, {{dashboard}}, {{vip}}, {{status}}.")
                if style not in STYLES:
                    raise PageError(400, "Style must be primary or quiet.")
                clean.append({"label": label, "url": url, "style": style})
            self.store.data["buttons"] = clean
        self.store.save()
        return self.buttons()

    def set_notice(self, body):
        level = body.get("level", "info")
        text = str(body.get("text", "")).strip()[:300]
        if level not in LEVELS:
            raise PageError(400, "Level must be info, good, warn or bad.")
        self.store.data["notice"] = {"on": body.get("on") is True and bool(text), "level": level, "text": text}
        self.store.save()
        return dict(self.store.data["notice"])

    def add_incident(self, body):
        title = str(body.get("title", "")).strip()[:80]
        text = str(body.get("text", "")).strip()[:500]
        level = body.get("level", "warn")
        if not title:
            raise PageError(400, "Give the incident a title.")
        if level not in LEVELS:
            raise PageError(400, "Level must be info, good, warn or bad.")
        incident = {"id": secrets.token_hex(4), "title": title, "text": text, "level": level, "at": int(time.time()), "resolved_at": None}
        incidents = self.store.data["incidents"]
        incidents.append(incident)
        del incidents[:-MAX_INCIDENTS]
        self.store.save()
        return incident

    def resolve_incident(self, incident_id, text=""):
        for incident in self.store.data["incidents"]:
            if incident["id"] == incident_id:
                incident["resolved_at"] = incident["resolved_at"] or int(time.time())
                if text:
                    incident["text"] = str(text).strip()[:500]
                self.store.save()
                return incident
        raise PageError(404, "No such incident.")

    def remove_incident(self, incident_id):
        before = len(self.store.data["incidents"])
        self.store.data["incidents"] = [i for i in self.store.data["incidents"] if i["id"] != incident_id]
        if len(self.store.data["incidents"]) == before:
            raise PageError(404, "No such incident.")
        self.store.save()
        return {"id": incident_id}


async def setup(bot):
    await bot.add_cog(StatusPage(bot))
