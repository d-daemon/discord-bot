import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = discord.utils.get(member.guild.text_channels, name='general')  # Replace 'general' with your channel name
        if channel:
            await channel.send(f'Welcome to the server, {member.mention}!')

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        channel = discord.utils.get(member.guild.text_channels, name='general')  # Replace 'general' with your channel name
        if channel:
            await channel.send(f'{member.mention} has left the server. Goodbye!')

def setup(bot):
    bot.add_cog(Welcome(bot))
