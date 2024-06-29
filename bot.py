import os
import json
import discord
from discord.ext import commands
import asyncpg

class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, token, database_url, config):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.token = token
        self.database_url = database_url
        self.config = config
        self.db_pool = None

    async def setup_hook(self):
        # Load cogs, skipping __init__.py or other non-cog files
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != '__init__.py':  # Ensure __init__.py is not loaded
                cog = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog)
                    print(f"Successfully loaded cog: {cog}")
                except Exception as e:
                    print(f"Failed to load {cog}: {e}")

        # Connect to the database
        self.db_pool = await self.create_db_pool()
    
    async def create_db_pool(self):
        try:
            pool = await asyncpg.create_pool(self.database_url)
            print("Database connection established")
            return pool
        except Exception as e:
            print(f"Error connecting to the database: {str(e)}")
            return None

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

    async def start_bot(self):
        await self.start(self.token)

if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True  # Enable this if your bot needs to access member information
    intents.message_content = True
    intents.messages = True
    intents.presences = False
    intents.typing = False

    with open('config/config.json') as config_file:
        config = json.load(config_file)

    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    DATABASE_URL = os.getenv('DATABASE_URL')

    bot = MyBot(command_prefix=config['prefix'], intents=intents, token=TOKEN, database_url=DATABASE_URL, config=config)
    bot.run(TOKEN)
