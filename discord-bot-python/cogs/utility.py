import discord
from discord.ext import commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="userinfo")
    async def userinfo(self, ctx, member: discord.Member = None):
        """Shows information about a user. Usage: !userinfo @user"""
        member = member or ctx.author

        embed = discord.Embed(title=f"User Info - {member}", color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.display_name, inline=True)
        embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"), inline=True)
        embed.set_footer(text=f"Requested by {ctx.author}")

        await ctx.send(embed=embed)

    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx):
        """Shows information about the server."""
        guild = ctx.guild

        embed = discord.Embed(title=f"Server Info - {guild.name}", color=discord.Color.green())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="Owner", value=guild.owner, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="Verification Level", value=guild.verification_level, inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
