import random
import time
from typing import Union

import discord
from discord.ext import commands, tasks

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

DEFAULT_MESSAGE = "🎉 {user} reached level **{level}**!"
MAX_XP = 10_000_000


def level_for(xp):
    return int((max(xp, 0) / 100) ** 0.5)


def xp_for(level):
    return 100 * level * level


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("levels")
        self.settings = JsonStore("level_settings")
        self.dirty = False

    async def cog_load(self):
        self.flush.start()

    def cog_unload(self):
        self.flush.cancel()
        if self.dirty:
            self.store.save()

    @tasks.loop(seconds=30)
    async def flush(self):
        if self.dirty:
            self.dirty = False
            self.store.save()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Data helpers
    def entry(self, guild_id, user_id):
        entry = self.store.data.setdefault(str(guild_id), {}).setdefault(str(user_id), {"xp": 0, "last": 0, "msgs": 0})
        entry.setdefault("msgs", 0)
        return entry

    def cfg(self, guild_id):
        data = self.settings.data.setdefault(str(guild_id), {})
        data.setdefault("message", None)
        data.setdefault("channel", "same")
        data.setdefault("rewards", {})
        data.setdefault("mode", "stack")
        data.setdefault("noxp_channels", [])
        data.setdefault("noxp_roles", [])
        data.setdefault("multiplier", 1.0)
        data.setdefault("cooldown", 60)
        return data

    def ranked(self, guild_id):
        guild = self.store.data.get(str(guild_id), {})
        return sorted(guild.items(), key=lambda item: item[1]["xp"], reverse=True)

    def set_xp(self, guild_id, user_id, xp):
        entry = self.entry(guild_id, user_id)
        entry["xp"] = max(0, min(MAX_XP, int(xp)))
        self.dirty = True
        return entry["xp"]

    async def apply_rewards(self, member):
        """Gives (or swaps) the reward roles a member qualifies for. Returns how many roles were added."""
        rewards = self.cfg(member.guild.id)["rewards"]
        if not rewards:
            return 0
        level = level_for(self.entry(member.guild.id, member.id)["xp"])
        eligible = sorted((int(lvl), member.guild.get_role(rid)) for lvl, rid in rewards.items() if int(lvl) <= level)
        eligible = [(lvl, role) for lvl, role in eligible if role is not None and role < member.guild.me.top_role]
        if not eligible:
            return 0
        wanted = [eligible[-1][1]] if self.cfg(member.guild.id)["mode"] == "replace" else [role for _, role in eligible]
        added = [role for role in wanted if role not in member.roles]
        try:
            if added:
                await member.add_roles(*added, reason="Level reward")
            if self.cfg(member.guild.id)["mode"] == "replace":
                others = [role for role in member.roles if role.id in rewards.values() and role not in wanted]
                if others:
                    await member.remove_roles(*others, reason="Level reward replaced")
        except discord.HTTPException:
            return 0
        return len(added)

    async def announce(self, member, channel, level):
        config = self.cfg(member.guild.id)
        target = config["channel"]
        if target == "off":
            return
        if target != "same":
            channel = member.guild.get_channel(int(target)) or channel
        template = config["message"] or DEFAULT_MESSAGE
        text = template.replace("{user}", member.mention).replace("{level}", str(level)).replace("{name}", member.display_name)
        try:
            await channel.send(text[:1900], allowed_mentions=discord.AllowedMentions(users=[member]))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None or not message.content:
            return
        config = self.cfg(message.guild.id)
        entry = self.entry(message.guild.id, message.author.id)
        entry["msgs"] += 1
        self.dirty = True
        if message.channel.id in config["noxp_channels"]:
            return
        if any(role.id in config["noxp_roles"] for role in getattr(message.author, "roles", [])):
            return
        now = int(time.time())
        if now - entry["last"] < config["cooldown"]:
            return
        before = level_for(entry["xp"])
        entry["xp"] = min(MAX_XP, entry["xp"] + max(1, round(random.randint(15, 25) * config["multiplier"])))
        entry["last"] = now
        after = level_for(entry["xp"])
        if after > before:
            await self.apply_rewards(message.author)
            await self.announce(message.author, message.channel, after)

    # Viewing
    @commands.command(name="rank", aliases=["level"])
    async def rank(self, ctx, member: discord.Member = None):
        """Shows someone's level and XP. Usage: !rank @user"""
        member = member or ctx.author
        entry = self.store.data.get(str(ctx.guild.id), {}).get(str(member.id), {"xp": 0, "msgs": 0})
        xp = entry["xp"]
        level = level_for(xp)
        start, goal = xp_for(level), xp_for(level + 1)
        progress = (xp - start) / (goal - start)
        bar = "█" * int(progress * 12) + "░" * (12 - int(progress * 12))
        position = next((i for i, (uid, _) in enumerate(self.ranked(ctx.guild.id), start=1) if uid == str(member.id)), None)
        embed = discord.Embed(title=member.display_name, color=discord.Color.light_grey())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="Rank", value=f"#{position}" if position else "Unranked")
        embed.add_field(name="XP", value=f"{xp:,} / {goal:,}")
        embed.add_field(name="Messages", value=f"{entry.get('msgs', 0):,}")
        embed.add_field(name="Progress", value=f"`{bar}` {int(progress * 100)}%", inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="levels", aliases=["xpboard"])
    async def levels(self, ctx, page: int = 1):
        """Shows the most active members by XP, 10 per page. Usage: !levels 2"""
        ranked = self.ranked(ctx.guild.id)
        pages = max(1, -(-len(ranked) // 10))
        page = max(1, min(page, pages))
        chunk = ranked[(page - 1) * 10: page * 10]
        if not chunk:
            await ctx.reply("Nobody has any XP yet. Start chatting.", mention_author=False)
            return
        lines = []
        for index, (uid, entry) in enumerate(chunk, start=(page - 1) * 10 + 1):
            member = ctx.guild.get_member(int(uid))
            name = discord.utils.escape_markdown(member.display_name) if member else f"User {uid}"
            lines.append(f"**{index}.** {name}: level {level_for(entry['xp'])} ({entry['xp']:,} XP)")
        embed = discord.Embed(title="Top chatters", description="\n".join(lines), color=discord.Color.light_grey())
        embed.set_footer(text=f"Page {page} of {pages}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="nextlevel")
    async def nextlevel(self, ctx, member: discord.Member = None):
        """Shows how much XP is left for the next level. Usage: !nextlevel @user"""
        member = member or ctx.author
        xp = self.entry(ctx.guild.id, member.id)["xp"]
        level = level_for(xp)
        left = xp_for(level + 1) - xp
        average = 20 * self.cfg(ctx.guild.id)["multiplier"]
        messages = max(1, round(left / average))
        await ctx.reply(f"{member.display_name} needs **{left:,} XP** for level {level + 1}, about {messages:,} more XP-earning message(s).", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="xpneeded")
    async def xpneeded(self, ctx, level: int):
        """Shows the total XP needed to reach a level. Usage: !xpneeded 25"""
        if not 1 <= level <= 3000:
            await ctx.reply("Pick a level from 1 to 3000.", mention_author=False)
            return
        await ctx.reply(f"Level {level} starts at **{xp_for(level):,} XP**.", mention_author=False)

    @commands.command(name="levelstats")
    async def levelstats(self, ctx):
        """Shows level statistics for the server. Usage: !levelstats"""
        ranked = self.ranked(ctx.guild.id)
        if not ranked:
            await ctx.reply("Nobody has any XP yet.", mention_author=False)
            return
        total = sum(entry["xp"] for _, entry in ranked)
        top_uid, top_entry = ranked[0]
        embed = discord.Embed(title="Level statistics", color=discord.Color.light_grey())
        embed.add_field(name="Ranked members", value=f"{len(ranked):,}")
        embed.add_field(name="Total XP", value=f"{total:,}")
        embed.add_field(name="Average level", value=f"{sum(level_for(e['xp']) for _, e in ranked) / len(ranked):.1f}")
        embed.add_field(name="Messages counted", value=f"{sum(e.get('msgs', 0) for _, e in ranked):,}")
        embed.add_field(name="Top member", value=f"<@{top_uid}> (level {level_for(top_entry['xp'])})")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="levelinfo")
    async def levelinfo(self, ctx):
        """Shows how levels are set up in this server. Usage: !levelinfo"""
        config = self.cfg(ctx.guild.id)
        channel = {"same": "Where they level up", "off": "Off"}.get(config["channel"], f"<#{config['channel']}>")
        embed = discord.Embed(title="Level settings", color=discord.Color.light_grey())
        embed.add_field(name="Level-up message", value=config["message"] or DEFAULT_MESSAGE, inline=False)
        embed.add_field(name="Announce in", value=channel)
        embed.add_field(name="XP multiplier", value=f"×{config['multiplier']:g}")
        embed.add_field(name="XP cooldown", value=f"{config['cooldown']}s")
        embed.add_field(name="Reward roles", value=f"{len(config['rewards'])} ({config['mode']})")
        embed.add_field(name="No-XP channels", value=" ".join(f"<#{c}>" for c in config["noxp_channels"]) or "None", inline=False)
        embed.add_field(name="No-XP roles", value=" ".join(f"<@&{r}>" for r in config["noxp_roles"]) or "None", inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # XP edits
    @commands.command(name="setxp")
    @commands.has_permissions(manage_guild=True)
    async def setxp(self, ctx, member: discord.Member, xp: int):
        """Sets someone's XP. Usage: !setxp @user 2500"""
        if not 0 <= xp <= MAX_XP:
            await ctx.reply(f"XP must be between 0 and {MAX_XP:,}.", mention_author=False)
            return
        value = self.set_xp(ctx.guild.id, member.id, xp)
        await self.apply_rewards(member)
        await ctx.reply(f"Set {member.display_name} to {value:,} XP (level {level_for(value)}).", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="setlevel")
    @commands.has_permissions(manage_guild=True)
    async def setlevel(self, ctx, member: discord.Member, level: int):
        """Sets someone to the start of a level. Usage: !setlevel @user 10"""
        if not 0 <= level <= 3000:
            await ctx.reply("Pick a level from 0 to 3000.", mention_author=False)
            return
        value = self.set_xp(ctx.guild.id, member.id, xp_for(level))
        await self.apply_rewards(member)
        await ctx.reply(f"Set {member.display_name} to level {level} ({value:,} XP).", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="addxp")
    @commands.has_permissions(manage_guild=True)
    async def addxp(self, ctx, member: discord.Member, amount: int):
        """Gives someone extra XP. Usage: !addxp @user 500"""
        if not 1 <= amount <= MAX_XP:
            await ctx.reply("Give an amount from 1 to 10,000,000.", mention_author=False)
            return
        value = self.set_xp(ctx.guild.id, member.id, self.entry(ctx.guild.id, member.id)["xp"] + amount)
        await self.apply_rewards(member)
        await ctx.reply(f"Gave {member.display_name} {amount:,} XP. They're at {value:,} (level {level_for(value)}).", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="removexp")
    @commands.has_permissions(manage_guild=True)
    async def removexp(self, ctx, member: discord.Member, amount: int):
        """Takes XP away from someone. Usage: !removexp @user 500"""
        if not 1 <= amount <= MAX_XP:
            await ctx.reply("Give an amount from 1 to 10,000,000.", mention_author=False)
            return
        value = self.set_xp(ctx.guild.id, member.id, self.entry(ctx.guild.id, member.id)["xp"] - amount)
        await ctx.reply(f"Took {amount:,} XP from {member.display_name}. They're at {value:,} (level {level_for(value)}).", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="resetxp")
    @commands.has_permissions(manage_guild=True)
    async def resetxp(self, ctx, member: discord.Member):
        """Resets one person's XP and message count. Usage: !resetxp @user"""
        self.store.data.get(str(ctx.guild.id), {}).pop(str(member.id), None)
        self.dirty = True
        await ctx.reply(f"Reset {member.display_name} to level 0.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="resetlevels")
    @commands.has_permissions(administrator=True)
    async def resetlevels(self, ctx, confirm: str = ""):
        """Resets everyone's XP in this server. Usage: !resetlevels confirm"""
        if confirm.lower() != "confirm":
            await ctx.reply("This erases every member's XP. Run `!resetlevels confirm` to continue.", mention_author=False)
            return
        self.store.data[str(ctx.guild.id)] = {}
        self.dirty = True
        await ctx.reply("Everyone's XP has been reset.", mention_author=False)

    # Settings
    @commands.command(name="levelmessage")
    @commands.has_permissions(manage_guild=True)
    async def levelmessage(self, ctx, *, text: str):
        """Sets the level-up message using {user}, {name} and {level}, or reset. Usage: !levelmessage Nice one {user}, level {level}!"""
        config = self.cfg(ctx.guild.id)
        if text.lower() == "reset":
            config["message"] = None
            self.settings.save()
            await ctx.reply("Level-up message reset to the default.", mention_author=False)
            return
        config["message"] = text[:300]
        self.settings.save()
        preview = text.replace("{user}", ctx.author.mention).replace("{level}", "5").replace("{name}", ctx.author.display_name)
        await ctx.reply(f"Saved. Preview:\n{preview[:300]}", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="levelchannel")
    @commands.has_permissions(manage_guild=True)
    async def levelchannel(self, ctx, target: str):
        """Chooses where level-ups are announced: a #channel, here, or off. Usage: !levelchannel #levels"""
        config = self.cfg(ctx.guild.id)
        lowered = target.lower()
        if lowered in ("off", "same", "here"):
            config["channel"] = "off" if lowered == "off" else "same"
            text = "Level-ups won't be announced." if lowered == "off" else "Level-ups are announced in the channel where they happen."
        else:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, target)
            except commands.BadArgument:
                await ctx.reply("Use a #channel, `here` or `off`.", mention_author=False)
                return
            config["channel"] = channel.id
            text = f"Level-ups are announced in {channel.mention}."
        self.settings.save()
        await ctx.reply(text, mention_author=False)

    @commands.command(name="xpmultiplier")
    @commands.has_permissions(manage_guild=True)
    async def xpmultiplier(self, ctx, value: float):
        """Sets how much XP each message earns, from 0.5 to 5. Usage: !xpmultiplier 2"""
        if not 0.5 <= value <= 5:
            await ctx.reply("Pick a multiplier from 0.5 to 5.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["multiplier"] = round(value, 2)
        self.settings.save()
        await ctx.reply(f"XP is now ×{value:g}.", mention_author=False)

    @commands.command(name="xpcooldown")
    @commands.has_permissions(manage_guild=True)
    async def xpcooldown(self, ctx, seconds: int):
        """Sets how many seconds a member waits between XP gains. Usage: !xpcooldown 45"""
        if not 10 <= seconds <= 600:
            await ctx.reply("Pick between 10 and 600 seconds.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["cooldown"] = seconds
        self.settings.save()
        await ctx.reply(f"Members now earn XP at most once every {seconds} seconds.", mention_author=False)

    @commands.command(name="noxp")
    @commands.has_permissions(manage_guild=True)
    async def noxp(self, ctx, target: Union[discord.TextChannel, discord.Role]):
        """Toggles a channel or role that earns no XP. Usage: !noxp #bot-spam"""
        config = self.cfg(ctx.guild.id)
        if isinstance(target, discord.Role):
            bucket, label = config["noxp_roles"], target.mention
        elif isinstance(target, discord.TextChannel):
            bucket, label = config["noxp_channels"], target.mention
        else:
            await ctx.reply("Mention a text channel or a role.", mention_author=False)
            return
        if target.id in bucket:
            bucket.remove(target.id)
            text = f"{label} earns XP again."
        else:
            bucket.append(target.id)
            text = f"{label} no longer earns XP."
        self.settings.save()
        await ctx.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)

    # Reward roles
    @commands.command(name="levelreward")
    @commands.has_permissions(manage_roles=True)
    async def levelreward(self, ctx, level: int, role: discord.Role):
        """Gives a role when members reach a level. Usage: !levelreward 10 @Regular"""
        if not 1 <= level <= 3000:
            await ctx.reply("Pick a level from 1 to 3000.", mention_author=False)
            return
        if role >= ctx.guild.me.top_role or role.is_default() or role.managed:
            await ctx.reply("I can't hand out that role. Move my role above it, and don't pick @everyone or a bot role.", mention_author=False)
            return
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.reply("That role is above your highest role.", mention_author=False)
            return
        config = self.cfg(ctx.guild.id)
        if len(config["rewards"]) >= 25 and str(level) not in config["rewards"]:
            await ctx.reply("You can have up to 25 level rewards.", mention_author=False)
            return
        config["rewards"][str(level)] = role.id
        self.settings.save()
        await ctx.reply(f"Members who reach level {level} get {role.mention}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="levelrewards", aliases=["levelroles"])
    async def levelrewards(self, ctx):
        """Lists the roles given at each level. Usage: !levelrewards"""
        config = self.cfg(ctx.guild.id)
        if not config["rewards"]:
            await ctx.reply("No level rewards yet. Add one with `!levelreward 10 @role`.", mention_author=False)
            return
        lines = [f"Level **{level}** → <@&{rid}>" for level, rid in sorted(config["rewards"].items(), key=lambda item: int(item[0]))]
        embed = discord.Embed(title="Level rewards", description="\n".join(lines), color=discord.Color.light_grey())
        embed.set_footer(text=f"Mode: {config['mode']}")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="delreward")
    @commands.has_permissions(manage_roles=True)
    async def delreward(self, ctx, level: int):
        """Removes the reward for a level. Usage: !delreward 10"""
        if self.cfg(ctx.guild.id)["rewards"].pop(str(level), None) is None:
            await ctx.reply(f"There's no reward for level {level}.", mention_author=False)
            return
        self.settings.save()
        await ctx.reply(f"Removed the level {level} reward. Roles members already have stay.", mention_author=False)

    @commands.command(name="rewardmode")
    @commands.has_permissions(manage_roles=True)
    async def rewardmode(self, ctx, mode: str):
        """Chooses whether reward roles stack or only the newest is kept. Usage: !rewardmode replace"""
        mode = mode.lower()
        if mode not in ("stack", "replace"):
            await ctx.reply("Use `stack` (keep every reward) or `replace` (keep only the newest).", mention_author=False)
            return
        self.cfg(ctx.guild.id)["mode"] = mode
        self.settings.save()
        await ctx.reply(f"Reward roles now **{mode}**.", mention_author=False)

    @commands.command(name="rewardsync")
    @commands.has_permissions(manage_roles=True)
    async def rewardsync(self, ctx):
        """Gives reward roles to members who already qualify. Usage: !rewardsync"""
        if not self.cfg(ctx.guild.id)["rewards"]:
            await ctx.reply("There are no level rewards to sync.", mention_author=False)
            return
        async with ctx.typing():
            given = 0
            for uid in list(self.store.data.get(str(ctx.guild.id), {})):
                member = ctx.guild.get_member(int(uid))
                if member is not None and not member.bot:
                    given += await self.apply_rewards(member)
        await ctx.reply(f"Done. Added {given} role(s).", mention_author=False)


async def setup(bot):
    await bot.add_cog(Levels(bot))
