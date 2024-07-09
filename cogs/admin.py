import discord
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='addrole', help='Adds a specified role to a specified member.')
    @commands.has_permissions(manage_roles=True)
    async def addrole(self, ctx, member: discord.Member, role: discord.Role):
        """Adds a role to a member."""
        await member.add_roles(role)
        await ctx.send(f'Added {role.mention} to {member.mention}')

    @commands.command(name='removerole', help='Removes a specified role from a specified member.')
    @commands.has_permissions(manage_roles=True)
    async def removerole(self, ctx, member: discord.Member, role: discord.Role):
        """Removes a role from a member."""
        await member.remove_roles(role)
        await ctx.send(f'Removed {role.mention} from {member.mention}')

async def setup(bot):
    await bot.add_cog(Admin(bot))
