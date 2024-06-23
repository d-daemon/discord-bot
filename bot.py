import os
import discord
from discord.ext import commands
import json

# Load config
with open('data/config.json') as f:
    config = json.load(f)

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
PREFIX = config['prefix']

# Define intents
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.members = True  # Enable this if your bot needs to access member information
intents.message_content = True  # Enable the message content intent

class MyBot(commands.Bot):
    async def setup_hook(self):
        initial_extensions = [
            'cogs.admin',
            'cogs.fun',
            'cogs.info',
            'cogs.moderation',
            'cogs.welcome'
        ]
        for extension in initial_extensions:
            await self.load_extension(extension)

# Initialize bot with intents
bot = MyBot(command_prefix=PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

bot.run(TOKEN)
