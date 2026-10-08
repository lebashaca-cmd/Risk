import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        """Deletes a specified number of messages. Usage: !clear 10"""
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f'Cleared {amount} messages.', delete_after=5)

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kicks a member from the server. Usage: !kick @user reason"""
        await member.kick(reason=reason)
        await ctx.send(f'Kicked {member.mention}. Reason: {reason}')

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Bans a member from the server. Usage: !ban @user reason"""
        await member.ban(reason=reason)
        await ctx.send(f'Banned {member.mention}. Reason: {reason}')

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int):
        """Unbans a user by their ID. Usage: !unban 123456789"""
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f'Unbanned {user.name}.')

async def setup(bot):
    await bot.add_cog(Moderation(bot))
