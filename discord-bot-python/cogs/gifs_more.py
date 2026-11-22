"""More anime GIF reactions and pictures. Every command asks a free image service, so one that is down just shows the text."""
import random
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error

TIMEOUT = aiohttp.ClientTimeout(total=10)
# Sources tried in order for the picture commands: (url, where the image link sits in the JSON, where the credit sits)
PICTURE_SOURCES = {
    "catboy": [("https://api.catboys.com/img", ("url",), ("artist",)), ("https://nekos.best/api/v2/husbando", ("results", 0, "url"), ("results", 0, "artist_name"))],
    "femboy": [("https://api.nekosia.cat/api/v1/images/shadow?additionalTags=femboy&rating=safe", ("image", "original", "url"), ("attribution", "artist", "username"))],
}


def dig(data, path):
    for key in path:
        data = data[key]
    return data


class GifsMore(commands.Cog, name="GifsMore"):
    """More anime GIF reactions and pictures."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    async def get(self, url):
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers={"User-Agent": "Risk-Discord-Bot"}) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(response.status)
                return await response.json(content_type=None)

    async def gif(self, kind):
        """(gif_url, credit) from nekos.best, then waifu.pics, or (None, None)."""
        try:
            item = (await self.get(f"https://nekos.best/api/v2/{kind}"))["results"][0]
            return item["url"], item.get("anime_name")
        except Exception:
            pass
        try:
            return (await self.get(f"https://api.waifu.pics/sfw/{kind}"))["url"], None
        except Exception:
            return None, None

    async def react(self, ctx, kind, solo, target, member):
        if member is not None and member.id == ctx.author.id:
            member = None
        if member is None and solo is None:
            await ctx.reply("Pick someone else.", mention_author=False)
            return
        line = (target if member is not None else solo).format(a=ctx.author.display_name, b=member.display_name if member else "")
        text = f"{ctx.author.display_name} {line}"
        url, credit = await self.gif(kind)
        if not url:
            await ctx.send(text, allowed_mentions=NO_MENTIONS)
            return
        embed = discord.Embed(description=f"**{text}**", color=discord.Color.light_grey())
        embed.set_image(url=url)
        if credit:
            embed.set_footer(text=credit)
        await ctx.send(embed=embed, allowed_mentions=NO_MENTIONS)

    async def picture(self, ctx, kind, sources):
        for url, image_path, credit_path in sources:
            try:
                data = await self.get(url)
                link = dig(data, image_path)
                try:
                    credit = dig(data, credit_path)
                except Exception:
                    credit = None
                embed = discord.Embed(color=discord.Color.light_grey())
                embed.set_image(url=link)
                if credit:
                    embed.set_footer(text=f"Art by {credit}")
                await ctx.reply(embed=embed, mention_author=False)
                return
            except Exception:
                continue
        await ctx.reply(f"I couldn't get a {kind} picture right now. The image service may be down, try again in a bit.", mention_author=False)

    @commands.command(name="baka")
    @commands.guild_only()
    async def baka(self, ctx, member: discord.Member):
        """Calls someone a baka. Usage: !baka @user"""
        await self.react(ctx, "baka", None, "calls {b} a baka.", member)

    @commands.command(name="feed")
    @commands.guild_only()
    async def feed(self, ctx, member: discord.Member):
        """Feeds someone. Usage: !feed @user"""
        await self.react(ctx, "feed", None, "feeds {b}.", member)

    @commands.command(name="handhold")
    @commands.guild_only()
    async def handhold(self, ctx, member: discord.Member):
        """Holds someone's hand. Usage: !handhold @user"""
        await self.react(ctx, "handhold", None, "holds {b}'s hand.", member)

    @commands.command(name="handshake")
    @commands.guild_only()
    async def handshake(self, ctx, member: discord.Member):
        """Shakes someone's hand. Usage: !handshake @user"""
        await self.react(ctx, "handshake", None, "shakes {b}'s hand.", member)

    @commands.command(name="peck")
    @commands.guild_only()
    async def peck(self, ctx, member: discord.Member):
        """Gives someone a little peck. Usage: !peck @user"""
        await self.react(ctx, "peck", None, "gives {b} a little peck.", member)

    @commands.command(name="shoot")
    @commands.guild_only()
    async def shoot(self, ctx, member: discord.Member):
        """Shoots a finger gun at someone. Usage: !shoot @user"""
        await self.react(ctx, "shoot", None, "shoots a finger gun at {b}.", member)

    @commands.command(name="bored")
    @commands.guild_only()
    async def bored(self, ctx, member: Optional[discord.Member] = None):
        """Shows you are bored, on your own or with someone. Usage: !bored or !bored @user"""
        await self.react(ctx, "bored", "is bored.", "is bored with {b}.", member)

    @commands.command(name="happy")
    @commands.guild_only()
    async def happy(self, ctx, member: Optional[discord.Member] = None):
        """Shows you are happy, on your own or with someone. Usage: !happy or !happy @user"""
        await self.react(ctx, "happy", "is happy.", "is happy with {b}.", member)

    @commands.command(name="lurk")
    @commands.guild_only()
    async def lurk(self, ctx, member: Optional[discord.Member] = None):
        """Lurks quietly, on your own or with someone. Usage: !lurk or !lurk @user"""
        await self.react(ctx, "lurk", "is lurking.", "is lurking next to {b}.", member)

    @commands.command(name="nod")
    @commands.guild_only()
    async def nod(self, ctx, member: Optional[discord.Member] = None):
        """Nods, on your own or with someone. Usage: !nod or !nod @user"""
        await self.react(ctx, "nod", "nods.", "nods at {b}.", member)

    @commands.command(name="nope")
    @commands.guild_only()
    async def nope(self, ctx, member: Optional[discord.Member] = None):
        """Says nope, on your own or with someone. Usage: !nope or !nope @user"""
        await self.react(ctx, "nope", "says nope.", "says nope to {b}.", member)

    @commands.command(name="pout")
    @commands.guild_only()
    async def pout(self, ctx, member: Optional[discord.Member] = None):
        """Pouts, on your own or with someone. Usage: !pout or !pout @user"""
        await self.react(ctx, "pout", "pouts.", "pouts at {b}.", member)

    @commands.command(name="shrug")
    @commands.guild_only()
    async def shrug(self, ctx, member: Optional[discord.Member] = None):
        """Shrugs, on your own or with someone. Usage: !shrug or !shrug @user"""
        await self.react(ctx, "shrug", "shrugs.", "shrugs at {b}.", member)

    @commands.command(name="sleep")
    @commands.guild_only()
    async def sleep(self, ctx, member: Optional[discord.Member] = None):
        """Goes to sleep, on your own or with someone. Usage: !sleep or !sleep @user"""
        await self.react(ctx, "sleep", "falls asleep.", "falls asleep next to {b}.", member)

    @commands.command(name="smile")
    @commands.guild_only()
    async def smile(self, ctx, member: Optional[discord.Member] = None):
        """Smiles, on your own or with someone. Usage: !smile or !smile @user"""
        await self.react(ctx, "smile", "smiles.", "smiles at {b}.", member)

    @commands.command(name="smug")
    @commands.guild_only()
    async def smug(self, ctx, member: Optional[discord.Member] = None):
        """Looks smug, on your own or with someone. Usage: !smug or !smug @user"""
        await self.react(ctx, "smug", "looks smug.", "looks smugly at {b}.", member)

    @commands.command(name="think")
    @commands.guild_only()
    async def think(self, ctx, member: Optional[discord.Member] = None):
        """Thinks hard, on your own or with someone. Usage: !think or !think @user"""
        await self.react(ctx, "think", "is thinking.", "is thinking about {b}.", member)

    @commands.command(name="thumbsup")
    @commands.guild_only()
    async def thumbsup(self, ctx, member: Optional[discord.Member] = None):
        """Gives a thumbs up, on your own or with someone. Usage: !thumbsup or !thumbsup @user"""
        await self.react(ctx, "thumbsup", "gives a thumbs up.", "gives {b} a thumbs up.", member)

    @commands.command(name="yawn")
    @commands.guild_only()
    async def yawn(self, ctx, member: Optional[discord.Member] = None):
        """Yawns, on your own or with someone. Usage: !yawn or !yawn @user"""
        await self.react(ctx, "yawn", "yawns.", "yawns at {b}.", member)

    @commands.command(name="neko")
    async def neko(self, ctx):
        """A random neko picture. Usage: !neko"""
        await self.picture(ctx, "neko", [("https://nekos.best/api/v2/neko", ("results", 0, "url"), ("results", 0, "artist_name"))])

    @commands.command(name="kitsune")
    async def kitsune(self, ctx):
        """A random kitsune (fox person) picture. Usage: !kitsune"""
        await self.picture(ctx, "kitsune", [("https://nekos.best/api/v2/kitsune", ("results", 0, "url"), ("results", 0, "artist_name"))])

    @commands.command(name="waifu")
    async def waifu(self, ctx):
        """A random waifu picture. Usage: !waifu"""
        await self.picture(ctx, "waifu", [("https://nekos.best/api/v2/waifu", ("results", 0, "url"), ("results", 0, "artist_name"))])

    @commands.command(name="husbando")
    async def husbando(self, ctx):
        """A random husbando picture. Usage: !husbando"""
        await self.picture(ctx, "husbando", [("https://nekos.best/api/v2/husbando", ("results", 0, "url"), ("results", 0, "artist_name"))])

    @commands.command(name="catboy")
    async def catboy(self, ctx):
        """A random catboy picture. Usage: !catboy"""
        await self.picture(ctx, "catboy", PICTURE_SOURCES["catboy"])

    @commands.command(name="femboy")
    async def femboy(self, ctx):
        """A random femboy picture (safe-for-work). Usage: !femboy"""
        await self.picture(ctx, "femboy", PICTURE_SOURCES["femboy"])


async def setup(bot):
    await bot.add_cog(GifsMore(bot))
