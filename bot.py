import discord
from discord.ext import commands
import json

# Load config
with open('data/config.json') as f:
    config = json.load(f)

TOKEN = config['token']
PREFIX = config['prefix']

bot = commands.Bot(command_prefix=PREFIX)

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
