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
intents.members = True  # Add this if your bot needs to access member information

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Load cogs
initial_extensions = [
    'cogs.admin',
    'cogs.fun',
    'cogs.info',
    'cogs.moderation',
    'cogs.welcome'
]

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

bot.run(TOKEN)
