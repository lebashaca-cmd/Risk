"""The staff panel's brain.

Who gets in is decided here, never by the website. A person has a panel role only if they are:
  - the bot's owner (the Discord application's owner or team, or a user id in OWNER_IDS), or
  - a member of the bot's own staff server (STAFF_GUILD_ID) who holds a panel role. A panel role comes from
    a Discord role listed in STAFF_ROLE_IDS or DEV_ROLE_IDS, or from an assignment made in the panel itself.

Servers that merely have Risk installed never count: they don't appear in the staff server's member list.

Panel roles: staff (sees the totals), developer and owner (the owner panel: prices, server bans, VIP, roles).
"""
import os
import re
import time

import discord
from discord.ext import commands

from utils.store import JsonStore

LEVELS = {"staff": 1, "developer": 2, "owner": 3}
PLANS = ("basic", "lifetime", "white", "supreme")
SNOWFLAKE = re.compile(r"\d{15,21}")
LOG_LIMIT = 100
SERVER_LIST_LIMIT = 1000


class StaffError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def env_ids(name):
    out = set()
    for part in re.split(r"[,\s]+", os.getenv(name, "")):
        if SNOWFLAKE.fullmatch(part):
            out.add(int(part))
    return out


def snowflake(value, what):
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not SNOWFLAKE.fullmatch(value.strip()):
        raise StaffError(400, f"{what} isn't valid.")
    return int(value.strip())


class Staff(commands.Cog, name="Staff"):
    """The staff and owner panel on the website."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("staff")
        for key, empty in (("roles", {}), ("banned", {}), ("prices", {}), ("log", [])):
            self.store.data.setdefault(key, empty)

    # ------------------------------------------------------------------ who is who
    @property
    def staff_guild(self):
        ids = env_ids("STAFF_GUILD_ID")
        return self.bot.get_guild(next(iter(ids))) if ids else None

    async def is_owner(self, user_id):
        if user_id in env_ids("OWNER_IDS"):
            return True
        try:
            return await self.bot.is_owner(discord.Object(id=user_id))
        except Exception:
            return False

    async def staff_member(self, user_id):
        guild = self.staff_guild
        if guild is None:
            return None
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return None
        return member

    async def role_of(self, user_id):
        """'owner', 'developer', 'staff' or None."""
        if await self.is_owner(user_id):
            return "owner"
        member = await self.staff_member(user_id)
        if member is None or member.bot:
            return None
        best = self.store.data["roles"].get(str(user_id))
        best = best if best in LEVELS else None
        have = {r.id for r in getattr(member, "roles", [])}
        if have & env_ids("DEV_ROLE_IDS") and LEVELS["developer"] > LEVELS.get(best, 0):
            best = "developer"
        if have & env_ids("STAFF_ROLE_IDS") and LEVELS["staff"] > LEVELS.get(best, 0):
            best = "staff"
        return best

    async def require(self, user_id, minimum="staff"):
        role = await self.role_of(user_id)
        if role is None:
            raise StaffError(403, "You're not on the staff team.")
        if LEVELS[role] < LEVELS[minimum]:
            raise StaffError(403, f"That needs the {minimum} role or higher.")
        return role

    def note(self, user_id, action, detail=""):
        log = self.store.data["log"]
        log.append({"at": int(time.time()), "by": str(user_id), "action": action, "detail": str(detail)[:200]})
        del log[:-LOG_LIMIT]
        self.store.save()

    # ------------------------------------------------------------------ reading
    def totals(self):
        vip = self.bot.get_cog("VIP")
        guilds = list(self.bot.guilds)
        return {
            "servers": len(guilds),
            "members": sum(g.member_count or 0 for g in guilds),
            "vip": sum(1 for g in guilds if vip and vip.info(g.id)["vip"]),
            "banned": len(self.store.data["banned"]),
        }

    async def me(self, user_id):
        role = await self.role_of(user_id)
        return {"role": role, "owner": role is not None and LEVELS[role] >= LEVELS["developer"], "staffServer": self.staff_guild is not None}

    async def overview(self, user_id):
        role = await self.require(user_id, "staff")
        return {"role": role, "owner": LEVELS[role] >= LEVELS["developer"], **self.totals()}

    def public_prices(self):
        """The saved price and checkout link per plan. Missing plans fall back to the site's own settings."""
        out = {}
        for plan, entry in self.store.data["prices"].items():
            if plan in PLANS and isinstance(entry, dict):
                out[plan] = {"price": entry.get("price") or None, "url": entry.get("url") or None}
        return out

    async def owner_panel(self, user_id):
        role = await self.require(user_id, "developer")
        vip = self.bot.get_cog("VIP")
        banned = self.store.data["banned"]
        servers = []
        for guild in sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)[:SERVER_LIST_LIMIT]:
            info = vip.info(guild.id) if vip else {"vip": False, "tier": None, "until": None, "source": None}
            servers.append({
                "id": str(guild.id), "name": guild.name[:100], "members": guild.member_count or 0,
                "vip": info["vip"], "tier": vip.tier_name(guild.id) if vip and info["vip"] else None,
                "until": info["until"], "source": info["source"],
            })
        roles = []
        for uid, panel_role in self.store.data["roles"].items():
            member = self.staff_guild.get_member(int(uid)) if self.staff_guild else None
            roles.append({"id": uid, "role": panel_role, "name": member.display_name if member else None})
        return {
            "role": role, "canAssignOwner": role == "owner", **self.totals(),
            "serverList": servers,
            "bannedList": [{"id": gid, **{k: v for k, v in entry.items() if k in ("name", "reason", "by", "at")}} for gid, entry in banned.items()],
            "prices": self.public_prices(), "plans": list(PLANS),
            "roles": roles, "log": list(reversed(self.store.data["log"]))[:50],
        }

    # ------------------------------------------------------------------ owner actions
    async def set_prices(self, user_id, body):
        await self.require(user_id, "developer")
        if not isinstance(body, dict):
            raise StaffError(400, "Send the prices as an object.")
        pending = {}
        for plan, entry in body.items():
            if plan not in PLANS:
                raise StaffError(400, f"Unknown plan: {str(plan)[:30]}.")
            if not isinstance(entry, dict):
                raise StaffError(400, f"The {plan} plan needs a price and a link.")
            price = str(entry.get("price", "") or "").strip()
            url = str(entry.get("url", "") or "").strip()
            if len(price) > 20:
                raise StaffError(400, f"The {plan} price must be 20 characters or fewer.")
            if url and (not url.startswith("https://") or len(url) > 500 or any(c.isspace() for c in url)):
                raise StaffError(400, f"The {plan} link must start with https:// and have no spaces.")
            pending[plan] = {"price": price, "url": url}
        # Nothing is saved unless every plan passed, so a typo can't leave the prices half changed.
        self.store.data["prices"].update(pending)
        self.store.save()
        self.note(user_id, "prices", ", ".join(pending))
        return {"prices": self.public_prices()}

    async def set_vip(self, user_id, body):
        await self.require(user_id, "developer")
        vip = self.bot.get_cog("VIP")
        if vip is None:
            raise StaffError(503, "VIP isn't loaded on the bot right now.")
        guild_id = snowflake(body.get("guild_id"), "Server id")
        action = body.get("action")
        if action == "grant":
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                raise StaffError(404, "Risk isn't in that server.")
            if str(guild_id) in self.store.data["banned"]:
                raise StaffError(400, "That server is banned. Unban it first.")
            days = body.get("days", 0)
            if isinstance(days, bool) or not isinstance(days, int) or not 0 <= days <= 3650:
                raise StaffError(400, "Days must be a whole number from 0 to 3650 (0 means no end).")
            tier = body.get("tier") or "basic"
            if tier not in PLANS:
                raise StaffError(400, "Pick one of: " + ", ".join(PLANS) + ".")
            vip.grant(guild_id, days, tier, str(body.get("note", ""))[:100])
            self.note(user_id, "vip grant", f"{guild.name} ({guild_id}) {tier} {'no end' if not days else f'{days} days'}")
        elif action == "revoke":
            if not vip.revoke(guild_id):
                raise StaffError(404, "That server has no granted VIP to take away.")
            self.note(user_id, "vip revoke", str(guild_id))
        else:
            raise StaffError(400, "Action must be grant or revoke.")
        info = vip.info(guild_id)
        return {"id": str(guild_id), "vip": info["vip"], "tier": vip.tier_name(guild_id) if info["vip"] else None, "until": info["until"]}

    async def ban_server(self, user_id, body):
        await self.require(user_id, "developer")
        guild_id = snowflake(body.get("guild_id"), "Server id")
        reason = str(body.get("reason", "") or "").strip()[:200]
        staff = self.staff_guild
        if staff is not None and staff.id == guild_id:
            raise StaffError(400, "That's the staff server. It can't be banned.")
        guild = self.bot.get_guild(guild_id)
        self.store.data["banned"][str(guild_id)] = {"name": guild.name[:100] if guild else None, "reason": reason, "by": str(user_id), "at": int(time.time())}
        self.store.save()
        vip = self.bot.get_cog("VIP")
        if vip is not None:
            vip.revoke(guild_id)
        left = False
        if guild is not None:
            try:
                await guild.leave()
                left = True
            except discord.HTTPException:
                pass
        self.note(user_id, "server ban", f"{guild.name if guild else 'unknown'} ({guild_id}) {reason}".strip())
        return {"id": str(guild_id), "left": left, "banned": len(self.store.data["banned"])}

    async def unban_server(self, user_id, body):
        await self.require(user_id, "developer")
        guild_id = snowflake(body.get("guild_id"), "Server id")
        if self.store.data["banned"].pop(str(guild_id), None) is None:
            raise StaffError(404, "That server isn't banned.")
        self.store.save()
        self.note(user_id, "server unban", str(guild_id))
        return {"id": str(guild_id), "banned": len(self.store.data["banned"])}

    async def assign_role(self, user_id, body):
        mine = await self.require(user_id, "developer")
        target = snowflake(body.get("user_id"), "User id")
        wanted = body.get("role")
        if wanted not in (*LEVELS, "none"):
            raise StaffError(400, "Role must be staff, developer, owner or none.")
        if await self.is_owner(target):
            raise StaffError(400, "That person is a bot owner. Their access can't be changed here.")
        current = self.store.data["roles"].get(str(target))
        # Owners can set anything. Developers can only add or remove staff.
        if mine != "owner" and (wanted not in ("staff", "none") or current in ("developer", "owner")):
            raise StaffError(403, "Developers can only add or remove staff. Ask an owner for the rest.")
        if wanted != "none":
            member = await self.staff_member(target)
            if member is None or member.bot:
                raise StaffError(400, "That person isn't a member of the staff server.")
        if wanted == "none":
            if self.store.data["roles"].pop(str(target), None) is None:
                raise StaffError(404, "That person has no assigned role.")
        else:
            self.store.data["roles"][str(target)] = wanted
        self.store.save()
        self.note(user_id, "role", f"{target} -> {wanted}")
        return {"id": str(target), "role": None if wanted == "none" else wanted}

    # ------------------------------------------------------------------ keeping banned servers out
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if str(guild.id) in self.store.data["banned"]:
            try:
                await guild.leave()
            except discord.HTTPException:
                pass

    async def cog_load(self):
        # Cogs load once the bot is ready, so sweep here for servers banned while the bot was offline.
        await self.sweep()

    async def sweep(self):
        for guild in list(self.bot.guilds):
            if str(guild.id) in self.store.data["banned"]:
                try:
                    await guild.leave()
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(Staff(bot))
