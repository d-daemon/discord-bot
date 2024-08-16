import os
import json
import discord
from discord.ext import commands
import asyncpg
import logging
import io
import base64

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

        # Recreate the bot_settings table
        await self.recreate_bot_settings_table()

        # Load cogs, skipping __init__.py, *_data.py, or other non-cog files
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != '__init__.py' and not filename.endswith('_data.py'):
                cog = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog)
                    logging.info(f"Successfully loaded cog: {cog}")
                except Exception as e:
                    logging.error(f"Failed to load {cog}: {e}")

        # Sync commands globally and per guild
        await self.sync_commands()

        # Apply saved personalization settings
        await self.apply_personalization_settings()

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

    async def recreate_bot_settings_table(self):
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("DROP TABLE IF EXISTS bot_settings")
                await conn.execute('''
                    CREATE TABLE bot_settings (
                        key TEXT NOT NULL,
                        value TEXT,
                        guild_id BIGINT NOT NULL,
                        PRIMARY KEY (key, guild_id)
                    )
                ''')
            logging.info("bot_settings table recreated successfully")
        except Exception as e:
            logging.error(f"Error recreating bot_settings table: {str(e)}")

    async def sync_commands(self):
        async with self.db_pool.acquire() as connection:
            guild_ids = await connection.fetch("SELECT guild_id FROM guilds")
            for record in guild_ids:
                guild_id = record['guild_id']
                await self.tree.sync(guild=discord.Object(id=guild_id))
                logging.info(f'Synced commands for guild {guild_id}')
        await self.tree.sync()  # Sync globally as well

    async def apply_personalization_settings(self):
        async with self.db_pool.acquire() as conn:
            global_settings = await conn.fetch("SELECT key, value FROM bot_settings WHERE guild_id IS NULL")
            for setting in global_settings:
                key, value = setting['key'], setting['value']
                if key == 'status':
                    status_map = {
                        'online': discord.Status.online,
                        'idle': discord.Status.idle,
                        'dnd': discord.Status.dnd,
                        'invisible': discord.Status.invisible
                    }
                    await self.change_presence(status=status_map[value])
                elif key == 'activity_type':
                    activity_text = await conn.fetchval("SELECT value FROM bot_settings WHERE key = 'activity_text' AND guild_id IS NULL")
                    if activity_text:
                        activity_map = {
                            'playing': discord.ActivityType.playing,
                            'streaming': discord.ActivityType.streaming,
                            'listening': discord.ActivityType.listening,
                            'watching': discord.ActivityType.watching,
                            'competing': discord.ActivityType.competing
                        }
                        activity = discord.Activity(type=activity_map[value], name=activity_text)
                        await self.change_presence(activity=activity)
                elif key == 'avatar':
                    avatar_bytes = base64.b64decode(value)
                    await self.user.edit(avatar=avatar_bytes)

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name}')
        # Apply server-specific nicknames
        await self.apply_server_nicknames()
        # Sync commands every time the bot starts up
        await self.sync_commands()

    async def apply_server_nicknames(self):
        async with self.db_pool.acquire() as conn:
            nicknames = await conn.fetch("SELECT guild_id, value FROM bot_settings WHERE key = 'nickname'")
            for nickname in nicknames:
                guild = self.get_guild(nickname['guild_id'])
                if guild:
                    try:
                        await guild.me.edit(nick=nickname['value'])
                        logging.info(f"Applied nickname '{nickname['value']}' in guild {guild.name}")
                    except discord.Forbidden:
                        logging.warning(f"Failed to set nickname in guild {guild.name}: Missing permissions")

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
                await connection.execute("DELETE FROM bot_settings WHERE guild_id = $1", guild.id)
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