import discord
from discord.ext import commands

SECTIONS = [
    (
        "1. Who this covers",
        "This policy covers the Risk Discord bot and its website. Risk is run by an individual, not a company. "
        "For any question or request below, use the support server linked on the website.",
    ),
    (
        "2. What Risk saves",
        "Risk saves only what its features need, tied to Discord user, server, channel and role IDs: coin balances, "
        "items and cooldowns (economy); XP, message counts and level settings (levels); per-server settings that admins "
        "choose, such as prefix, switched-off commands, auto-moderation and welcome messages; to-do lists, AFK notes and "
        "reminder text; warnings with the reason, moderator and time; welcome, log, ticket and sticky-message settings; "
        "and ticket records, including staff notes. Risk does not keep a copy of your general chat messages.",
    ),
    (
        "3. Messages Risk reads",
        "Risk reads messages in servers it is in so it can notice commands and count messages for levels. It saves "
        "the count, not the text. For the snipe commands it holds the last deleted and last edited message of each "
        "channel in memory only. These are replaced by newer ones and cleared when the bot restarts.",
    ),
    (
        "4. Tickets and server logs",
        "When a ticket closes, Risk posts a text transcript (messages, names and attachment links) to the staff log "
        "channel that server chose. Server logs post things like deleted and edited messages, joins and leaves, role, "
        "nickname and voice changes to the channel that server's admins choose. That content then lives in Discord, "
        "under that server's control. Risk itself keeps only the last 200 log summaries per server, in memory.",
    ),
    (
        "5. Outside services",
        "Some commands send what you type to other services to get an answer: AI questions go to Groq; weather "
        "locations to wttr.in; words to dictionaryapi.dev; QR text to qrserver.com; topics to Wikipedia; profile "
        "lookups to api.nerve.wtf and the platform being looked up; and GIF, image, joke, advice and trivia commands "
        "to nekos.best, waifu.pics, thecatapi.com, dog.ceo, randomfox.ca, icanhazdadjoke.com, adviceslip.com and "
        "opentdb.com. Don't send passwords or private details to these commands. Each service has its own policy.",
    ),
    (
        "6. The website",
        "The public pages show the bot's status and command list. They set no cookies, use no analytics or ads, and "
        "store nothing in your browser. Its host keeps ordinary request logs (IP address, time and page), and the "
        "pages load fonts from Google Fonts, which sees your IP address. The public status feed lists, for up to 30 "
        "servers the bot is in, the server's name, icon and member count. Server owners can ask to be left out.",
    ),
    (
        "7. The dashboard",
        "Signing in to the dashboard uses Discord's OAuth2. Risk asks for your Discord ID, name and avatar, and the list of "
        "servers you are in with your permissions there (the identify and guilds scopes). It uses these only to work out "
        "which servers you can manage, and asks Discord to revoke the access token right after sign-in. A random session "
        "cookie (HttpOnly, 6 hours) keeps you signed in, and the site holds your name, avatar and managed-server list in "
        "memory until you sign out, the session ends or the site restarts. Settings you save are stored with the bot like "
        "any other setting, and each save is noted in that server's logs with your name.",
    ),
    (
        "8. How long data is kept",
        "Saved data stays on the bot's host until it is reset or deleted. Admins can reset XP with the level "
        "commands, clear warnings with the moderation commands, and you can clear your own to-do list. If Risk "
        "leaves a server, that server's saved data stays on the host until it is deleted on request.",
    ),
    (
        "9. Your choices",
        "You can ask what Risk has saved about you, or ask for it to be deleted, through the support server. "
        "Include your Discord user ID. Server admins can switch features off, exclude channels from XP and logs, "
        "or remove the bot. Removing the bot stops all collection from that server.",
    ),
    (
        "10. Sharing and security",
        "Risk does not sell your data or use it for advertising. It is shared only as described above, or when "
        "the law requires it. Saved files and secret keys are kept on the bot's host and not published, but no "
        "system is perfectly secure, so avoid putting sensitive information into any command.",
    ),
    (
        "11. Age",
        "Discord requires users to be at least 13, or the minimum age in their country. Risk is not meant for "
        "anyone younger and does not knowingly collect data from them.",
    ),
    (
        "12. Changes",
        "This policy may change as Risk gains features. The date at the bottom shows the latest version, and "
        "continuing to use Risk means you accept the current one.",
    ),
]
UPDATED = "November 1, 2026"


class Privacy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="privacy")
    async def privacy(self, ctx):
        """Shows what data Risk saves and how it is used. Usage: !privacy"""
        pages, current, size = [], [], 0
        for name, text in SECTIONS:
            if current and size + len(name) + len(text) > 4500:
                pages.append(current)
                current, size = [], 0
            current.append((name, text))
            size += len(name) + len(text)
        pages.append(current)
        for index, page in enumerate(pages):
            embed = discord.Embed(
                title="🔒 Privacy Policy" if index == 0 else None,
                description="What Risk saves, why, and your choices." if index == 0 else None,
                color=discord.Color.dark_grey(),
            )
            for name, text in page:
                embed.add_field(name=name, value=text, inline=False)
            if index == len(pages) - 1:
                embed.set_footer(text=f"Last updated: {UPDATED}")
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Privacy(bot))
