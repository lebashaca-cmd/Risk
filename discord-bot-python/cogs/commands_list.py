import discord
from discord.ext import commands


class CommandsList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="commands")
    async def commands_list(self, ctx):
        """Shows all commands and what they do. Usage: !commands"""
        prefix = ctx.prefix
        prefixes = self.bot.command_prefix
        if not isinstance(prefixes, (list, tuple)):
            prefixes = [prefixes]

        embed = discord.Embed(
            title="📜 Commands",
            description=f"Prefixes you can use: {' '.join(f'`{p}`' for p in prefixes)}",
            color=discord.Color.blurple(),
        )

        # Group commands by cog; commands with no cog go under "General"
        groups = {}
        for cmd in self.bot.commands:
            if cmd.hidden:
                continue
            name = cmd.cog_name or "General"
            groups.setdefault(name, []).append(cmd)

        for group_name in sorted(groups):
            lines = []
            for cmd in sorted(groups[group_name], key=lambda c: c.name):
                desc = cmd.short_doc or "No description."
                lines.append(f"`{prefix}{cmd.name}` — {desc}")
            value = "\n".join(lines)
            if len(value) > 1024:
                value = value[:1020] + "..."
            embed.add_field(name=group_name, value=value, inline=False)

        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommandsList(bot))
