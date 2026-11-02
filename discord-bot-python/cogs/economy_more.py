import asyncio
import random
import time

import discord
from discord.ext import commands, tasks

from cogs.economy_extra import COOLDOWNS, ITEMS
from utils.helpers import NO_MENTIONS, explain_error, human_duration
from utils.store import JsonStore

TICKET_PRICE = 100
MAX_TICKETS = 50
LOTTERY_EVERY = 24 * 3600
HEIST_WINDOW = 45
HEIST_MIN_CREW = 2
HEIST_COOLDOWN = 3 * 3600
GIFT_MAX = 1_000_000
ANIMALS = [("a rabbit", 60), ("a duck", 120), ("a boar", 300), ("a deer", 550), ("a bear", 1100), ("a golden stag", 2200)]
SCRATCH = [("💎", 1000), ("🍀", 300), ("⭐", 100), ("🍒", 50), ("🍋", 20)]


class HighLowView(discord.ui.View):
    def __init__(self, cog, ctx, bet):
        super().__init__(timeout=60)
        self.cog, self.ctx, self.bet = cog, ctx, bet
        self.card = random.randint(1, 13)
        self.streak = 0
        self.message = None
        self.done = False

    @staticmethod
    def name(card):
        return {1: "A", 11: "J", 12: "Q", 13: "K"}.get(card, str(card))

    def embed(self, note=None, color=None):
        embed = discord.Embed(title="🔼 Higher or lower", color=color or discord.Color.blurple())
        embed.add_field(name="Card", value=f"**{self.name(self.card)}**")
        embed.add_field(name="Streak", value=str(self.streak))
        embed.add_field(name="Cash out now", value=self.cog.eco.money(self.payout()))
        if note:
            embed.set_footer(text=note)
        return embed

    def payout(self):
        return int(self.bet * (1 + 0.6 * self.streak))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This game isn't yours.", ephemeral=True)
            return False
        return not self.done

    async def finish(self, interaction, note, color, payout):
        self.done = True
        self.stop()
        for child in self.children:
            child.disabled = True
        eco = self.cog.eco
        async with eco.lock:
            acc = eco.account(self.ctx.guild.id, self.ctx.author.id)
            acc["wallet"] = min(10 ** 12, acc["wallet"] + payout)
            eco.store.save()
        self.cog.playing.discard((self.ctx.guild.id, self.ctx.author.id))
        await interaction.response.edit_message(embed=self.embed(note, color), view=self)

    async def guess(self, interaction, higher):
        nxt = random.randint(1, 13)
        if nxt == self.card:
            self.card = nxt
            await interaction.response.edit_message(embed=self.embed("Same card. No change, guess again."), view=self)
            return
        if (nxt > self.card) == higher:
            self.card = nxt
            self.streak += 1
            await interaction.response.edit_message(embed=self.embed(f"Correct, it was {self.name(nxt)}."), view=self)
            return
        self.card = nxt
        await self.finish(interaction, f"Wrong, it was {self.name(nxt)}. You lost your bet.", discord.Color.red(), 0)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.primary, emoji="🔼")
    async def higher(self, interaction, button):
        await self.guess(interaction, True)

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.primary, emoji="🔽")
    async def lower(self, interaction, button):
        await self.guess(interaction, False)

    @discord.ui.button(label="Cash out", style=discord.ButtonStyle.success, emoji="💰")
    async def cash(self, interaction, button):
        await self.finish(interaction, f"You cashed out {self.payout():,}.", discord.Color.green(), self.payout())

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        eco = self.cog.eco
        async with eco.lock:
            acc = eco.account(self.ctx.guild.id, self.ctx.author.id)
            acc["wallet"] = min(10 ** 12, acc["wallet"] + self.payout())
            eco.store.save()
        self.cog.playing.discard((self.ctx.guild.id, self.ctx.author.id))
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=self.embed("Timed out. You were cashed out.", discord.Color.light_grey()), view=self)
            except discord.HTTPException:
                pass


class HeistView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=HEIST_WINDOW)
        self.cog, self.ctx = cog, ctx
        self.crew = {ctx.author.id}

    @discord.ui.button(label="Join the crew", style=discord.ButtonStyle.danger, emoji="🕶️")
    async def join(self, interaction, button):
        if interaction.user.id in self.crew:
            await interaction.response.send_message("You're already in the crew.", ephemeral=True)
            return
        if len(self.crew) >= 10:
            await interaction.response.send_message("The crew is full.", ephemeral=True)
            return
        eco = self.cog.eco
        async with eco.lock:
            wallet = eco.account(interaction.guild_id, interaction.user.id)["wallet"]
        if wallet < 200:
            await interaction.response.send_message("You need at least 200 coins in your wallet to join.", ephemeral=True)
            return
        self.crew.add(interaction.user.id)
        await interaction.response.send_message("You're in. Stay quiet.", ephemeral=True)


class EconomyMore(commands.Cog):
    """Lottery, gifts, higher or lower, scratch cards, dice bets, heists and hunting."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("lottery")
        self.playing = set()
        self.heists = {}

    @property
    def eco(self):
        return self.bot.get_cog("Economy")

    async def cog_load(self):
        COOLDOWNS.setdefault("hunt", 450)
        self.lottery_loop.start()

    def cog_unload(self):
        self.lottery_loop.cancel()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if self.eco is None:
            await ctx.reply("The economy isn't loaded right now.", mention_author=False)
            return False
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Lottery
    def pot(self, guild_id):
        data = self.store.data.setdefault(str(guild_id), {"tickets": {}, "next": int(time.time()) + LOTTERY_EVERY, "last": None})
        data.setdefault("tickets", {})
        data.setdefault("next", int(time.time()) + LOTTERY_EVERY)
        data.setdefault("last", None)
        return data

    @staticmethod
    def ticket_total(data):
        return sum(data["tickets"].values())

    async def run_draw(self, guild, data, channel=None):
        total = self.ticket_total(data)
        if total == 0:
            data["next"] = int(time.time()) + LOTTERY_EVERY
            self.store.save()
            return None
        holders = [uid for uid in data["tickets"] if guild.get_member(int(uid))]
        if not holders:
            data["tickets"] = {}
            data["next"] = int(time.time()) + LOTTERY_EVERY
            self.store.save()
            return None
        prize = int(total * TICKET_PRICE * 0.9)
        winner = random.choices(holders, weights=[data["tickets"][u] for u in holders])[0]
        eco = self.eco
        async with eco.lock:
            acc = eco.account(guild.id, int(winner))
            acc["wallet"] = min(10 ** 12, acc["wallet"] + prize)
            eco.store.save()
        data["last"] = {"winner": int(winner), "prize": prize, "at": int(time.time())}
        data["tickets"] = {}
        data["next"] = int(time.time()) + LOTTERY_EVERY
        self.store.save()
        text = f"🎟️ <@{winner}> won the lottery and took home {eco.money(prize)}!"
        if channel is not None:
            try:
                await channel.send(text, allowed_mentions=discord.AllowedMentions(users=[discord.Object(int(winner))]))
            except discord.HTTPException:
                pass
        return int(winner), prize

    @tasks.loop(minutes=5)
    async def lottery_loop(self):
        now = int(time.time())
        for guild_id, data in list(self.store.data.items()):
            if data.get("next", now + 1) > now:
                continue
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue
            channel = guild.system_channel
            if channel is not None and not channel.permissions_for(guild.me).send_messages:
                channel = None
            await self.run_draw(guild, data, channel)

    @lottery_loop.before_loop
    async def before_lottery(self):
        await self.bot.wait_until_ready()

    @commands.group(name="lottery", aliases=["lotto"], invoke_without_command=True)
    async def lottery(self, ctx):
        """Shows the lottery pot and your tickets. Actions: buy, info, draw. Usage: !lottery"""
        await self.lottery_info(ctx)

    @lottery.command(name="info", aliases=["pot"])
    async def lottery_info(self, ctx):
        """Shows the pot, the next draw and the last winner. Usage: !lottery info"""
        data = self.pot(ctx.guild.id)
        total = self.ticket_total(data)
        mine = data["tickets"].get(str(ctx.author.id), 0)
        embed = discord.Embed(title="🎟️ Lottery", color=discord.Color.gold())
        embed.add_field(name="Pot", value=self.eco.money(int(total * TICKET_PRICE * 0.9)))
        embed.add_field(name="Tickets sold", value=str(total))
        embed.add_field(name="Your tickets", value=f"{mine} ({(mine / total * 100) if total else 0:.1f}% chance)")
        embed.add_field(name="Next draw", value=f"<t:{data['next']}:R>")
        last = data["last"]
        if last:
            embed.add_field(name="Last winner", value=f"<@{last['winner']}> won {self.eco.money(last['prize'])}")
        embed.set_footer(text=f"Tickets cost {TICKET_PRICE} each. Buy with !lottery buy <amount>. 10% of the pot is kept by the house.")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @lottery.command(name="buy")
    async def lottery_buy(self, ctx, amount: int = 1):
        """Buys lottery tickets for 100 coins each (up to 50 per person). Usage: !lottery buy 5"""
        if amount < 1:
            await ctx.reply("Buy at least 1 ticket.", mention_author=False)
            return
        data = self.pot(ctx.guild.id)
        key = str(ctx.author.id)
        eco = self.eco
        async with eco.lock:
            have = data["tickets"].get(key, 0)
            if have + amount > MAX_TICKETS:
                await ctx.reply(f"You can hold {MAX_TICKETS} tickets at most. You have {have}.", mention_author=False)
                return
            acc = eco.account(ctx.guild.id, ctx.author.id)
            cost = amount * TICKET_PRICE
            if acc["wallet"] < cost:
                await ctx.reply(f"{amount} ticket(s) cost {eco.money(cost)} and you have {eco.money(acc['wallet'])}.", mention_author=False)
                return
            acc["wallet"] -= cost
            data["tickets"][key] = have + amount
            eco.store.save()
            self.store.save()
        await ctx.reply(f"🎟️ Bought {amount} ticket(s) for {eco.money(cost)}. You hold {have + amount}.", mention_author=False)

    @lottery.command(name="draw")
    @commands.has_permissions(manage_guild=True)
    async def lottery_draw(self, ctx):
        """Draws the lottery now (staff only). Usage: !lottery draw"""
        data = self.pot(ctx.guild.id)
        result = await self.run_draw(ctx.guild, data, ctx.channel)
        if result is None:
            await ctx.reply("Nobody has bought a ticket, so there is nothing to draw.", mention_author=False)

    # Gifts and net worth
    @commands.command(name="gift")
    async def gift(self, ctx, member: discord.Member, item: str, amount: int = 1):
        """Gives one of your shop items to another member. Usage: !gift @user padlock 1"""
        key = item.lower()
        if key not in ITEMS:
            await ctx.reply("That item isn't in the shop. See `!shop`.", mention_author=False)
            return
        if member.bot or member.id == ctx.author.id:
            await ctx.reply("Pick another real member.", mention_author=False)
            return
        if not 1 <= amount <= 50:
            await ctx.reply("Gift between 1 and 50 at a time.", mention_author=False)
            return
        eco = self.eco
        async with eco.lock:
            mine = eco.account(ctx.guild.id, ctx.author.id).setdefault("inv", {})
            if mine.get(key, 0) < amount:
                await ctx.reply(f"You only have {mine.get(key, 0)} × {ITEMS[key]['name']}.", mention_author=False)
                return
            theirs = eco.account(ctx.guild.id, member.id).setdefault("inv", {})
            mine[key] -= amount
            theirs[key] = theirs.get(key, 0) + amount
            eco.store.save()
        await ctx.reply(f"🎁 You gave {member.display_name} {amount} × **{ITEMS[key]['name']}**.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="networth", aliases=["nw"])
    async def networth(self, ctx, member: discord.Member = None):
        """Shows wallet, bank and item value added together. Usage: !networth @user"""
        member = member or ctx.author
        eco = self.eco
        acc = eco.account(ctx.guild.id, member.id)
        items = sum(ITEMS[k]["price"] // 2 * n for k, n in acc.get("inv", {}).items() if k in ITEMS and n > 0)
        total = acc["wallet"] + acc["bank"] + items
        embed = discord.Embed(title=f"{member.display_name}'s net worth", color=discord.Color.gold())
        embed.add_field(name="Wallet", value=eco.money(acc["wallet"]))
        embed.add_field(name="Bank", value=eco.money(acc["bank"]))
        embed.add_field(name="Items (sell value)", value=eco.money(items))
        embed.add_field(name="Total", value=eco.money(total), inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # Games
    @commands.command(name="highlow", aliases=["hl"])
    async def highlow(self, ctx, amount: str):
        """Guesses higher or lower to build a streak, then cash out. Usage: !highlow 200"""
        key = (ctx.guild.id, ctx.author.id)
        if key in self.playing:
            await ctx.reply("Finish your current game first.", mention_author=False)
            return
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            bet, error = eco.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            acc["wallet"] -= bet
            eco.store.save()
        self.playing.add(key)
        view = HighLowView(self, ctx, bet)
        view.message = await ctx.reply(embed=view.embed("Guess if the next card is higher or lower."), view=view, mention_author=False)

    @commands.command(name="scratch", aliases=["scratchcard"])
    async def scratch(self, ctx, amount: str = "50"):
        """Scratches a card with 3 hidden boxes. Match symbols to win. Usage: !scratch 50"""
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            bet, error = eco.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            symbols = [s for s, _ in SCRATCH]
            roll = random.random()
            if roll < 0.04:
                symbol = random.choices(symbols, weights=[1, 3, 6, 10, 15])[0]
                boxes, multiplier = [symbol] * 3, dict(SCRATCH)[symbol] / 10
            elif roll < 0.30:
                symbol = random.choice(symbols)
                other = random.choice([s for s in symbols if s != symbol])
                boxes, multiplier = [symbol, symbol, other], 1.0
                random.shuffle(boxes)
            else:
                boxes, multiplier = random.sample(symbols, 3), 0
            payout = int(bet * multiplier)
            acc["wallet"] += payout - bet
            eco.store.save()
            wallet = acc["wallet"]
        shown = " ".join(f"||{b}||" for b in boxes)
        if multiplier == 0:
            result, color = "No match. You lost your bet.", discord.Color.red()
        elif multiplier == 1.0:
            result, color = "Two match. You got your bet back.", discord.Color.light_grey()
        else:
            result, color = f"Three match! You won {eco.money(payout)}.", discord.Color.green()
        embed = discord.Embed(title="🎫 Scratch card", description=f"{shown}\n{result}", color=color)
        embed.add_field(name="Wallet", value=eco.money(wallet))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="dicebet", aliases=["diceroll"])
    async def dicebet(self, ctx, amount: str, guess: int):
        """Bets on the number a die will land on. A correct guess pays 5 to 1. Usage: !dicebet 100 4"""
        if not 1 <= guess <= 6:
            await ctx.reply("Guess a number from 1 to 6.", mention_author=False)
            return
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            bet, error = eco.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            roll = random.randint(1, 6)
            if roll == guess:
                acc["wallet"] += bet * 5
                text, color = f"🎲 It landed on **{roll}**. You won {eco.money(bet * 5)}!", discord.Color.green()
            else:
                acc["wallet"] -= bet
                text, color = f"🎲 It landed on **{roll}**. You lost {eco.money(bet)}.", discord.Color.red()
            eco.store.save()
        await ctx.reply(embed=discord.Embed(description=text, color=color), mention_author=False)

    # Heist
    @commands.command(name="heist")
    async def heist(self, ctx):
        """Starts a bank heist that others can join for 45 seconds. Usage: !heist"""
        guild_id = ctx.guild.id
        if guild_id in self.heists:
            await ctx.reply("A heist is already being planned here.", mention_author=False)
            return
        eco = self.eco
        async with eco.lock:
            acc = eco.account(guild_id, ctx.author.id)
            left = acc.setdefault("cd", {}).get("heist", 0) + HEIST_COOLDOWN - int(time.time())
            if left > 0:
                await ctx.reply(f"The police are watching you. Try again in {human_duration(left)}.", mention_author=False)
                return
            if acc["wallet"] < 200:
                await ctx.reply("You need at least 200 coins in your wallet to plan a heist.", mention_author=False)
                return
            acc["cd"]["heist"] = int(time.time())
            eco.store.save()
        view = HeistView(self, ctx)
        self.heists[guild_id] = view
        embed = discord.Embed(title="🕶️ Bank heist", description=f"{ctx.author.mention} is planning a heist. Press the button to join in the next {HEIST_WINDOW} seconds. At least {HEIST_MIN_CREW} people are needed.", color=discord.Color.dark_red())
        message = await ctx.send(embed=embed, view=view, allowed_mentions=NO_MENTIONS)
        try:
            await asyncio.sleep(HEIST_WINDOW)
        finally:
            self.heists.pop(guild_id, None)
            view.stop()
            for child in view.children:
                child.disabled = True
        crew = list(view.crew)
        if len(crew) < HEIST_MIN_CREW:
            await message.edit(embed=discord.Embed(title="🕶️ Heist called off", description="Not enough people joined.", color=discord.Color.light_grey()), view=view)
            return
        success = random.random() < min(0.75, 0.3 + 0.08 * len(crew))
        lines = []
        async with eco.lock:
            if success:
                loot = random.randint(800, 1800) * len(crew)
                share = loot // len(crew)
                for uid in crew:
                    eco.account(guild_id, uid)["wallet"] += share
                    lines.append(f"<@{uid}> +{share:,}")
                title, color = "🕶️ Heist succeeded!", discord.Color.green()
                description = f"The crew got away with {eco.money(loot)}, split {len(crew)} ways."
            else:
                for uid in crew:
                    acc = eco.account(guild_id, uid)
                    fine = min(acc["wallet"], max(100, int(acc["wallet"] * 0.2)))
                    acc["wallet"] -= fine
                    lines.append(f"<@{uid}> -{fine:,}")
                title, color = "🚔 Heist failed", discord.Color.red()
                description = "The police caught the crew. Everyone paid a fine."
            eco.store.save()
        embed = discord.Embed(title=title, description=description + "\n" + "\n".join(lines[:15]), color=color)
        await message.edit(embed=embed, view=view)

    # Hunting
    @commands.command(name="hunt")
    async def hunt(self, ctx):
        """Hunts animals with a rifle for coins. Usage: !hunt"""
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            if acc.setdefault("inv", {}).get("rifle", 0) < 1:
                await ctx.reply("You need a hunting rifle. Buy one with `!buy rifle`.", mention_author=False)
                return
            cd = acc.setdefault("cd", {})
            left = cd.get("hunt", 0) + COOLDOWNS.get("hunt", 450) - int(time.time())
            if left > 0:
                await ctx.reply(f"The animals are hiding. Try again in {human_duration(left)}.", mention_author=False)
                return
            cd["hunt"] = int(time.time())
            if random.random() < 0.25:
                text = "You missed every shot and came home with nothing."
            else:
                weights = [max(1, 100 - i * 18) for i in range(len(ANIMALS))]
                animal, value = random.choices(ANIMALS, weights=weights)[0]
                value = int(value * random.uniform(0.8, 1.3))
                acc["wallet"] = min(10 ** 12, acc["wallet"] + value)
                text = f"You hunted {animal} worth {eco.money(value)}."
            eco.store.save()
        await ctx.reply(embed=discord.Embed(title="🏹 Hunting", description=text, color=discord.Color.dark_green()), mention_author=False)


async def setup(bot):
    await bot.add_cog(EconomyMore(bot))
