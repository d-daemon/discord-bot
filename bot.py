import asyncio
import logging
import base64
import json
import os
import sys
from typing import Any, Dict, List, Optional

import asyncpg
import discord
from discord.ext import commands

class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass

class MyBot(commands.Bot):
    """
    A custom Discord bot implementation with enhanced guild management and database integration.
    
    This bot class extends discord.py's commands.Bot with additional functionality for:
    - Database connection management
    - Guild tracking and synchronization
    - Personalization settings
    - Dynamic cog loading
    
    Attributes:
        token (str): The Discord bot token
        database_url (str): PostgreSQL database connection URL
        config_path (str): Path to the configuration file
        db_pool (Optional[asyncpg.Pool]): Connection pool for database operations
        config (Dict[str, Any]): Bot configuration settings
        guild_ids (List[int]): Cached list of guild IDs
        ready_event (asyncio.Event): Event to track bot's ready state
    """

    def __init__(self, command_prefix: str, intents: discord.Intents, 
                 token: str, database_url: str, config_path: str):
        """
        Initialize the bot with necessary configurations and settings.
        
        Args:
            command_prefix (str): Prefix for bot commands
            intents (discord.Intents): Discord gateway intents
            token (str): Discord bot authentication token
            database_url (str): PostgreSQL database URL
            config_path (str): Path to configuration file
        """
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.token = token
        self.database_url = database_url
        self.config_path = config_path
        self.db_pool: Optional[asyncpg.Pool] = None
        self.guild_ids: List[int] = []
        
        with open(self.config_path, 'r') as config_file:
            self.config = json.load(config_file)

    async def ensure_database_connection(self) -> None:
        """
        Ensures database connection is established with retry mechanism.
        
        Raises:
            DatabaseConnectionError: If unable to establish connection after retries.
        """
        max_retries = 5
        retry_delay = 5  # seconds
        timeout = 30  # seconds

        for attempt in range(max_retries):
            try:
                if self.db_pool is None:
                    # Use asyncio.wait_for instead of asyncio.timeout for Python 3.9 compatibility
                    self.db_pool = await asyncio.wait_for(
                        asyncpg.create_pool(
                            self.database_url,
                            min_size=1,
                            max_size=10,
                            command_timeout=30
                        ),
                        timeout=timeout
                    )
                    logger.info("Database connection established successfully")
                return
            except asyncio.TimeoutError:
                logger.warning(f"Database connection attempt {attempt + 1} timed out")
            except Exception as e:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                raise DatabaseConnectionError(f"Failed to connect to database after {max_retries} attempts")


    async def execute_db_operation(self, operation):
        """
        Executes a database operation with connection checking.
        
        Args:
            operation: Async function that performs the database operation
            
        Returns:
            The result of the database operation
            
        Raises:
            DatabaseConnectionError: If database connection fails
        """
        await self.ensure_database_connection()
        if self.db_pool is None:
            raise DatabaseConnectionError("Database connection not available")
        
        try:
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    return await operation(conn)
        except asyncpg.PostgresError as e:
            logger.error(f"Database operation failed: {e}")
            raise

    async def setup_hook(self) -> None:
        """
        Initializes the bot's essential components before starting.
        This method is automatically called by discord.py.
        """
        try:
            # First establish database connection
            await self.ensure_database_connection()
            logger.info("Database connection established")

            # Initialize database tables
            await self.init_database()
            logger.info("Database tables initialized")

            # Wait a short time to ensure database is ready
            await asyncio.sleep(2)

            # Load cogs first as they don't depend on guild data
            await self.load_all_cogs()
            logger.info("Cogs loaded successfully")

            # Now cache guild IDs
            await self.cache_guild_ids()
            logger.info("Guild IDs cached successfully")

            # Sync commands after guild data is cached
            await self.sync_all_commands()
            logger.info("Commands synchronized")

            # Apply personalization last
            await self.apply_personalization_settings()
            logger.info("Personalization settings applied")

        except DatabaseConnectionError as e:
            logger.critical(f"Database connection failed: {e}")
            # Gracefully shutdown the bot
            await self.close()
            raise
        except Exception as e:
            logger.critical(f"Setup failed: {e}")
            await self.close()
            raise

    async def on_ready(self) -> None:
        """
        Modified ready event handler with retry mechanism for critical operations.
        """
        logger.info(f'Logged in as {self.user.name}')
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Ensure database connection is still alive
                await self.ensure_database_connection()
                
                # Refresh guild cache
                await self.cache_guild_ids()
                
                # Apply nicknames
                await self.apply_server_nicknames()
                
                # Final command sync
                await self.sync_all_commands()
                
                logger.info("Bot successfully initialized and ready")
                return
                
            except Exception as e:
                logger.error(f"Ready event initialization attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                else:
                    logger.critical("Failed to complete ready event initialization")
                    await self.close()
                    raise

    async def init_database(self) -> None:
        """
        Initializes the database connection and creates necessary tables.
        """
        async def create_tables(conn):
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id BIGINT PRIMARY KEY,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT NOT NULL,
                    value TEXT,
                    guild_id BIGINT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (key, guild_id)
                )
            ''')
        
        try:
            await self.execute_db_operation(create_tables)
            logger.info("Database initialization complete")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def cache_guild_ids(self) -> None:
        """
        Caches guild IDs from the database and synchronizes with current guilds.
        """
        async def fetch_guilds(conn):
            return await conn.fetch("SELECT guild_id FROM guilds")

        try:
            rows = await self.execute_db_operation(fetch_guilds)
            self.guild_ids = [row['guild_id'] for row in rows]
            
            # Sync with current guilds
            current_guild_ids = [guild.id for guild in self.guilds]
            
            # Add missing guilds to database
            for guild_id in current_guild_ids:
                if guild_id not in self.guild_ids:
                    await self.add_guild_to_db(guild_id)
            
            logger.info(f"Cached {len(self.guild_ids)} guild IDs")
        except Exception as e:
            logger.error(f"Failed to cache guild IDs: {e}")
            raise

    async def apply_personalization_settings(self) -> None:
        """
        Applies personalization settings from the database, including status,
        activity, and avatar settings.
        """
        async def fetch_settings(conn):
            return await conn.fetch(
                "SELECT key, value FROM bot_settings WHERE guild_id = 0"
            )

        try:
            global_settings = await self.execute_db_operation(fetch_settings)
            
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
                    async def fetch_activity_text(conn):
                        return await conn.fetchval(
                            "SELECT value FROM bot_settings WHERE key = 'activity_text' AND guild_id = 0"
                        )
                    
                    activity_text = await self.execute_db_operation(fetch_activity_text)
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
                        logger.error(f"Failed to set avatar: {e}")

            logger.info("Applied global personalization settings")
        except Exception as e:
            logger.error(f"Failed to apply personalization settings: {e}")


    async def apply_server_nicknames(self) -> None:
        """
        Applies saved nicknames for the bot in each guild.
        """
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
                            logger.error(f"Failed to set nickname in guild {guild.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to apply server nicknames: {e}")

    async def load_all_cogs(self) -> None:
        """
        Loads all cogs from the cogs directory.
        """
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    logger.info(f"Loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {e}")

    async def sync_all_commands(self) -> None:
        """
        Synchronizes application commands globally and per guild.
        """
        try:
            # Sync global commands
            await self.tree.sync()
            
            # Sync guild-specific commands
            for guild_id in self.guild_ids:
                await self.tree.sync(guild=discord.Object(id=guild_id))
            
            logger.info("Command synchronization complete")
        except Exception as e:
            logger.error(f"Command synchronization failed: {e}")

    async def add_guild_to_db(self, guild_id: int) -> None:
        """
        Adds a new guild to the database.
        
        Args:
            guild_id (int): The Discord guild ID to add
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                    guild_id
                )
                if guild_id not in self.guild_ids:
                    self.guild_ids.append(guild_id)
                logger.info(f"Added guild {guild_id} to database")
        except Exception as e:
            logger.error(f"Failed to add guild {guild_id}: {e}")

    async def remove_guild_from_db(self, guild_id: int) -> None:
        """
        Removes a guild from the database.
        
        Args:
            guild_id (int): The Discord guild ID to remove
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("DELETE FROM guilds WHERE guild_id = $1", guild_id)
                await conn.execute("DELETE FROM bot_settings WHERE guild_id = $1", guild_id)
                if guild_id in self.guild_ids:
                    self.guild_ids.remove(guild_id)
                logger.info(f"Removed guild {guild_id} from database")
        except Exception as e:
            logger.error(f"Failed to remove guild {guild_id}: {e}")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Handles the bot joining a new guild.
        
        Args:
            guild (discord.Guild): The guild that was joined
        """
        await self.add_guild_to_db(guild.id)
        await self.tree.sync(guild=discord.Object(id=guild.id))
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """
        Handles the bot being removed from a guild.
        
        Args:
            guild (discord.Guild): The guild that was left
        """
        await self.remove_guild_from_db(guild.id)
        logger.info(f"Removed from guild: {guild.name} (ID: {guild.id})")

    async def on_ready(self) -> None:
        """
        Handles the bot's ready event.
        """
        logger.info(f'Logged in as {self.user.name}')
        await self.cache_guild_ids()
        await self.apply_server_nicknames()
        await self.sync_all_commands()

    async def start_bot(self) -> None:
        """
        Starts the bot with the configured token.
        """
        try:
            await self.start(self.token)
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise

if __name__ == "__main__":
    # Set up logging first
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        # Set up intents
        intents = discord.Intents.all()

        # Load configuration
        config_path = 'config/config.json'
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)

        # Get environment variables
        TOKEN = os.getenv('DISCORD_BOT_TOKEN')
        DATABASE_URL = os.getenv('DATABASE_URL')

        if not all([TOKEN, DATABASE_URL]):
            raise EnvironmentError("Missing required environment variables")

        # Create and run bot with error handling
        bot = MyBot(
            command_prefix=config['prefix'],
            intents=intents,
            token=TOKEN,
            database_url=DATABASE_URL,
            config_path=config_path
        )

        # Run the bot
        bot.run(TOKEN)

    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
