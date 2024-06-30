import discord
from discord.ext import commands
import json

def load_config():
    with open('/app/config/config.json', 'r') as config_file:
        return json.load(config_file)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.welcome_channel_name = self.config.get('welcome_channel', 'general')
        self.goodbye_channel_name = self.config.get('goodbye_channel', 'general')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Sends a welcome message when a new member joins the server."""
        self.config = load_config()  # Reload configuration
        channel = discord.utils.get(member.guild.text_channels, name=self.welcome_channel_name)
        if channel:
            await channel.send(f'Welcome to the server, {member.mention}! We\'re glad to have you here.')

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Sends a message when a member leaves the server."""
        self.config = load_config()  # Reload configuration
        channel = discord.utils.get(member.guild.text_channels, name=self.goodbye_channel_name)
        if channel:
            await channel.send(f'Sad to see you go, {member.mention}. Goodbye!')

async def setup(bot):
    await bot.add_cog(Welcome(bot))
