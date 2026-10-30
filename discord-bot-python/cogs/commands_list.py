import discord
from discord.ext import commands

CATEGORY_BY_COG = {
    "CommandsList": "Info",
    "Uptime": "Info",
    "Website": "Info",
    "TOS": "Info",
    "BotTime": "Info",
    "Utility": "Utility",
    "UtilityTools": "Utility",
    "Moderation": "Moderation",
    "ModerationTools": "Moderation",
    "GiveRole": "Moderation",
    "Fun": "Fun",
    "Economy": "Economy",
    "Tickets": "Tickets",
    "ServerLogs": "Server logs",
    "Welcome": "Welcome",
    "AIChat": "AI",
    "Nerve": "Lookups",
}
ORDER = ["Info", "Utility", "Moderation", "Fun", "Economy", "Tickets", "Server logs", "Welcome", "AI", "Lookups"]
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
        embed = self.cog.overview(view.prefix, self.categories) if choice == "Overview" else self.cog.category_embed(view.prefix, choice, self.categories[choice])
        await interaction.response.edit_message(embed=embed, view=view)


class CommandsView(discord.ui.View):
    def __init__(self, cog, author_id, prefix, categories):
        super().__init__(timeout=180)
        self.author_id, self.prefix = author_id, prefix
        self.message = None
        self.add_item(CategorySelect(cog, categories))

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

    def category_embed(self, prefix, name, items):
        lines = []
        for cmd in items:
            alias = f" (also {', '.join(f'`{a}`' for a in cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"`{prefix}{cmd.name}`{alias}: {cmd.short_doc or 'No description.'}")
        embed = discord.Embed(title=f"{name} commands", color=discord.Color.light_grey())
        for index, page in enumerate(chunk(lines)):
            embed.add_field(name="​" if index else f"{len(items)} commands", value=page, inline=False)
        return embed

    @commands.command(name="commands")
    async def commands_list(self, ctx):
        """Shows all commands and what they do. Usage: !commands"""
        categories = self.gather()
        prefix = ctx.prefix or "!"
        view = CommandsView(self, ctx.author.id, prefix, categories)
        view.message = await ctx.send(embed=self.overview(prefix, categories), view=view)


async def setup(bot):
    await bot.add_cog(CommandsList(bot))
