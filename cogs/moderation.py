import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='kick', help='Kicks a member from the server with an optional reason.')
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """
        Kicks a member from the server.
        Parameters:
            member (discord.Member): The member to kick.
            reason (str, optional): The reason for the kick.
        """
        await member.kick(reason=reason)
        reason_message = f" for {reason}" if reason else ""
        await ctx.send(f'Kicked {member.mention}{reason_message}')

    @commands.command(name='ban', help='Bans a member from the server with an optional reason.')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """
        Bans a member from the server.
        Parameters:
            member (discord.Member): The member to ban.
            reason (str, optional): The reason for the ban.
        """
        await member.ban(reason=reason)
        reason_message = f" for {reason}" if reason else ""
        await ctx.send(f'Banned {member.mention}{reason_message}')

async def setup(bot):
    await bot.add_cog(Moderation(bot))
