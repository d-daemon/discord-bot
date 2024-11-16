"""bot.py"""
import os
import json
import logging
import base64
from typing import Optional
import discord
from discord.ext import commands
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MyBot(commands.Bot):
    def __init__(self, command_prefix, intents, token, database_url, config_path):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.token = token
        self.database_url = database_url
        self.config_path = config_path
        self.db_pool: Optional[asyncpg.Pool] = None

        with open(self.config_path, 'r') as config_file:
            self.config = json.load(config_file)

    async def setup_hook(self) -> None:
        """Initialize the bot's database and load cogs."""
        try:
            # Initialize database connection
            self.db_pool = await self.create_db_pool()
            if not self.db_pool:
                logger.error("Failed to create database pool. Bot cannot start.")
                return

            # Initialize database tables
            await self.initialize_database()

            # Sync existing guilds
            await self.sync_guilds()

            # Load cogs
            await self.load_all_cogs()

            # Apply personalization settings
            await self.apply_personalization_settings()

        except Exception as e:
            logger.error(f"Error in setup_hook: {str(e)}", exc_info=True)
            raise

    async def create_db_pool(self) -> Optional[asyncpg.Pool]:
        """Create and return the database connection pool."""
        try:
            return await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20
            )
        except Exception as e:
            logger.error(f"Failed to create database pool: {str(e)}", exc_info=True)
            return None

    async def initialize_database(self) -> None:
        """Initialize all necessary database tables."""
        try:
            async with self.db_pool.acquire() as conn:
                # Create guilds table if it doesn't exist
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS guilds (
                        guild_id BIGINT PRIMARY KEY,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                ''')

                # Create bot_settings table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS bot_settings (
                        key TEXT NOT NULL,
                        value TEXT,
                        guild_id BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (key, guild_id)
                    )
                ''')

            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {str(e)}", exc_info=True)
            raise

    async def sync_guilds(self) -> None:
        """Sync all current guilds with the database."""
        try:
            current_guild_ids = {guild.id for guild in self.guilds}
            
            async with self.db_pool.acquire() as conn:
                # Get existing guild IDs from database
                db_guild_records = await conn.fetch("SELECT guild_id, is_active FROM guilds")
                db_guild_ids = {record['guild_id'] for record in db_guild_records}
                
                # Add new guilds
                new_guilds = current_guild_ids - db_guild_ids
                if new_guilds:
                    await conn.executemany(
                        "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO UPDATE SET is_active = TRUE",
                        [(guild_id,) for guild_id in new_guilds]
                    )
                    logger.info(f"Added {len(new_guilds)} new guilds to database")

                # Mark guilds as inactive if they're in DB but bot is no longer in them
                inactive_guilds = db_guild_ids - current_guild_ids
                if inactive_guilds:
                    await conn.executemany(
                        "UPDATE guilds SET is_active = FALSE WHERE guild_id = $1",
                        [(guild_id,) for guild_id in inactive_guilds]
                    )
                    logger.info(f"Marked {len(inactive_guilds)} guilds as inactive")

                # Reactivate guilds if they were previously marked inactive
                await conn.executemany(
                    "UPDATE guilds SET is_active = TRUE WHERE guild_id = $1",
                    [(guild_id,) for guild_id in current_guild_ids]
                )

            # Sync commands for all active guilds
            await self.sync_commands()
            
        except Exception as e:
            logger.error(f"Failed to sync guilds: {str(e)}", exc_info=True)
            raise

    async def load_all_cogs(self) -> None:
        """Load all cogs from the cogs directory."""
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith(('__', '_')) and not filename.endswith('_data.py'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    logger.info(f"Successfully loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {str(e)}", exc_info=True)

    async def sync_commands(self) -> None:
        """Sync commands for all active guilds."""
        try:
            async with self.db_pool.acquire() as conn:
                active_guilds = await conn.fetch("SELECT guild_id FROM guilds WHERE is_active = TRUE")
                
                for record in active_guilds:
                    guild_id = record['guild_id']
                    try:
                        await self.tree.sync(guild=discord.Object(id=guild_id))
                        logger.info(f'Synced commands for guild {guild_id}')
                    except Exception as e:
                        logger.error(f"Failed to sync commands for guild {guild_id}: {str(e)}")
                
                # Sync global commands
                await self.tree.sync()
                logger.info("Synced global commands")
                
        except Exception as e:
            logger.error(f"Failed to sync commands: {str(e)}", exc_info=True)

    async def apply_personalization_settings(self) -> None:
        """Apply saved personalization settings."""
        try:
            async with self.db_pool.acquire() as conn:
                global_settings = await conn.fetch(
                    "SELECT key, value FROM bot_settings WHERE guild_id = 0"
                )
                
                for setting in global_settings:
                    key, value = setting['key'], setting['value']
                    
                    if key == 'status':
                        status_map = {
                            'online': discord.Status.online,
                            'idle': discord.Status.idle,
                            'dnd': discord.Status.dnd,
                            'invisible': discord.Status.invisible
                        }
                        if value in status_map:
                            await self.change_presence(status=status_map[value])
                    
                    elif key == 'activity_type':
                        activity_text = await conn.fetchval(
                            "SELECT value FROM bot_settings WHERE key = 'activity_text' AND guild_id = 0"
                        )
                        if activity_text:
                            activity_map = {
                                'playing': discord.ActivityType.playing,
                                'streaming': discord.ActivityType.streaming,
                                'listening': discord.ActivityType.listening,
                                'watching': discord.ActivityType.watching,
                                'competing': discord.ActivityType.competing
                            }
                            if value in activity_map:
                                activity = discord.Activity(type=activity_map[value], name=activity_text)
                                await self.change_presence(activity=activity)
                    
                    elif key == 'avatar':
                        try:
                            avatar_bytes = base64.b64decode(value)
                            await self.user.edit(avatar=avatar_bytes)
                        except Exception as e:
                            logger.error(f"Failed to update avatar: {str(e)}")
                            
        except Exception as e:
            logger.error(f"Failed to apply personalization settings: {str(e)}", exc_info=True)

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        await self.apply_server_nicknames()
        await self.sync_guilds()  # Resync guilds when bot comes online

    async def apply_server_nicknames(self) -> None:
        """Apply saved nicknames for each guild."""
        try:
            async with self.db_pool.acquire() as conn:
                nicknames = await conn.fetch(
                    "SELECT guild_id, value FROM bot_settings WHERE key = 'nickname'"
                )
                
                for nickname in nicknames:
                    guild = self.get_guild(nickname['guild_id'])
                    if guild:
                        try:
                            await guild.me.edit(nick=nickname['value'])
                            logger.info(f"Applied nickname '{nickname['value']}' in guild {guild.name}")
                        except discord.Forbidden:
                            logger.warning(f"Failed to set nickname in guild {guild.name}: Missing permissions")
                            
        except Exception as e:
            logger.error(f"Failed to apply server nicknames: {str(e)}", exc_info=True)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handle bot joining a new guild."""
        try:
            async with self.db_pool.acquire() as conn:
                # Add guild to database or reactivate if it existed
                await conn.execute('''
                    INSERT INTO guilds (guild_id, is_active) 
                    VALUES ($1, TRUE) 
                    ON CONFLICT (guild_id) 
                    DO UPDATE SET is_active = TRUE, joined_at = CURRENT_TIMESTAMP
                ''', guild.id)
                
                # Sync commands for the new guild
                await self.tree.sync(guild=discord.Object(id=guild.id))
                logger.info(f'Joined new guild: {guild.name} (ID: {guild.id})')
                
        except Exception as e:
            logger.error(f"Failed to process guild join for {guild.id}: {str(e)}", exc_info=True)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Handle bot leaving a guild."""
        try:
            async with self.db_pool.acquire() as conn:
                # Mark guild as inactive instead of deleting
                await conn.execute(
                    "UPDATE guilds SET is_active = FALSE WHERE guild_id = $1",
                    guild.id
                )
                logger.info(f'Removed from guild: {guild.name} (ID: {guild.id})')
                
        except Exception as e:
            logger.error(f"Failed to process guild remove for {guild.id}: {str(e)}", exc_info=True)

    async def start_bot(self) -> None:
        """Start the bot."""
        try:
            await self.start(self.token)
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    intents = discord.Intents.all()

    config_path = 'config/config.json'
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    DATABASE_URL = os.getenv('DATABASE_URL')

    if not TOKEN or not DATABASE_URL:
        logger.error("Missing required environment variables")
        exit(1)

    bot = MyBot(
        command_prefix=config['prefix'],
        intents=intents,
        token=TOKEN,
        database_url=DATABASE_URL,
        config_path=config_path
    )

    bot.run(TOKEN)
