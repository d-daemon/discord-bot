import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

import aiohttp
import asyncpg
import discord
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    if not isinstance(config, dict):
        raise ValueError("Bot configuration must be a JSON object")
    prefix = config.get("prefix")
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("Bot configuration must include a non-empty command prefix")
    return config


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
        db_pool (asyncpg.Pool | None): Connection pool for database operations
        config (dict[str, Any]): Bot configuration settings
        guild_ids (list[int]): Cached list of guild IDs
        ready_event (asyncio.Event): Event to track bot's ready state
    """

    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        token: str,
        database_url: str,
        config_path: str,
        config: dict[str, Any] | None = None,
    ):
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
        if not token or not database_url:
            raise ValueError("Bot token and database URL are required")
        self.db_pool: asyncpg.Pool | None = None
        self.http_session: aiohttp.ClientSession | None = None
        self.guild_ids: list[int] = []
        self._ready_initialized = False
        self._commands_synced = False

        self.config = config if config is not None else load_config(self.config_path)

    async def ensure_database_connection(self) -> None:
        """
        Ensures database connection is established with retry mechanism.

        Raises:
            DatabaseConnectionError: If unable to establish connection after retries.
        """
        max_retries = 5
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                if self.db_pool is None:
                    self.db_pool = await asyncpg.create_pool(
                        self.database_url, min_size=1, max_size=10, command_timeout=30
                    )
                    logger.info("Database connection established successfully")
                return
            except (asyncpg.PostgresError, OSError, TimeoutError) as e:
                logger.warning(
                    "Database connection attempt %s failed: %s", attempt + 1, e
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise DatabaseConnectionError(
                        f"Failed to connect to database after {max_retries} attempts"
                    ) from e

    async def close(self) -> None:
        """Close owned resources before shutting down the Discord client."""
        try:
            if self.http_session is not None and not self.http_session.closed:
                await self.http_session.close()
        finally:
            try:
                if self.db_pool is not None:
                    await self.db_pool.close()
                    self.db_pool = None
            finally:
                await super().close()

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
            if self.http_session is None or self.http_session.closed:
                self.http_session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=20)
                )

            # Initialize database
            await self.init_database()

            # Cache guild IDs
            await self.cache_guild_ids()

            # Load cogs
            await self.load_all_cogs()

        except Exception:
            logger.exception("Failed to complete bot setup")
            raise

    async def init_database(self) -> None:
        """
        Initializes the database connection and creates necessary tables.
        """

        async def create_tables(conn):
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id BIGINT PRIMARY KEY,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT NOT NULL,
                    value TEXT,
                    guild_id BIGINT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (key, guild_id)
                )
            """)

        try:
            await self.execute_db_operation(create_tables)
            logger.info("Database initialization complete")
        except Exception:
            logger.exception("Database initialization failed")
            raise

    async def cache_guild_ids(self) -> None:
        """
        Caches guild IDs from the database and synchronizes with current guilds.
        """

        async def fetch_guilds(conn):
            return await conn.fetch("SELECT guild_id FROM guilds")

        try:
            rows = await self.execute_db_operation(fetch_guilds)
            guild_ids = list(dict.fromkeys(row["guild_id"] for row in rows))
            known_ids = set(guild_ids)
            current_guild_ids = [guild.id for guild in self.guilds]
            missing_ids = [
                guild_id for guild_id in current_guild_ids if guild_id not in known_ids
            ]

            if missing_ids:

                async def insert_missing(conn):
                    await conn.executemany(
                        "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                        [(guild_id,) for guild_id in missing_ids],
                    )

                await self.execute_db_operation(insert_missing)

            self.guild_ids = list(dict.fromkeys(guild_ids + current_guild_ids))
            logger.info("Cached %s guild IDs", len(self.guild_ids))
        except Exception:
            logger.exception("Failed to cache guild IDs")
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

        global_settings = await self.execute_db_operation(fetch_settings)
        settings = {row["key"]: row["value"] for row in global_settings}
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        activity_map = {
            "playing": discord.ActivityType.playing,
            "streaming": discord.ActivityType.streaming,
            "listening": discord.ActivityType.listening,
            "watching": discord.ActivityType.watching,
            "competing": discord.ActivityType.competing,
        }
        presence = {}
        if settings.get("status") in status_map:
            presence["status"] = status_map[settings["status"]]
        activity_type = settings.get("activity_type")
        activity_text = settings.get("activity_text")
        if activity_type in activity_map and activity_text:
            presence["activity"] = discord.Activity(
                type=activity_map[activity_type], name=activity_text
            )
        if presence:
            await self.change_presence(**presence)

        avatar = settings.get("avatar")
        if avatar:
            try:
                await self.user.edit(avatar=base64.b64decode(avatar, validate=True))
            except (ValueError, discord.HTTPException):
                logger.exception("Failed to apply the saved bot avatar")

        logger.info("Applied global personalization settings")

    async def apply_server_nicknames(self) -> None:
        """
        Applies saved nicknames for the bot in each guild.
        """

        async def fetch_nicknames(conn):
            return await conn.fetch(
                "SELECT guild_id, value FROM bot_settings WHERE key = 'nickname'"
            )

        nicknames = await self.execute_db_operation(fetch_nicknames)
        for nickname in nicknames:
            guild = self.get_guild(nickname["guild_id"])
            if guild is None or guild.me is None:
                continue
            try:
                await guild.me.edit(nick=nickname["value"])
                logger.info("Applied saved nickname in guild %s", guild.id)
            except discord.Forbidden:
                logger.warning(
                    "Missing permission to apply nickname in guild %s", guild.id
                )
            except discord.HTTPException:
                logger.exception("Failed to apply nickname in guild %s", guild.id)

    async def load_all_cogs(self) -> None:
        """
        Loads required top-level cogs in a deterministic order.
        """
        cog_directory = Path(__file__).parent / "cogs"
        for path in sorted(cog_directory.glob("*.py")):
            if path.name.startswith("_"):
                continue

            cog_name = f"cogs.{path.stem}"
            try:
                await self.load_extension(cog_name)
            except Exception:
                logger.exception("Failed to load required cog %s", cog_name)
                raise
            logger.info("Loaded cog: %s", cog_name)

    async def sync_all_commands(self) -> None:
        """
        Synchronizes global application commands once per process.
        """
        if self._commands_synced:
            return

        try:
            # Sync global commands
            await self.tree.sync()
        except Exception:
            logger.exception("Global command synchronization failed")
            raise

        self._commands_synced = True
        logger.info("Command synchronization complete")

    async def add_guild_to_db(self, guild_id: int) -> None:
        """
        Adds a new guild to the database.

        Args:
            guild_id (int): The Discord guild ID to add
        """

        async def insert_guild(conn):
            await conn.execute(
                "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                guild_id,
            )

        await self.execute_db_operation(insert_guild)
        if guild_id not in self.guild_ids:
            self.guild_ids.append(guild_id)
        logger.info("Added guild %s to database", guild_id)

    async def remove_guild_from_db(self, guild_id: int) -> None:
        """
        Removes a guild from the database.

        Args:
            guild_id (int): The Discord guild ID to remove
        """

        async def delete_guild(conn):
            await conn.execute("DELETE FROM guilds WHERE guild_id = $1", guild_id)
            await conn.execute("DELETE FROM bot_settings WHERE guild_id = $1", guild_id)

        await self.execute_db_operation(delete_guild)
        if guild_id in self.guild_ids:
            self.guild_ids.remove(guild_id)
        logger.info("Removed guild %s from database", guild_id)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Handles the bot joining a new guild.

        Args:
            guild (discord.Guild): The guild that was joined
        """
        await self.add_guild_to_db(guild.id)
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
        if self._ready_initialized:
            logger.info("Discord connection resumed")
            return

        logger.info("Logged in as %s", self.user)
        # Ensure cached guilds and nicknames are applied after the websocket is ready
        await self.cache_guild_ids()
        await self.apply_server_nicknames()

        # Sync commands and apply personalization now that the connection is established
        await self.sync_all_commands()
        await self.apply_personalization_settings()
        self._ready_initialized = True

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
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True

    config_path = os.environ.get(
        "BOT_CONFIG_PATH", str(Path(__file__).parent / "config" / "config.json")
    )
    config = load_config(config_path)
    token = os.getenv("DISCORD_BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL")

    if not token or not database_url:
        raise RuntimeError("DISCORD_BOT_TOKEN and DATABASE_URL are required")

    # Create and run bot
    bot = MyBot(
        command_prefix=config["prefix"],
        intents=intents,
        token=token,
        database_url=database_url,
        config_path=config_path,
        config=config,
    )

    bot.run(token)
