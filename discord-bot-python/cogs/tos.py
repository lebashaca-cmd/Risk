import discord
from discord.ext import commands

SECTIONS = [
    (
        "1. Acceptance",
        "By joining or using this server, its bot, or its tickets, you agree to these terms. "
        "If you don't agree, please leave the server.",
    ),
    (
        "2. Discord Rules",
        "You must follow Discord's Terms of Service and Community Guidelines at all times. "
        "You must be at least 13 years old, or the minimum age required in your country.",
    ),
    (
        "3. Respect Everyone",
        "No harassment, bullying, hate speech, discrimination, threats, or doxxing. "
        "Disagreements are fine, personal attacks are not.",
    ),
    (
        "4. Content",
        "No NSFW, gore, or illegal content. No malware, token loggers, scams, phishing links, "
        "or pirated material.",
    ),
    (
        "5. Spam & Advertising",
        "No spam, mass pings, or flooding. No advertising, self-promotion, or server invites "
        "(including by DM) without staff permission.",
    ),
    (
        "6. Bot Usage",
        "Don't abuse, exploit, or try to crash the bot. AI answers can be wrong, so don't rely on "
        "them for anything important, and don't use the bot to produce harmful content.",
    ),
    (
        "7. Tickets & Logs",
        "Tickets are private between you and staff. Staff can read them, and a transcript is saved "
        "to a staff-only log channel when a ticket closes. Don't open tickets to troll or spam.",
    ),
    (
        "8. Moderation",
        "Staff may warn, mute, kick, or ban at their discretion. Staff decisions are final, but you "
        "can appeal through a ticket. Using alt accounts to evade a ban results in a permanent ban.",
    ),
    (
        "9. Changes",
        "These terms may change at any time without notice. Continuing to use the server means you "
        "accept the current version.",
    ),
]


class TOS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="tos")
    async def tos(self, ctx):
        """Shows the server Terms of Service. Usage: ,tos"""
        embed = discord.Embed(
            title="📜 Terms of Service",
            description="Please read and follow these rules while you're here.",
            color=discord.Color.dark_grey(),
        )
        for name, text in SECTIONS:
            embed.add_field(name=name, value=text, inline=False)
        embed.set_footer(text="Last updated: October 10, 2026")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TOS(bot))
