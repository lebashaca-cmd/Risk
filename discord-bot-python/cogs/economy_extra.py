import random
import time

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error, human_duration

ITEMS = {
    "rod": {"name": "Fishing rod", "price": 2000, "info": "Needed for `!fish`."},
    "pickaxe": {"name": "Pickaxe", "price": 5000, "info": "Needed for `!mine`."},
    "padlock": {"name": "Padlock", "price": 3000, "info": "Stops the next `!rob` against you, then breaks."},
}
COOLDOWNS = {
    "weekly": 7 * 86400, "monthly": 30 * 86400, "beg": 60, "crime": 2 * 3600,
    "rob": 3600, "fish": 300, "mine": 600,
}
FISH = [("an old boot", 5), ("a tiny minnow", 40), ("a trout", 120), ("a salmon", 250), ("a golden carp", 600), ("a treasure chest", 1500)]
ORES = [("some stone", 30), ("copper ore", 90), ("iron ore", 200), ("gold ore", 450), ("a diamond", 1200)]
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = {1: "A", 11: "J", 12: "Q", 13: "K"}


def card_text(card):
    return f"{RANKS.get(card[0], card[0])}{card[1]}"


def hand_value(hand):
    total = sum(min(rank, 10) for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == 1)
    while aces and total + 10 <= 21:
        total += 10
        aces -= 1
    return total


class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet):
        super().__init__(timeout=90)
        self.cog, self.ctx, self.bet = cog, ctx, bet
        self.deck = [(rank, suit) for rank in range(1, 14) for suit in SUITS] * 2
        random.shuffle(self.deck)
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.message = None
        self.done = False

    def embed(self, reveal=False, footer=None, color=None):
        embed = discord.Embed(title="🃏 Blackjack", color=color or discord.Color.dark_green())
        embed.add_field(name=f"Your hand ({hand_value(self.player)})", value=" ".join(card_text(c) for c in self.player), inline=False)
        if reveal:
            embed.add_field(name=f"Dealer ({hand_value(self.dealer)})", value=" ".join(card_text(c) for c in self.dealer), inline=False)
        else:
            embed.add_field(name="Dealer", value=f"{card_text(self.dealer[0])} ❔", inline=False)
        embed.add_field(name="Bet", value=self.cog.eco.money(self.bet))
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def interaction_check(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game.", ephemeral=True)
            return False
        return True

    async def settle(self, outcome):
        """outcome: blackjack, win, push, lose. Returns the finished embed."""
        self.done = True
        for item in self.children:
            item.disabled = True
        payout = {"blackjack": self.bet + self.bet * 3 // 2, "win": self.bet * 2, "push": self.bet, "lose": 0}[outcome]
        eco = self.cog.eco
        async with eco.lock:
            acc = eco.account(self.ctx.guild.id, self.ctx.author.id)
            acc["wallet"] = min(10 ** 12, acc["wallet"] + payout)
            eco.store.save()
            wallet = acc["wallet"]
        self.cog.playing.discard((self.ctx.guild.id, self.ctx.author.id))
        texts = {
            "blackjack": f"Blackjack! You win {eco.money(payout - self.bet)}.",
            "win": f"You win {eco.money(self.bet)}.",
            "push": "Push. Your bet is returned.",
            "lose": f"You lose {eco.money(self.bet)}.",
        }
        colors = {"blackjack": discord.Color.gold(), "win": discord.Color.green(), "push": discord.Color.light_grey(), "lose": discord.Color.red()}
        self.stop()
        return self.embed(reveal=True, footer=f"{texts[outcome]} Wallet: {eco.money(wallet)}", color=colors[outcome])

    async def dealer_turn(self):
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        mine, theirs = hand_value(self.player), hand_value(self.dealer)
        if theirs > 21 or mine > theirs:
            return "win"
        return "push" if mine == theirs else "lose"

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        if self.done:
            return
        self.player.append(self.deck.pop())
        if hand_value(self.player) > 21:
            embed = await self.settle("lose")
            await interaction.response.edit_message(embed=embed, view=self)
        elif hand_value(self.player) == 21:
            embed = await self.settle(await self.dealer_turn())
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction, button):
        if self.done:
            return
        embed = await self.settle(await self.dealer_turn())
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.done:
            return
        embed = await self.settle("lose")
        embed.set_footer(text="Out of time, so the bet is lost. " + (embed.footer.text or ""))
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass


class EconomyExtra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playing = set()

    @property
    def eco(self):
        return self.bot.get_cog("Economy")

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

    # Helpers (call with the economy lock held).
    @staticmethod
    def cooldown_left(acc, name):
        return acc.setdefault("cd", {}).get(name, 0) + COOLDOWNS[name] - int(time.time())

    @staticmethod
    def start_cooldown(acc, name):
        acc.setdefault("cd", {})[name] = int(time.time())

    @staticmethod
    def pay(acc, amount):
        acc["wallet"] = max(0, min(10 ** 12, acc["wallet"] + amount))

    async def timed_reward(self, ctx, name, reward, title):
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            wait = self.cooldown_left(acc, name)
            if wait > 0:
                await ctx.reply(f"Come back in {human_duration(wait)}.", mention_author=False)
                return
            self.start_cooldown(acc, name)
            self.pay(acc, reward)
            eco.store.save()
            wallet = acc["wallet"]
        embed = discord.Embed(title=title, description=f"You claimed {eco.money(reward)}.", color=discord.Color.gold())
        embed.add_field(name="Wallet", value=eco.money(wallet))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="weekly")
    async def weekly(self, ctx):
        """Claims your weekly coins. Usage: !weekly"""
        await self.timed_reward(ctx, "weekly", 3000, "Weekly reward")

    @commands.command(name="monthly")
    async def monthly(self, ctx):
        """Claims your monthly coins. Usage: !monthly"""
        await self.timed_reward(ctx, "monthly", 15000, "Monthly reward")

    @commands.command(name="beg")
    async def beg(self, ctx):
        """Begs for spare change. Usage: !beg"""
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            wait = self.cooldown_left(acc, "beg")
            if wait > 0:
                await ctx.reply(f"Give people a moment. Try again in {human_duration(wait)}.", mention_author=False)
                return
            self.start_cooldown(acc, "beg")
            gift = random.randint(20, 100) if random.random() < 0.7 else 0
            self.pay(acc, gift)
            eco.store.save()
        text = f"A kind stranger gave you {eco.money(gift)}." if gift else "Everyone walked past you."
        await ctx.reply(embed=discord.Embed(description=text, color=discord.Color.gold()), mention_author=False)

    @commands.command(name="crime")
    async def crime(self, ctx):
        """Attempts a risky crime for big coins, or a fine. Usage: !crime"""
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            wait = self.cooldown_left(acc, "crime")
            if wait > 0:
                await ctx.reply(f"Lay low for {human_duration(wait)}.", mention_author=False)
                return
            self.start_cooldown(acc, "crime")
            if random.random() < 0.55:
                amount = random.randint(300, 900)
                self.pay(acc, amount)
                text = random.choice(["You hacked a vending machine", "You sold fake concert tickets", "You pulled off a museum prank"])
                embed = discord.Embed(title="Crime paid", description=f"{text} and made {eco.money(amount)}.", color=discord.Color.green())
            else:
                fine = min(acc["wallet"], random.randint(200, 600))
                self.pay(acc, -fine)
                embed = discord.Embed(title="Caught", description=f"You were caught and fined {eco.money(fine)}.", color=discord.Color.red())
            eco.store.save()
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="rob")
    async def rob(self, ctx, member: discord.Member):
        """Tries to steal coins from someone's wallet. Usage: !rob @user"""
        eco = self.eco
        if member.bot or member.id == ctx.author.id:
            await ctx.reply("Pick another member.", mention_author=False)
            return
        async with eco.lock:
            me = eco.account(ctx.guild.id, ctx.author.id)
            them = eco.account(ctx.guild.id, member.id)
            wait = self.cooldown_left(me, "rob")
            if wait > 0:
                await ctx.reply(f"You're being watched. Try again in {human_duration(wait)}.", mention_author=False)
                return
            if me["wallet"] < 200:
                await ctx.reply("You need at least 200 coins in your wallet to risk a robbery.", mention_author=False)
                return
            if them["wallet"] < 200:
                await ctx.reply(f"{member.display_name} has nothing worth stealing.", mention_author=False, allowed_mentions=NO_MENTIONS)
                return
            self.start_cooldown(me, "rob")
            inventory = them.setdefault("inv", {})
            if inventory.get("padlock", 0) > 0:
                inventory["padlock"] -= 1
                eco.store.save()
                await ctx.reply(f"{member.display_name} had a padlock. It broke, and you got nothing.", mention_author=False, allowed_mentions=NO_MENTIONS)
                return
            if random.random() < 0.4:
                stolen = max(1, int(them["wallet"] * random.uniform(0.1, 0.3)))
                self.pay(them, -stolen)
                self.pay(me, stolen)
                embed = discord.Embed(title="Robbery worked", description=f"You took {eco.money(stolen)} from {member.display_name}.", color=discord.Color.green())
            else:
                fine = min(me["wallet"], random.randint(100, 300))
                self.pay(me, -fine)
                self.pay(them, fine)
                embed = discord.Embed(title="Robbery failed", description=f"You paid {member.display_name} {eco.money(fine)} for the trouble.", color=discord.Color.red())
            eco.store.save()
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    async def gather(self, ctx, name, item, table, verb, title):
        eco = self.eco
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            if acc.setdefault("inv", {}).get(item, 0) < 1:
                await ctx.reply(f"You need a {ITEMS[item]['name'].lower()}. Buy one with `!buy {item}`.", mention_author=False)
                return
            wait = self.cooldown_left(acc, name)
            if wait > 0:
                await ctx.reply(f"Try again in {human_duration(wait)}.", mention_author=False)
                return
            self.start_cooldown(acc, name)
            weights = [max(1, 100 - index * 20) for index in range(len(table))]
            found, value = random.choices(table, weights=weights)[0]
            value = int(value * random.uniform(0.8, 1.3))
            self.pay(acc, value)
            eco.store.save()
        await ctx.reply(embed=discord.Embed(title=title, description=f"You {verb} {found} worth {eco.money(value)}.", color=discord.Color.gold()), mention_author=False)

    @commands.command(name="fish")
    async def fish(self, ctx):
        """Goes fishing with a rod. Usage: !fish"""
        await self.gather(ctx, "fish", "rod", FISH, "caught", "🎣 Fishing")

    @commands.command(name="mine")
    async def mine(self, ctx):
        """Mines for ore with a pickaxe. Usage: !mine"""
        await self.gather(ctx, "mine", "pickaxe", ORES, "dug up", "⛏️ Mining")

    @commands.command(name="shop")
    async def shop(self, ctx):
        """Lists items you can buy. Usage: !shop"""
        eco = self.eco
        lines = [f"**{item['name']}** (`{key}`): {eco.money(item['price'])}\n{item['info']}" for key, item in ITEMS.items()]
        embed = discord.Embed(title="Shop", description="\n\n".join(lines), color=discord.Color.gold())
        embed.set_footer(text="Buy with !buy <item>. Sell back for half with !sell <item>.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="buy")
    async def buy(self, ctx, item: str, amount: int = 1):
        """Buys an item from the shop. Usage: !buy padlock 2"""
        eco = self.eco
        key = item.lower()
        if key not in ITEMS:
            await ctx.reply("That item isn't in the shop. See `!shop`.", mention_author=False)
            return
        if not 1 <= amount <= 50:
            await ctx.reply("Buy between 1 and 50 at a time.", mention_author=False)
            return
        cost = ITEMS[key]["price"] * amount
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            if acc["wallet"] < cost:
                await ctx.reply(f"That costs {eco.money(cost)} and you have {eco.money(acc['wallet'])}.", mention_author=False)
                return
            acc["wallet"] -= cost
            inventory = acc.setdefault("inv", {})
            inventory[key] = inventory.get(key, 0) + amount
            eco.store.save()
        await ctx.reply(f"Bought {amount} × **{ITEMS[key]['name']}** for {eco.money(cost)}.", mention_author=False)

    @commands.command(name="sell")
    async def sell(self, ctx, item: str, amount: int = 1):
        """Sells an item back for half its price. Usage: !sell rod"""
        eco = self.eco
        key = item.lower()
        if key not in ITEMS or amount < 1:
            await ctx.reply("Name an item you own, like `!sell rod`.", mention_author=False)
            return
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            inventory = acc.setdefault("inv", {})
            if inventory.get(key, 0) < amount:
                await ctx.reply("You don't have that many.", mention_author=False)
                return
            inventory[key] -= amount
            value = ITEMS[key]["price"] // 2 * amount
            self.pay(acc, value)
            eco.store.save()
        await ctx.reply(f"Sold {amount} × **{ITEMS[key]['name']}** for {eco.money(value)}.", mention_author=False)

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, member: discord.Member = None):
        """Shows the items someone owns. Usage: !inventory @user"""
        member = member or ctx.author
        acc = self.eco.account(ctx.guild.id, member.id)
        owned = {key: count for key, count in acc.get("inv", {}).items() if count > 0 and key in ITEMS}
        text = "\n".join(f"{count} × {ITEMS[key]['name']}" for key, count in owned.items()) or "Nothing yet. See `!shop`."
        await ctx.reply(embed=discord.Embed(title=f"{member.display_name}'s inventory", description=text, color=discord.Color.gold()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.command(name="roulette")
    async def roulette(self, ctx, amount: str, bet: str):
        """Bets on a roulette spin: red, black, even, odd, low, high or a number 0-36. Usage: !roulette 500 red"""
        eco = self.eco
        choice = bet.lower()
        valid_words = {"red", "black", "green", "even", "odd", "low", "high"}
        if choice not in valid_words and not (choice.isdigit() and 0 <= int(choice) <= 36):
            await ctx.reply("Bet on `red`, `black`, `green`, `even`, `odd`, `low`, `high` or a number from 0 to 36.", mention_author=False)
            return
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            value, error = eco.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            spin = random.randint(0, 36)
            color = "green" if spin == 0 else "red" if spin in RED else "black"
            if choice.isdigit():
                multiplier = 35 if int(choice) == spin else 0
            elif choice == "green":
                multiplier = 35 if spin == 0 else 0
            else:
                wins = {
                    "red": color == "red", "black": color == "black",
                    "even": spin != 0 and spin % 2 == 0, "odd": spin % 2 == 1,
                    "low": 1 <= spin <= 18, "high": 19 <= spin <= 36,
                }[choice]
                multiplier = 1 if wins else 0
            change = value * multiplier if multiplier else -value
            self.pay(acc, change)
            eco.store.save()
            wallet = acc["wallet"]
        emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}[color]
        embed = discord.Embed(
            title=f"🎡 {emoji} {spin}",
            description=f"You won {eco.money(change)}." if change > 0 else f"You lost {eco.money(-change)}.",
            color=discord.Color.green() if change > 0 else discord.Color.red(),
        )
        embed.set_footer(text=f"Bet: {choice}. Wallet: {eco.money(wallet)}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="blackjack", aliases=["bj"])
    async def blackjack(self, ctx, amount: str):
        """Plays blackjack against the dealer with buttons. Usage: !blackjack 500"""
        eco = self.eco
        key = (ctx.guild.id, ctx.author.id)
        if key in self.playing:
            await ctx.reply("Finish your current blackjack game first.", mention_author=False)
            return
        async with eco.lock:
            acc = eco.account(ctx.guild.id, ctx.author.id)
            value, error = eco.resolve_bet(amount, acc["wallet"])
            if error:
                await ctx.reply(error, mention_author=False)
                return
            acc["wallet"] -= value
            eco.store.save()
        self.playing.add(key)
        view = BlackjackView(self, ctx, value)
        if hand_value(view.player) == 21:
            outcome = "push" if hand_value(view.dealer) == 21 else "blackjack"
            embed = await view.settle(outcome)
            await ctx.reply(embed=embed, view=view, mention_author=False)
            return
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)


async def setup(bot):
    await bot.add_cog(EconomyExtra(bot))
