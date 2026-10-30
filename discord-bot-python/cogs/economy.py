import asyncio
import random
import time

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error, human_duration, parse_amount
from utils.store import JsonStore

CURRENCY = "🪙"
DAILY_BASE = 500
DAILY_STREAK_BONUS = 50
DAILY_COOLDOWN = 20 * 3600
DAILY_RESET = 48 * 3600
WORK_COOLDOWN = 3600
MAX_BALANCE = 10 ** 12
SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]
WORK_LINES = [
    "You fixed a stranger's Wi-Fi", "You walked a very large dog", "You sold lemonade by the road",
    "You debugged a mystery crash", "You delivered pizzas all night", "You moderated a chaotic chat",
    "You painted a fence", "You tuned someone's guitar",
]


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("economy")
        self.lock = asyncio.Lock()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    def account(self, guild_id, user_id):
        guild = self.store.data.setdefault(str(guild_id), {})
        return guild.setdefault(str(user_id), {"wallet": 0, "bank": 0, "last_daily": 0, "last_work": 0, "streak": 0})

    def money(self, amount):
        return f"{CURRENCY} {amount:,}"

    def resolve_bet(self, text, wallet):
        amount = parse_amount(text, wallet)
        if amount is None or amount <= 0:
            return None, "Give a positive amount, or `all` or `half`."
        if amount > wallet:
            return None, f"You only have {self.money(wallet)} in your wallet."
        return amount, None

    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx, member: discord.Member = None):
        """Shows a wallet and bank balance. Usage: !balance @user"""
        member = member or ctx.author
        acc = self.account(ctx.guild.id, member.id)
        embed = discord.Embed(title=f"{member.display_name}'s balance", color=discord.Color.gold())
        embed.add_field(name="Wallet", value=self.money(acc["wallet"]))
        embed.add_field(name="Bank", value=self.money(acc["bank"]))
        embed.add_field(name="Total", value=self.money(acc["wallet"] + acc["bank"]))
        await ctx.send(embed=embed)

    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claims your daily coins. Keep a streak for a bonus. Usage: !daily"""
        async with self.lock:
            acc = self.account(ctx.guild.id, ctx.author.id)
            now = int(time.time())
            wait = acc["last_daily"] + DAILY_COOLDOWN - now
            if wait > 0:
                await ctx.reply(f"Come back in {human_duration(wait)}.", mention_author=False)
                return
            acc["streak"] = acc["streak"] + 1 if now - acc["last_daily"] <= DAILY_RESET else 1
            reward = DAILY_BASE + DAILY_STREAK_BONUS * min(acc["streak"] - 1, 20)
            acc["wallet"] = min(MAX_BALANCE, acc["wallet"] + reward)
            acc["last_daily"] = now
            self.store.save()
        await ctx.reply(f"You claimed {self.money(reward)}. Streak: **{acc['streak']}** day(s).", mention_author=False)

    @commands.command(name="work")
    async def work(self, ctx):
        """Works a shift for coins once an hour. Usage: !work"""
        async with self.lock:
            acc = self.account(ctx.guild.id, ctx.author.id)
            now = int(time.time())
            wait = acc["last_work"] + WORK_COOLDOWN - now
            if wait > 0:
                await ctx.reply(f"You're tired. Rest for {human_duration(wait)}.", mention_author=False)
                return
            reward = random.randint(100, 400)
            acc["wallet"] = min(MAX_BALANCE, acc["wallet"] + reward)
            acc["last_work"] = now
            self.store.save()
        await ctx.reply(f"{random.choice(WORK_LINES)} and earned {self.money(reward)}.", mention_author=False)

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx, amount: str):
        """Moves coins from your wallet to your bank. Usage: !deposit 500"""
        async with self.lock:
            acc = self.account(ctx.guild.id, ctx.author.id)
            value, error = self.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            acc["wallet"] -= value
            acc["bank"] += value
            self.store.save()
        await ctx.reply(f"Deposited {self.money(value)}.", mention_author=False)

    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx, amount: str):
        """Moves coins from your bank to your wallet. Usage: !withdraw 500"""
        async with self.lock:
            acc = self.account(ctx.guild.id, ctx.author.id)
            value = parse_amount(amount, acc["bank"])
            if value is None or value <= 0:
                await ctx.reply("Give a positive amount, or `all` or `half`.", mention_author=False)
                return
            if value > acc["bank"]:
                await ctx.reply(f"You only have {self.money(acc['bank'])} in the bank.", mention_author=False)
                return
            acc["bank"] -= value
            acc["wallet"] += value
            self.store.save()
        await ctx.reply(f"Withdrew {self.money(value)}.", mention_author=False)

    @commands.command(name="give", aliases=["pay"])
    async def give(self, ctx, member: discord.Member, amount: str):
        """Gives some of your wallet coins to someone. Usage: !give @user 100"""
        if member.bot or member.id == ctx.author.id:
            await ctx.reply("Pick another person.", mention_author=False)
            return
        async with self.lock:
            sender = self.account(ctx.guild.id, ctx.author.id)
            value, error = self.resolve_bet(amount, sender["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            receiver = self.account(ctx.guild.id, member.id)
            sender["wallet"] -= value
            receiver["wallet"] = min(MAX_BALANCE, receiver["wallet"] + value)
            self.store.save()
        await ctx.reply(f"Gave {self.money(value)} to {member.mention}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="bet", aliases=["gamble"])
    async def bet(self, ctx, amount: str, side: str = "heads"):
        """Bets on a coin flip. Win to double it. Usage: !bet 100 heads"""
        side = side.lower()
        if side not in ("heads", "tails", "h", "t"):
            await ctx.reply("Pick `heads` or `tails`.", mention_author=False)
            return
        async with self.lock:
            acc = self.account(ctx.guild.id, ctx.author.id)
            value, error = self.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            result = random.choice(["heads", "tails"])
            won = result[0] == side[0]
            acc["wallet"] += value if won else -value
            acc["wallet"] = min(acc["wallet"], MAX_BALANCE)
            self.store.save()
        text = f"It landed on **{result}**. You {'won' if won else 'lost'} {self.money(value)}."
        await ctx.reply(text, mention_author=False)

    @commands.command(name="slots")
    async def slots(self, ctx, amount: str):
        """Spins the slot machine. Usage: !slots 100"""
        async with self.lock:
            acc = self.account(ctx.guild.id, ctx.author.id)
            value, error = self.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
            if reels[0] == reels[1] == reels[2]:
                multiplier = 10 if reels[0] == "7️⃣" else 5
            elif len(set(reels)) == 2:
                multiplier = 1.5
            else:
                multiplier = 0
            payout = int(value * multiplier)
            acc["wallet"] = min(MAX_BALANCE, acc["wallet"] - value + payout)
            self.store.save()
        outcome = f"You won {self.money(payout)}!" if payout > value else ("You got your bet back." if payout == value else f"You lost {self.money(value)}.")
        await ctx.reply(f"🎰 | {' '.join(reels)} |\n{outcome}", mention_author=False)

    @commands.command(name="leaderboard", aliases=["lb", "rich"])
    async def leaderboard(self, ctx):
        """Shows the richest members of this server. Usage: !leaderboard"""
        accounts = self.store.data.get(str(ctx.guild.id), {})
        ranked = sorted(accounts.items(), key=lambda item: item[1]["wallet"] + item[1]["bank"], reverse=True)[:10]
        ranked = [(uid, acc) for uid, acc in ranked if acc["wallet"] + acc["bank"] > 0]
        if not ranked:
            await ctx.reply("Nobody has any coins yet. Try `!daily`.", mention_author=False)
            return
        lines = []
        for index, (uid, acc) in enumerate(ranked, start=1):
            member = ctx.guild.get_member(int(uid))
            name = discord.utils.escape_markdown(member.display_name) if member else f"User {uid}"
            lines.append(f"**{index}.** {name}: {self.money(acc['wallet'] + acc['bank'])}")
        await ctx.send(embed=discord.Embed(title="Richest members", description="\n".join(lines), color=discord.Color.gold()))

    @commands.command(name="addmoney")
    @commands.has_permissions(administrator=True)
    async def addmoney(self, ctx, member: discord.Member, amount: int):
        """Adds or removes coins from someone's wallet. Usage: !addmoney @user 1000"""
        if abs(amount) > MAX_BALANCE:
            await ctx.reply("That amount is too large.", mention_author=False)
            return
        async with self.lock:
            acc = self.account(ctx.guild.id, member.id)
            acc["wallet"] = max(0, min(MAX_BALANCE, acc["wallet"] + amount))
            self.store.save()
        await ctx.reply(f"{member.mention} now has {self.money(acc['wallet'])} in their wallet.", mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(Economy(bot))
