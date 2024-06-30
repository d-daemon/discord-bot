import os
import json
import discord
from discord.ext import commands
import asyncpg
import logging

logging.basicConfig(level=logging.INFO)

class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, token, database_url, config_path):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.token = token
        self.database_url = database_url
        self.config_path = config_path
        self.db_pool = None

        with open(self.config_path, 'r') as config_file:
            self.config = json.load(config_file)

    async def setup_hook(self):
        # Connect to the database
        self.db_pool = await self.create_db_pool()

        # Load cogs, skipping __init__.py or other non-cog files
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != '__init__.py':
                cog = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog)
                    logging.info(f"Successfully loaded cog: {cog}")
                except Exception as e:
                    logging.error(f"Failed to load {cog}: {e}")

        # Sync commands globally and per guild
        await self.sync_commands()

    async def create_db_pool(self):
        try:
            pool = await asyncpg.create_pool(self.database_url)
            async with pool.acquire() as connection:
                await connection.execute('''
                    CREATE TABLE IF NOT EXISTS guilds (
                        guild_id BIGINT PRIMARY KEY
                    )
                ''')
            logging.info("Database connection established")
            return pool
        except Exception as e:
            logging.error(f"Error connecting to the database: {str(e)}")
            return None

    async def sync_commands(self):
        async with self.db_pool.acquire() as connection:
            guild_ids = await connection.fetch("SELECT guild_id FROM guilds")
            for record in guild_ids:
                guild_id = record['guild_id']
                await self.tree.sync(guild=discord.Object(id=guild_id))
                logging.info(f'Synced commands for guild {guild_id}')
        await self.tree.sync()  # Sync globally as well

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name}')
        # Sync commands every time the bot starts up
        await self.sync_commands()

    async def on_guild_join(self, guild):
        try:
            async with self.db_pool.acquire() as connection:
                await connection.execute("INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild.id)
                # Ensure commands are synced immediately upon joining a guild
                await self.tree.sync(guild=discord.Object(id=guild.id))
                logging.info(f'Joined new guild: {guild.name} (ID: {guild.id})')
        except Exception as e:
            logging.error(f"Failed to add guild {guild.id} to database: {e}")

    async def on_guild_remove(self, guild):
        try:
            async with self.db_pool.acquire() as connection:
                await connection.execute("DELETE FROM guilds WHERE guild_id = $1", guild.id)
                logging.info(f'Removed from guild: {guild.name} (ID: {guild.id})')
        except Exception as e:
            logging.error(f"Failed to remove guild {guild.id} from database: {e}")

    async def start_bot(self):
        await self.start(self.token)

if __name__ == "__main__":
    intents = discord.Intents.all()

    config_path = 'config/config.json'
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    DATABASE_URL = os.getenv('DATABASE_URL')

    bot = MyBot(command_prefix=config['prefix'], intents=intents, token=TOKEN, database_url=DATABASE_URL, config_path=config_path)
    bot.run(TOKEN)
