import discord
from discord.ext import commands

from cogs.levels import level_for, xp_for
from utils.helpers import NO_MENTIONS, explain_error

SORTS = {
    "coins": ("Net worth", ["coins", "money", "net", "networth", "rich", "cash"], "net"),
    "wallet": ("Wallet", ["wallet"], "wallet"),
    "bank": ("Bank", ["bank"], "bank"),
    "level": ("Level", ["level", "levels", "xp", "rank"], "xp"),
    "messages": ("Messages", ["messages", "msgs", "chat", "chatters"], "msgs"),
    "streak": ("Daily streak", ["streak", "daily"], "streak"),
    "items": ("Items owned", ["items", "inventory", "inv"], "items"),
    "giveaways": ("Giveaways won", ["giveaways", "wins", "won", "giveaway"], "won"),
}
ALIASES = {alias: key for key, (_, aliases, _) in SORTS.items() for alias in aliases}
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
PER_PAGE = 8


class Stats(commands.Cog):
    """One leaderboard and one profile that bring together every stat Risk keeps."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def collect(self, guild):
        """Returns {user_id: stats} for every member with any saved stat."""
        economy = self.bot.get_cog("Economy")
        levels = self.bot.get_cog("Levels")
        giveaways = self.bot.get_cog("Giveaway")
        accounts = economy.store.data.get(str(guild.id), {}) if economy else {}
        xp_data = levels.store.data.get(str(guild.id), {}) if levels else {}
        stats = {}
        for uid in set(accounts) | set(xp_data):
            account = accounts.get(uid, {})
            xp_entry = xp_data.get(uid, {})
            wallet, bank = account.get("wallet", 0), account.get("bank", 0)
            xp = xp_entry.get("xp", 0)
            stats[int(uid)] = {
                "wallet": wallet, "bank": bank, "net": wallet + bank,
                "streak": account.get("streak", 0),
                "items": sum(count for count in account.get("inv", {}).values() if count > 0),
                "xp": xp, "level": level_for(xp), "msgs": xp_entry.get("msgs", 0),
                "won": giveaways.won_count(guild.id, int(uid)) if giveaways else 0,
                "entered": giveaways.entered_count(guild.id, int(uid)) if giveaways else 0,
            }
        return stats

    @staticmethod
    def lines(stats):
        coin = "🪙"
        return (
            f"{coin} **{stats['net']:,}** net ({stats['wallet']:,} wallet · {stats['bank']:,} bank)\n"
            f"⭐ Level **{stats['level']}** · {stats['xp']:,} XP · 💬 {stats['msgs']:,} messages\n"
            f"🔥 {stats['streak']} day streak · 🎒 {stats['items']} item{'s' if stats['items'] != 1 else ''} · "
            f"🎉 {stats['won']} won / {stats['entered']} entered"
        )

    @commands.command(name="leaderboard", aliases=["lb", "top", "rich"])
    async def leaderboard(self, ctx, sort: str = "coins", page: int = 1):
        """Shows the top members with all of their stats. Sort by coins, wallet, bank, level, messages, streak, items or giveaways. Usage: !leaderboard level 2"""
        if sort.isdigit():
            sort, page = "coins", int(sort)
        key = ALIASES.get(sort.lower())
        if key is None:
            await ctx.reply("Sort by one of: " + ", ".join(f"`{name}`" for name in SORTS) + ".", mention_author=False)
            return
        label, _, field = SORTS[key]
        everyone = self.collect(ctx.guild)
        ranked = [(uid, s) for uid, s in everyone.items() if ctx.guild.get_member(uid) is not None and s[field] > 0]
        ranked.sort(key=lambda item: (-item[1][field], item[0]))
        if not ranked:
            await ctx.reply(f"Nobody has any {label.lower()} yet.", mention_author=False)
            return
        pages = -(-len(ranked) // PER_PAGE)
        page = max(1, min(page, pages))
        start = (page - 1) * PER_PAGE
        embed = discord.Embed(title=f"🏆 Leaderboard: {label}", color=discord.Color.gold())
        for index, (uid, stats) in enumerate(ranked[start:start + PER_PAGE], start=start + 1):
            member = ctx.guild.get_member(uid)
            name = discord.utils.escape_markdown(member.display_name)
            embed.add_field(name=f"{MEDALS.get(index, f'#{index}')} {name}"[:250], value=self.lines(stats), inline=False)
        mine = next((i for i, (uid, _) in enumerate(ranked, start=1) if uid == ctx.author.id), None)
        embed.set_footer(text=f"Page {page} of {pages} · You are {'#' + str(mine) if mine else 'unranked'} · !leaderboard <{'|'.join(SORTS)}> [page]")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="profile", aliases=["userstats", "pf"])
    async def profile(self, ctx, member: discord.Member = None):
        """Shows every stat Risk has for a member, with their rank in each. Usage: !profile @user"""
        member = member or ctx.author
        everyone = self.collect(ctx.guild)
        stats = everyone.get(member.id)
        if stats is None:
            stats = {"wallet": 0, "bank": 0, "net": 0, "streak": 0, "items": 0, "xp": 0, "level": 0, "msgs": 0, "won": 0, "entered": 0}
        members = [(uid, s) for uid, s in everyone.items() if ctx.guild.get_member(uid) is not None]

        def rank(field):
            if stats[field] <= 0:
                return "unranked"
            return f"#{1 + sum(1 for uid, s in members if s[field] > stats[field])} of {sum(1 for _, s in members if s[field] > 0)}"

        level = stats["level"]
        start, goal = xp_for(level), xp_for(level + 1)
        progress = (stats["xp"] - start) / (goal - start)
        bar = "█" * int(progress * 12) + "░" * (12 - int(progress * 12))
        embed = discord.Embed(title=member.display_name, color=member.color if member.color.value else discord.Color.light_grey())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🪙 Wallet", value=f"{stats['wallet']:,}")
        embed.add_field(name="🏦 Bank", value=f"{stats['bank']:,}")
        embed.add_field(name="💰 Net worth", value=f"{stats['net']:,}\n{rank('net')}")
        embed.add_field(name="⭐ Level", value=f"{level}\n{rank('xp')}")
        embed.add_field(name="✨ XP", value=f"{stats['xp']:,} / {goal:,}")
        embed.add_field(name="💬 Messages", value=f"{stats['msgs']:,}\n{rank('msgs')}")
        embed.add_field(name="🔥 Daily streak", value=f"{stats['streak']} day(s)\n{rank('streak')}")
        embed.add_field(name="🎒 Items", value=str(stats["items"]))
        embed.add_field(name="🎉 Giveaways", value=f"{stats['won']} won\n{stats['entered']} entered")
        embed.add_field(name="Level progress", value=f"`{bar}` {int(progress * 100)}%", inline=False)
        joined = f"<t:{int(member.joined_at.timestamp())}:D>" if member.joined_at else "unknown"
        embed.add_field(name="Joined", value=joined)
        embed.add_field(name="Account created", value=f"<t:{int(member.created_at.timestamp())}:D>")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(Stats(bot))
