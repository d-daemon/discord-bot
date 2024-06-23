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

# Initialize bot with intents
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Load cogs
initial_extensions = [
    'cogs.admin',
    'cogs.fun',
    'cogs.info',
    'cogs.moderation',
    'cogs.welcome'
]

async def load_extensions():
    for extension in initial_extensions:
        await bot.load_extension(extension)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

bot.loop.create_task(load_extensions())
bot.run(TOKEN)
