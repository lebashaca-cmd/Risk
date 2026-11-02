import discord
from discord.ext import commands

CATEGORY_BY_COG = {
    "CommandsList": "Info",
    "Uptime": "Info",
    "Website": "Info",
    "TOS": "Info",
    "Privacy": "Info",
    "BotTime": "Info",
    "Utility": "Utility",
    "UtilityTools": "Utility",
    "UtilityExtra": "Utility",
    "UtilityMore": "Utility",
    "Moderation": "Moderation",
    "ModerationTools": "Moderation",
    "ModerationMore": "Moderation",
    "AutoMod": "Moderation",
    "GiveRole": "Moderation",
    "Fun": "Fun",
    "FunExtra": "Fun",
    "FunMore": "Fun",
    "Economy": "Economy",
    "EconomyExtra": "Economy",
    "EconomyMore": "Economy",
    "Levels": "Levels",
    "Stats": "Levels",
    "Community": "Community",
    "CommunityExtra": "Community",
    "Dashboard": "Info",
    "Giveaway": "Community",
    "Tickets": "Tickets",
    "TicketTools": "Tickets",
    "ServerLogs": "Server logs",
    "LogTools": "Server logs",
    "Welcome": "Welcome",
    "AIChat": "AI",
    "Nerve": "Lookups",
}
ORDER = ["Info", "Utility", "Moderation", "Fun", "Economy", "Levels", "Community", "Tickets", "Server logs", "Welcome", "AI", "Lookups"]
HIDDEN_PREFIX_COMMANDS = {"help"}


def chunk(lines, limit=1000):
    pages, current = [], ""
    for line in lines:
        if current and len(current) + len(line) + 1 > limit:
            pages.append(current)
            current = ""
        current += ("\n" if current else "") + line
    if current:
        pages.append(current)
    return pages


class CategorySelect(discord.ui.Select):
    def __init__(self, cog, categories):
        options = [discord.SelectOption(label="Overview", value="Overview", description="All categories", emoji="📜")]
        options += [discord.SelectOption(label=name, value=name, description=f"{len(items)} commands") for name, items in categories.items()]
        super().__init__(placeholder="Pick a category", options=options[:25])
        self.cog = cog
        self.categories = categories

    async def callback(self, interaction):
        view = self.view
        if interaction.user.id != view.author_id:
            await interaction.response.send_message("Run `!commands` to get your own.", ephemeral=True)
            return
        choice = self.values[0]
        if choice == "Overview":
            view.pages = [self.cog.overview(view.prefix, self.categories)]
        else:
            view.pages = self.cog.category_embeds(view.prefix, choice, self.categories[choice])
        view.index = 0
        view.refresh()
        await interaction.response.edit_message(embed=view.pages[0], view=view)


class CommandsView(discord.ui.View):
    def __init__(self, cog, author_id, prefix, categories):
        super().__init__(timeout=180)
        self.author_id, self.prefix = author_id, prefix
        self.message = None
        self.pages = []
        self.index = 0
        self.add_item(CategorySelect(cog, categories))
        self.refresh()

    def refresh(self):
        many = len(self.pages) > 1
        self.previous.disabled = not many or self.index == 0
        self.next.disabled = not many or self.index >= len(self.pages) - 1

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Run `!commands` to get your own.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, row=1)
    async def previous(self, interaction, button):
        self.index = max(0, self.index - 1)
        self.refresh()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction, button):
        self.index = min(len(self.pages) - 1, self.index + 1)
        self.refresh()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class CommandsList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def prefixes(self):
        value = self.bot.command_prefix
        if callable(value):
            return ['!', '?', ',']
        return list(value) if isinstance(value, (list, tuple)) else [value]

    def gather(self):
        groups = {}
        for cmd in self.bot.commands:
            if cmd.hidden or cmd.name in HIDDEN_PREFIX_COMMANDS:
                continue
            label = CATEGORY_BY_COG.get(cmd.cog_name or "", cmd.cog_name or "Info")
            groups.setdefault(label, []).append(cmd)
        ordered = {}
        for name in sorted(groups, key=lambda n: (ORDER.index(n) if n in ORDER else len(ORDER), n)):
            ordered[name] = sorted(groups[name], key=lambda c: c.name)
        return ordered

    def overview(self, prefix, categories):
        total = sum(len(v) for v in categories.values())
        embed = discord.Embed(
            title="Commands",
            description=f"{total} commands. Prefixes: {' '.join(f'`{p}`' for p in self.prefixes())}\nPick a category below.",
            color=discord.Color.light_grey(),
        )
        for name, items in categories.items():
            sample = ", ".join(f"`{c.name}`" for c in items[:6]) + (" ..." if len(items) > 6 else "")
            embed.add_field(name=f"{name} ({len(items)})", value=sample[:1000], inline=False)
        return embed

    def category_embeds(self, prefix, name, items):
        """Splits a category into embeds that each stay well under Discord's 6000 character limit."""
        lines = []
        for cmd in items:
            alias = f" (also {', '.join(f'`{a}`' for a in cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"`{prefix}{cmd.name}`{alias}: {cmd.short_doc or 'No description.'}")
        embeds, fields, size = [], [], 0
        for page in chunk(lines):
            if fields and size + len(page) > 4200:
                embeds.append(fields)
                fields, size = [], 0
            fields.append(page)
            size += len(page)
        embeds.append(fields)
        total = len(embeds)
        result = []
        for number, group in enumerate(embeds, start=1):
            embed = discord.Embed(title=f"{name} commands", color=discord.Color.light_grey())
            for index, page in enumerate(group):
                embed.add_field(name=f"{len(items)} commands" if number == 1 and index == 0 else "\u200b", value=page, inline=False)
            if total > 1:
                embed.set_footer(text=f"Page {number} of {total}")
            result.append(embed)
        return result

    def category_embed(self, prefix, name, items):
        return self.category_embeds(prefix, name, items)[0]

    @commands.command(name="commands")
    async def commands_list(self, ctx):
        """Shows all commands and what they do. Usage: !commands"""
        categories = self.gather()
        prefix = ctx.prefix or "!"
        view = CommandsView(self, ctx.author.id, prefix, categories)
        view.pages = [self.overview(prefix, categories)]
        view.refresh()
        view.message = await ctx.send(embed=view.pages[0], view=view)


async def setup(bot):
    await bot.add_cog(CommandsList(bot))
