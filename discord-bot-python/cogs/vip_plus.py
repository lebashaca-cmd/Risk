"""More VIP commands, grouped by the plan that unlocks them.

Basic (every VIP plan): vipcolor, vippoll, vipsay, vipannounce, viprolecolor, servercard, topmessages, userreport, rolereport.
White (White and Supreme): customcmd, autoreact, welcomedm, embededit, stafflist.
Supreme: autodelete, slowmodeall, lockall, unlockall, serverbackup, membercounter, permaudit.
Lifetime: founder, motd.

Each command calls `VIP.need(ctx, group)`, so a server on a lower plan is told which plan it needs.
"""
import asyncio
import io
import json
import re
import time
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

NUMBERS = ["1\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}", "2\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
           "3\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}", "4\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
           "5\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}", "6\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
           "7\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}", "8\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}",
           "9\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}", "\N{KEYCAP TEN}"]
CUSTOM_LIMIT = {"white": 50, "supreme": 200}
AUTOREACT_LIMIT = 25
NAME_RE = re.compile(r"^[a-z0-9_-]{1,20}$")
QUEUE_CAP = 5000
DANGEROUS = ("administrator", "manage_guild", "manage_roles", "manage_channels", "manage_webhooks", "ban_members", "kick_members", "mention_everyone", "manage_messages")


def parse_colour(text):
    try:
        value = int(text.strip().lstrip("#"), 16)
    except ValueError:
        raise ModError("Give the colour as hex, like `#5865f2`.")
    if not 0 <= value <= 0xFFFFFF or len(text.strip().lstrip("#")) != 6:
        raise ModError("Give the colour as six hex digits, like `#5865f2`.")
    return value


class VIPPlus(commands.Cog, name="VIPPlus"):
    """The extra VIP commands for every plan."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("vip_plus")
        for key in ("customcmds", "autoreact", "welcomedm", "autodelete", "queue", "locks", "counters", "motd"):
            self.store.data.setdefault(key, {} if key != "queue" else [])

    async def cog_load(self):
        self.reaper.start()
        self.counters.start()

    def cog_unload(self):
        self.reaper.cancel()
        self.counters.cancel()

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Helpers
    @property
    def vip(self):
        cog = self.bot.get_cog("VIP")
        if cog is None:
            raise ModError("VIP isn't loaded right now.")
        return cog

    def need(self, ctx, group):
        self.vip.need(ctx, group)

    def colour(self, guild):
        return self.vip.embed_color(guild.id) or discord.Color.gold()

    @staticmethod
    def can_manage(ctx, role):
        if role.is_default() or role.managed:
            raise ModError("That role can't be changed.")
        if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
            raise ModError("That role is at or above your highest role.")
        if role >= ctx.guild.me.top_role:
            raise ModError("That role is at or above my highest role.")

    # ----------------------------------------------------------------- Basic
    @commands.command(name="vipcolor")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def vipcolor(self, ctx, colour: str = ""):
        """VIP. Sets the accent colour of Risk's embeds here. Usage: !vipcolor #5865f2 (or !vipcolor reset)"""
        self.need(ctx, "basic")
        entry = self.vip.cfg(ctx.guild.id)
        if not colour:
            value = entry.get("color")
            await ctx.reply(f"The accent colour is {'`#%06x`' % value if isinstance(value, int) else 'the default'}.", mention_author=False)
            return
        if colour.lower() in ("reset", "default", "off"):
            entry.pop("color", None)
            self.vip.store.save()
            await ctx.reply("Back to the default colour.", mention_author=False)
            return
        entry["color"] = parse_colour(colour)
        self.vip.store.save()
        embed = discord.Embed(description="This is the new accent colour.", color=entry["color"])
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="vippoll")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def vippoll(self, ctx, *, poll: str):
        """VIP. Posts an embed poll with number reactions. Usage: !vippoll Question | Option 1 | Option 2 (up to 10)"""
        self.need(ctx, "basic")
        parts = [p.strip() for p in poll.split("|") if p.strip()]
        if len(parts) < 3:
            raise ModError("Give a question and at least two options, separated by `|`.")
        question, options = parts[0], parts[1:]
        if len(options) > 10:
            raise ModError("A poll can have up to 10 options.")
        if len(question) > 250 or any(len(o) > 150 for o in options):
            raise ModError("Keep the question under 250 characters and each option under 150.")
        embed = discord.Embed(title=question, description="\n".join(f"{NUMBERS[i]} {o}" for i, o in enumerate(options)), color=self.colour(ctx.guild))
        embed.set_footer(text=f"Poll by {ctx.author.display_name}")
        message = await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)
        for i in range(len(options)):
            await message.add_reaction(NUMBERS[i])

    @commands.command(name="vipsay")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def vipsay(self, ctx, channel: Optional[discord.TextChannel], *, text: str):
        """VIP. Makes Risk say something, in this or another channel. Usage: !vipsay [#channel] message"""
        self.need(ctx, "basic")
        channel = channel or ctx.channel
        if not channel.permissions_for(ctx.author).send_messages or not channel.permissions_for(ctx.guild.me).send_messages:
            raise ModError("Either of us can't post in that channel.")
        if len(text) > 1900:
            raise ModError("Keep it under 1900 characters.")
        await channel.send(text, allowed_mentions=NO_MENTIONS)
        if channel.id != ctx.channel.id:
            await ctx.reply(f"Sent in {channel.mention}.", mention_author=False)

    @commands.command(name="vipannounce")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def vipannounce(self, ctx, channel: discord.TextChannel, role: Optional[discord.Role], *, text: str):
        """VIP. Posts an announcement embed and can ping one role. Usage: !vipannounce #channel [@role] Title | Body"""
        self.need(ctx, "basic")
        if not channel.permissions_for(ctx.author).send_messages or not channel.permissions_for(ctx.guild.me).send_messages:
            raise ModError("Either of us can't post in that channel.")
        title, _, body = text.partition("|")
        if not body.strip():
            title, body = "", title
        if len(title.strip()) > 256 or len(body.strip()) > 3500 or not body.strip():
            raise ModError("Give a body under 3500 characters (and a title under 256).")
        ping = None
        if role is not None:
            if not (role.mentionable or ctx.author.guild_permissions.mention_everyone):
                raise ModError("You can't ping that role.")
            ping = role.mention
        embed = discord.Embed(title=title.strip() or None, description=body.strip(), color=self.colour(ctx.guild), timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Announcement from {ctx.author.display_name}")
        await channel.send(ping, embed=embed, allowed_mentions=discord.AllowedMentions(roles=[role] if role else False, everyone=False, users=False))
        await ctx.reply(f"Announced in {channel.mention}.", mention_author=False)

    @commands.command(name="viprolecolor")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def viprolecolor(self, ctx, role: discord.Role, colour: str):
        """VIP. Changes a role's colour. Usage: !viprolecolor @role #ff0000"""
        self.need(ctx, "basic")
        self.can_manage(ctx, role)
        value = parse_colour(colour)
        await role.edit(colour=discord.Colour(value), reason=f"Changed by {ctx.author} with !viprolecolor")
        await ctx.reply(embed=discord.Embed(description=f"{role.mention} is now `#{value:06x}`.", color=value), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="servercard")
    @commands.guild_only()
    async def servercard(self, ctx):
        """VIP. Shows a card with the server's icon, banner and numbers. Usage: !servercard"""
        self.need(ctx, "basic")
        g = ctx.guild
        embed = discord.Embed(title=g.name, description=g.description or None, color=self.colour(g))
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        if g.banner:
            embed.set_image(url=g.banner.url)
        people = sum(1 for m in g.members if not m.bot)
        embed.add_field(name="Owner", value=f"<@{g.owner_id}>")
        embed.add_field(name="Members", value=f"{g.member_count} ({people} people)")
        embed.add_field(name="Created", value=f"<t:{int(g.created_at.timestamp())}:D>")
        embed.add_field(name="Channels", value=f"{len(g.text_channels)} text, {len(g.voice_channels)} voice")
        embed.add_field(name="Roles", value=str(max(len(g.roles) - 1, 0)))
        embed.add_field(name="Boosts", value=f"Level {g.premium_tier} ({g.premium_subscription_count})")
        if g.features:
            embed.add_field(name="Features", value=", ".join(f.replace("_", " ").title() for f in sorted(g.features))[:1000], inline=False)
        embed.set_footer(text=f"ID {g.id}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="topmessages")
    @commands.guild_only()
    async def topmessages(self, ctx):
        """VIP. Shows who sent the most messages (counted for levels). Usage: !topmessages"""
        self.need(ctx, "basic")
        levels = self.bot.get_cog("Levels")
        rows = levels.store.data.get(str(ctx.guild.id), {}) if levels else {}
        ranked = sorted(((int(v.get("msgs", 0) or 0), k) for k, v in rows.items() if isinstance(v, dict)), reverse=True)[:10]
        ranked = [(n, k) for n, k in ranked if n > 0]
        if not ranked:
            raise ModError("No messages have been counted here yet.")
        lines = [f"**{i}.** <@{k}> - {n:,} messages" for i, (n, k) in enumerate(ranked, 1)]
        await ctx.reply(embed=discord.Embed(title="Most messages", description="\n".join(lines), color=self.colour(ctx.guild)), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="userreport")
    @commands.guild_only()
    async def userreport(self, ctx, member: Optional[discord.Member] = None):
        """VIP. A detailed report on a member: dates, roles, level and money. Usage: !userreport [@member]"""
        self.need(ctx, "basic")
        member = member or ctx.author
        embed = discord.Embed(title=str(member), color=member.color if member.color.value else self.colour(ctx.guild))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        if member.joined_at:
            embed.add_field(name="Joined here", value=f"<t:{int(member.joined_at.timestamp())}:R>")
        roles = [r.mention for r in reversed(member.roles) if not r.is_default()]
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:15]) + (" ..." if len(roles) > 15 else "") if roles else "None", inline=False)
        flags = [name.replace("_", " ") for name in ("administrator", "manage_guild", "manage_roles", "ban_members", "kick_members", "manage_messages") if getattr(member.guild_permissions, name)]
        embed.add_field(name="Key permissions", value=", ".join(flags) or "None", inline=False)
        levels = self.bot.get_cog("Levels")
        entry = levels.store.data.get(str(ctx.guild.id), {}).get(str(member.id)) if levels else None
        if isinstance(entry, dict):
            from cogs.levels import level_for
            embed.add_field(name="Level", value=f"{level_for(int(entry.get('xp', 0) or 0))} ({int(entry.get('xp', 0) or 0):,} XP, {int(entry.get('msgs', 0) or 0):,} messages)")
        economy = self.bot.get_cog("Economy")
        account = economy.store.data.get(str(ctx.guild.id), {}).get(str(member.id)) if economy else None
        if isinstance(account, dict):
            embed.add_field(name="Money", value=f"{int(account.get('wallet', 0) or 0):,} wallet, {int(account.get('bank', 0) or 0):,} bank")
        embed.set_footer(text=f"ID {member.id}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="rolereport")
    @commands.guild_only()
    async def rolereport(self, ctx, role: discord.Role):
        """VIP. Lists a role's members, colour and permissions. Usage: !rolereport @role"""
        self.need(ctx, "basic")
        members = role.members
        embed = discord.Embed(title=role.name, color=role.color if role.color.value else self.colour(ctx.guild))
        embed.add_field(name="Members", value=str(len(members)))
        embed.add_field(name="Colour", value=f"`#{role.color.value:06x}`")
        embed.add_field(name="Position", value=str(role.position))
        embed.add_field(name="Options", value=", ".join(n for n, on in (("shown separately", role.hoist), ("mentionable", role.mentionable), ("managed by a bot", role.managed)) if on) or "None", inline=False)
        perms = [n.replace("_", " ") for n, on in role.permissions if on]
        embed.add_field(name="Permissions", value=(", ".join(perms)[:1000] or "None"), inline=False)
        if members:
            shown = " ".join(m.mention for m in members[:20])
            embed.add_field(name="Who has it", value=shown + (f" and {len(members) - 20} more" if len(members) > 20 else ""), inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ----------------------------------------------------------------- White
    @commands.group(name="customcmd", aliases=["cc"], invoke_without_command=True)
    @commands.guild_only()
    async def customcmd(self, ctx):
        """VIP White. Your own commands that reply with text. Usage: !customcmd add <name> <reply> | remove <name> | list"""
        self.need(ctx, "white")
        await ctx.reply("Use `customcmd add <name> <reply>`, `customcmd remove <name>` or `customcmd list`. In the reply, `{user}` is the person and `{server}` the server name.", mention_author=False)

    @customcmd.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def customcmd_add(self, ctx, name: str, *, reply: str):
        """Adds a custom command. Usage: !customcmd add <name> <reply>"""
        self.need(ctx, "white")
        name = name.lower()
        if not NAME_RE.match(name):
            raise ModError("A name is 1 to 20 letters, numbers, `_` or `-`.")
        if self.bot.get_command(name) is not None:
            raise ModError("A built-in command already uses that name.")
        if len(reply) > 1500:
            raise ModError("Keep the reply under 1500 characters.")
        items = self.store.data["customcmds"].setdefault(str(ctx.guild.id), {})
        cap = CUSTOM_LIMIT["supreme" if self.vip.has(ctx.guild.id, "supreme") else "white"]
        if name not in items and len(items) >= cap:
            raise ModError(f"This server has used all {cap} custom commands.")
        items[name] = reply
        self.store.save()
        await ctx.reply(f"Added `{name}`. Anyone can run it.", mention_author=False)

    @customcmd.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def customcmd_remove(self, ctx, name: str):
        """Removes a custom command. Usage: !customcmd remove <name>"""
        self.need(ctx, "white")
        items = self.store.data["customcmds"].get(str(ctx.guild.id), {})
        if items.pop(name.lower(), None) is None:
            raise ModError("There's no custom command with that name.")
        self.store.save()
        await ctx.reply("Removed.", mention_author=False)

    @customcmd.command(name="list")
    async def customcmd_list(self, ctx):
        """Lists this server's custom commands. Usage: !customcmd list"""
        self.need(ctx, "white")
        items = self.store.data["customcmds"].get(str(ctx.guild.id), {})
        await ctx.reply(", ".join(f"`{n}`" for n in sorted(items)) or "No custom commands yet.", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        gid = str(message.guild.id)
        vip = self.bot.get_cog("VIP")
        if vip is None:
            return
        # Messages for the Supreme auto-delete channels are noted so the reaper can remove them later.
        rule = self.store.data["autodelete"].get(gid, {}).get(str(message.channel.id))
        if rule and vip.has(message.guild.id, "supreme") and not message.pinned and len(self.store.data["queue"]) < QUEUE_CAP:
            self.store.data["queue"].append([message.guild.id, message.channel.id, message.id, time.time() + rule * 60])
            self.store.save()
        if not vip.has(message.guild.id, "white"):
            return
        text = message.content or ""
        # Auto reactions
        for word, emoji in self.store.data["autoreact"].get(gid, {}).items():
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I):
                try:
                    await message.add_reaction(discord.PartialEmoji.from_str(emoji) if emoji.startswith("<") else emoji)
                except discord.HTTPException:
                    pass
        # Custom commands
        items = self.store.data["customcmds"].get(gid)
        if not items or not text:
            return
        try:
            prefixes = await self.bot.get_prefix(message)
        except Exception:
            return
        prefixes = [prefixes] if isinstance(prefixes, str) else list(prefixes)
        for prefix in prefixes:
            if prefix and text.startswith(prefix):
                name = text[len(prefix):].split(None, 1)[0].lower() if text[len(prefix):].strip() else ""
                reply = items.get(name)
                if reply:
                    out = reply.replace("{user}", message.author.mention).replace("{server}", message.guild.name)
                    await message.channel.send(out[:2000], allowed_mentions=discord.AllowedMentions(users=[message.author]))
                return

    @commands.group(name="autoreact", invoke_without_command=True)
    @commands.guild_only()
    async def autoreact(self, ctx):
        """VIP White. Reacts to messages that contain a word. Usage: !autoreact add <word> <emoji> | remove <word> | list"""
        self.need(ctx, "white")
        await ctx.reply("Use `autoreact add <word> <emoji>`, `autoreact remove <word>` or `autoreact list`.", mention_author=False)

    @autoreact.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def autoreact_add(self, ctx, word: str, emoji: str):
        """Reacts with an emoji whenever the word appears. Usage: !autoreact add <word> <emoji>"""
        self.need(ctx, "white")
        word = word.lower()
        if not 1 <= len(word) <= 32:
            raise ModError("The word must be 1 to 32 characters.")
        custom = re.fullmatch(r"<a?:\w{2,32}:\d{15,25}>", emoji)
        if not custom and (len(emoji) > 8 or emoji.isalnum()):
            raise ModError("Give an emoji, like \N{THUMBS UP SIGN} or a server emoji.")
        items = self.store.data["autoreact"].setdefault(str(ctx.guild.id), {})
        if word not in items and len(items) >= AUTOREACT_LIMIT:
            raise ModError(f"This server has used all {AUTOREACT_LIMIT} auto reactions.")
        items[word] = emoji
        self.store.save()
        await ctx.reply(f"I'll react with {emoji} when someone says `{word}`.", mention_author=False)

    @autoreact.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def autoreact_remove(self, ctx, word: str):
        """Removes an auto reaction. Usage: !autoreact remove <word>"""
        self.need(ctx, "white")
        if self.store.data["autoreact"].get(str(ctx.guild.id), {}).pop(word.lower(), None) is None:
            raise ModError("There's no auto reaction for that word.")
        self.store.save()
        await ctx.reply("Removed.", mention_author=False)

    @autoreact.command(name="list")
    async def autoreact_list(self, ctx):
        """Lists the auto reactions. Usage: !autoreact list"""
        self.need(ctx, "white")
        items = self.store.data["autoreact"].get(str(ctx.guild.id), {})
        await ctx.reply("\n".join(f"`{w}` {e}" for w, e in sorted(items.items())) or "No auto reactions yet.", mention_author=False)

    @commands.group(name="welcomedm", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcomedm(self, ctx, *, text: str = ""):
        """VIP White. Sends new members a private message. Usage: !welcomedm set <text> | off | show"""
        self.need(ctx, "white")
        await ctx.reply("Use `welcomedm set <text>`, `welcomedm show` or `welcomedm off`. In the text, `{user}` is the member's name and `{server}` the server.", mention_author=False)

    @welcomedm.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def welcomedm_set(self, ctx, *, text: str):
        """Sets the message. Usage: !welcomedm set <text>"""
        self.need(ctx, "white")
        if len(text) > 1500:
            raise ModError("Keep it under 1500 characters.")
        self.store.data["welcomedm"][str(ctx.guild.id)] = text
        self.store.save()
        await ctx.reply("New members will get that message in a DM.", mention_author=False)

    @welcomedm.command(name="show")
    @commands.has_permissions(manage_guild=True)
    async def welcomedm_show(self, ctx):
        """Shows the message. Usage: !welcomedm show"""
        self.need(ctx, "white")
        text = self.store.data["welcomedm"].get(str(ctx.guild.id))
        await ctx.reply(text or "No welcome DM is set.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @welcomedm.command(name="off")
    @commands.has_permissions(manage_guild=True)
    async def welcomedm_off(self, ctx):
        """Turns it off. Usage: !welcomedm off"""
        self.need(ctx, "white")
        self.store.data["welcomedm"].pop(str(ctx.guild.id), None)
        self.store.save()
        await ctx.reply("Turned off.", mention_author=False)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        text = self.store.data["welcomedm"].get(str(member.guild.id))
        vip = self.bot.get_cog("VIP")
        if not text or member.bot or vip is None or not vip.has(member.guild.id, "white"):
            return
        try:
            await member.send(text.replace("{user}", member.display_name).replace("{server}", member.guild.name)[:2000])
        except discord.HTTPException:
            pass

    @commands.command(name="embededit")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def embededit(self, ctx, message: discord.Message, *, text: str):
        """VIP White. Edits an embed Risk posted. Usage: !embededit <message id or link> Title | Body"""
        self.need(ctx, "white")
        if message.guild is None or message.guild.id != ctx.guild.id:
            raise ModError("That message isn't in this server.")
        if message.author.id != self.bot.user.id or not message.embeds:
            raise ModError("I can only edit embeds that I posted.")
        if not message.channel.permissions_for(ctx.author).manage_messages:
            raise ModError("You can't manage messages in that channel.")
        title, _, body = text.partition("|")
        if not body.strip():
            title, body = message.embeds[0].title or "", title
        if len(title.strip()) > 256 or len(body.strip()) > 3500 or not body.strip():
            raise ModError("Give a body under 3500 characters (and a title under 256).")
        embed = message.embeds[0].copy()
        embed.title = title.strip() or None
        embed.description = body.strip()
        await message.edit(embed=embed)
        await ctx.reply("Edited.", mention_author=False)

    @commands.command(name="stafflist")
    @commands.guild_only()
    async def stafflist(self, ctx):
        """VIP White. Lists the staff, grouped by their top role. Usage: !stafflist"""
        self.need(ctx, "white")
        groups = {}
        for member in ctx.guild.members:
            if member.bot:
                continue
            perms = member.guild_permissions
            if perms.administrator or perms.manage_guild or perms.manage_messages or perms.kick_members or perms.ban_members:
                groups.setdefault(member.top_role, []).append(member)
        if not groups:
            raise ModError("No staff found. (I may not have the member list yet.)")
        embed = discord.Embed(title="Staff", color=self.colour(ctx.guild))
        for role in sorted(groups, key=lambda r: r.position, reverse=True)[:10]:
            people = sorted(groups[role], key=lambda m: m.display_name.lower())
            embed.add_field(name=f"{role.name} ({len(people)})", value=" ".join(m.mention for m in people[:25]) + (" ..." if len(people) > 25 else ""), inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # --------------------------------------------------------------- Supreme
    @commands.group(name="autodelete", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def autodelete(self, ctx):
        """VIP Supreme. Deletes new messages in a channel after a delay. Usage: !autodelete set #channel <minutes> | off #channel | list"""
        self.need(ctx, "supreme")
        await ctx.reply("Use `autodelete set #channel <minutes>`, `autodelete off #channel` or `autodelete list`. Pinned messages are kept.", mention_author=False)

    @autodelete.command(name="set")
    @commands.has_permissions(manage_channels=True)
    async def autodelete_set(self, ctx, channel: discord.TextChannel, minutes: int):
        """Deletes messages in the channel after some minutes. Usage: !autodelete set #channel <minutes>"""
        self.need(ctx, "supreme")
        if not 1 <= minutes <= 10080:
            raise ModError("Pick between 1 minute and 7 days (10080 minutes).")
        if not channel.permissions_for(ctx.guild.me).manage_messages:
            raise ModError("I need the Manage Messages permission in that channel.")
        self.store.data["autodelete"].setdefault(str(ctx.guild.id), {})[str(channel.id)] = minutes
        self.store.save()
        await ctx.reply(f"New messages in {channel.mention} will be deleted after {minutes} minute(s). Messages already there aren't touched.", mention_author=False)

    @autodelete.command(name="off")
    @commands.has_permissions(manage_channels=True)
    async def autodelete_off(self, ctx, channel: discord.TextChannel):
        """Stops deleting in a channel. Usage: !autodelete off #channel"""
        self.need(ctx, "supreme")
        if self.store.data["autodelete"].get(str(ctx.guild.id), {}).pop(str(channel.id), None) is None:
            raise ModError("That channel doesn't have auto delete.")
        self.store.data["queue"] = [q for q in self.store.data["queue"] if q[1] != channel.id]
        self.store.save()
        await ctx.reply("Stopped.", mention_author=False)

    @autodelete.command(name="list")
    @commands.has_permissions(manage_channels=True)
    async def autodelete_list(self, ctx):
        """Lists the channels. Usage: !autodelete list"""
        self.need(ctx, "supreme")
        rules = self.store.data["autodelete"].get(str(ctx.guild.id), {})
        await ctx.reply("\n".join(f"<#{c}>: after {m} min" for c, m in rules.items()) or "No channel has auto delete.", mention_author=False)

    @tasks.loop(seconds=30)
    async def reaper(self):
        queue = self.store.data["queue"]
        now = time.time()
        due = [q for q in queue if q[3] <= now][:50]
        if not due:
            return
        for gid, cid, mid, _ in due:
            channel = self.bot.get_channel(cid)
            if channel is not None:
                try:
                    message = await channel.fetch_message(mid)
                    if not message.pinned:
                        await message.delete()
                except discord.HTTPException:
                    pass
        gone = {tuple(q) for q in due}
        self.store.data["queue"] = [q for q in queue if tuple(q) not in gone]
        self.store.save()

    @reaper.before_loop
    async def before_reaper(self):
        await self.bot.wait_until_ready()

    @commands.command(name="slowmodeall")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmodeall(self, ctx, seconds: int):
        """VIP Supreme. Sets slowmode on every text channel. Usage: !slowmodeall <seconds> (0 turns it off)"""
        self.need(ctx, "supreme")
        if not 0 <= seconds <= 21600:
            raise ModError("Slowmode must be between 0 and 21600 seconds.")
        done = 0
        for channel in ctx.guild.text_channels:
            if channel.slowmode_delay == seconds or not channel.permissions_for(ctx.guild.me).manage_channels:
                continue
            try:
                await channel.edit(slowmode_delay=seconds, reason=f"!slowmodeall by {ctx.author}")
                done += 1
            except discord.HTTPException:
                pass
        await ctx.reply(f"Slowmode is {'off' if not seconds else f'{seconds}s'} in {done} channel(s).", mention_author=False)

    @commands.command(name="lockall")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockall(self, ctx, *, reason: str = "Server lock"):
        """VIP Supreme. Stops everyone from sending in every text channel. Usage: !lockall [reason]. Undo with !unlockall"""
        self.need(ctx, "supreme")
        everyone = ctx.guild.default_role
        saved = self.store.data["locks"].setdefault(str(ctx.guild.id), {})
        done = 0
        for channel in ctx.guild.text_channels:
            if str(channel.id) in saved or not channel.permissions_for(ctx.guild.me).manage_channels:
                continue
            current = channel.overwrites_for(everyone).send_messages
            try:
                await channel.set_permissions(everyone, send_messages=False, reason=f"{reason[:100]} ({ctx.author})")
                saved[str(channel.id)] = current
                done += 1
            except discord.HTTPException:
                pass
        self.store.save()
        await ctx.reply(f"Locked {done} channel(s). Run `!unlockall` to put them back exactly as they were.", mention_author=False)

    @commands.command(name="unlockall")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockall(self, ctx):
        """VIP Supreme. Undoes !lockall and restores each channel. Usage: !unlockall"""
        self.need(ctx, "supreme")
        everyone = ctx.guild.default_role
        saved = self.store.data["locks"].get(str(ctx.guild.id), {})
        if not saved:
            raise ModError("Nothing is locked by `!lockall`.")
        done = 0
        for cid, previous in list(saved.items()):
            channel = ctx.guild.get_channel(int(cid))
            if channel is not None:
                try:
                    await channel.set_permissions(everyone, send_messages=previous, reason=f"Unlocked by {ctx.author}")
                    done += 1
                except discord.HTTPException:
                    continue
            saved.pop(cid, None)
        self.store.save()
        await ctx.reply(f"Unlocked {done} channel(s).", mention_author=False)

    @commands.command(name="serverbackup")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def serverbackup(self, ctx):
        """VIP Supreme. Sends a file listing the server's roles and channels. Usage: !serverbackup"""
        self.need(ctx, "supreme")
        g = ctx.guild
        data = {
            "server": {"name": g.name, "id": g.id, "created": g.created_at.isoformat(), "members": g.member_count},
            "roles": [{"name": r.name, "id": r.id, "colour": f"#{r.color.value:06x}", "position": r.position, "permissions": r.permissions.value, "hoist": r.hoist, "mentionable": r.mentionable, "managed": r.managed} for r in g.roles],
            "channels": [{"name": c.name, "id": c.id, "type": str(c.type), "category": c.category.name if c.category else None, "position": c.position,
                          "topic": getattr(c, "topic", None), "nsfw": getattr(c, "nsfw", False), "slowmode": getattr(c, "slowmode_delay", 0)} for c in g.channels],
            "emojis": [{"name": e.name, "id": e.id, "animated": e.animated} for e in g.emojis],
        }
        raw = json.dumps(data, indent=2).encode()
        await ctx.reply("Here's a snapshot of your server's setup. It lists roles and channels. It can't restore them by itself.", file=discord.File(io.BytesIO(raw), filename=f"{g.id}-backup.json"), mention_author=False)

    @commands.group(name="membercounter", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def membercounter(self, ctx):
        """VIP Supreme. Keeps a channel's name showing the member count. Usage: !membercounter set #voice [Members: {count}] | off"""
        self.need(ctx, "supreme")
        await ctx.reply("Use `membercounter set #channel [format]` or `membercounter off`. In the format, `{count}` is the number. The name updates every 10 minutes.", mention_author=False)

    @membercounter.command(name="set")
    @commands.has_permissions(manage_channels=True)
    async def membercounter_set(self, ctx, channel: discord.abc.GuildChannel, *, format: str = "Members: {count}"):
        """Picks the channel. Usage: !membercounter set #channel [Members: {count}]"""
        self.need(ctx, "supreme")
        if "{count}" not in format or len(format) > 80:
            raise ModError("The format needs `{count}` and must be under 80 characters.")
        if not channel.permissions_for(ctx.guild.me).manage_channels:
            raise ModError("I need Manage Channels for that channel.")
        self.store.data["counters"][str(ctx.guild.id)] = {"channel": channel.id, "format": format}
        self.store.save()
        await self.update_counter(ctx.guild)
        await ctx.reply(f"{channel.mention} will show the member count.", mention_author=False)

    @membercounter.command(name="off")
    @commands.has_permissions(manage_channels=True)
    async def membercounter_off(self, ctx):
        """Stops updating. Usage: !membercounter off"""
        self.need(ctx, "supreme")
        if self.store.data["counters"].pop(str(ctx.guild.id), None) is None:
            raise ModError("No member counter is set.")
        self.store.save()
        await ctx.reply("Stopped.", mention_author=False)

    async def update_counter(self, guild):
        entry = self.store.data["counters"].get(str(guild.id))
        channel = guild.get_channel(entry["channel"]) if entry else None
        if channel is None:
            return False
        name = entry["format"].replace("{count}", f"{guild.member_count:,}")[:100]
        if channel.name == name:
            return False
        try:
            await channel.edit(name=name, reason="Member counter")
        except discord.HTTPException:
            return False
        return True

    @tasks.loop(minutes=10)
    async def counters(self):
        for gid in list(self.store.data["counters"]):
            guild = self.bot.get_guild(int(gid))
            vip = self.bot.get_cog("VIP")
            if guild is not None and vip is not None and vip.has(guild.id, "supreme"):
                await self.update_counter(guild)

    @counters.before_loop
    async def before_counters(self):
        await self.bot.wait_until_ready()

    @commands.command(name="permaudit")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def permaudit(self, ctx):
        """VIP Supreme. Shows which roles hold powerful permissions and how many members have them. Usage: !permaudit"""
        self.need(ctx, "supreme")
        rows = []
        for role in sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True):
            if role.is_default():
                continue
            held = [p.replace("_", " ") for p in DANGEROUS if getattr(role.permissions, p)]
            if held:
                rows.append(f"**{role.name}** ({len(role.members)}): {'everything (Administrator)' if role.permissions.administrator else ', '.join(held)}")
        if not rows:
            raise ModError("No role has powerful permissions.")
        text = "\n".join(rows)
        embed = discord.Embed(title="Powerful permissions", description=text[:4000], color=self.colour(ctx.guild))
        if ctx.guild.default_role.permissions.mention_everyone:
            embed.add_field(name="Heads up", value="@everyone can mention everyone.", inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # -------------------------------------------------------------- Lifetime
    @commands.command(name="founder")
    @commands.guild_only()
    async def founder(self, ctx):
        """VIP Lifetime. Shows this server's founding supporter card. Usage: !founder"""
        self.need(ctx, "lifetime")
        entry = self.vip.store.data["guilds"].get(str(ctx.guild.id), {})
        embed = discord.Embed(title=f"{ctx.guild.name} is a Founding Supporter", description="This server backed Risk for life.", color=self.colour(ctx.guild))
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        since = entry.get("since")
        if since:
            embed.add_field(name="Supporting since", value=f"<t:{int(since)}:D>")
        embed.add_field(name="Plan", value="Lifetime, never expires")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.group(name="motd", invoke_without_command=True)
    @commands.guild_only()
    async def motd(self, ctx):
        """VIP Lifetime. Shows the server's message of the day. Usage: !motd (set with !motd set <text>, clear with !motd clear)"""
        self.need(ctx, "lifetime")
        text = self.store.data["motd"].get(str(ctx.guild.id))
        if not text:
            raise ModError("No message of the day is set. Set one with `!motd set <text>`.")
        await ctx.reply(embed=discord.Embed(title="Message of the day", description=text, color=self.colour(ctx.guild)), mention_author=False, allowed_mentions=NO_MENTIONS)

    @motd.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def motd_set(self, ctx, *, text: str):
        """Sets the message of the day. Usage: !motd set <text>"""
        self.need(ctx, "lifetime")
        if len(text) > 1000:
            raise ModError("Keep it under 1000 characters.")
        self.store.data["motd"][str(ctx.guild.id)] = text
        self.store.save()
        await ctx.reply("Saved. Anyone can see it with `!motd`.", mention_author=False)

    @motd.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def motd_clear(self, ctx):
        """Clears the message of the day. Usage: !motd clear"""
        self.need(ctx, "lifetime")
        self.store.data["motd"].pop(str(ctx.guild.id), None)
        self.store.save()
        await ctx.reply("Cleared.", mention_author=False)


async def setup(bot):
    await bot.add_cog(VIPPlus(bot))
