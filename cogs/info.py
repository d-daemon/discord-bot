import discord
from discord.ext import commands

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='userinfo', help='Displays information about a user.')
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author  # If no member is specified, show info about the message author
        embed = discord.Embed(title=f'User Info - {member}', color=discord.Color.blue())
        embed.add_field(name='ID', value=member.id, inline=True)
        embed.add_field(name='Name', value=member.display_name, inline=True)
        embed.add_field(name='Created At', value=member.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        embed.add_field(name='Joined At', value=member.joined_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
