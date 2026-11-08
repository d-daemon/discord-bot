import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot import MyBot


class BotLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.config_path.write_text(json.dumps({"prefix": "!"}), encoding="utf-8")
        self.bot = MyBot(
            command_prefix="!",
            intents=discord.Intents.none(),
            token="test-token",
            database_url="postgresql://unused",
            config_path=str(self.config_path),
        )

    async def asyncTearDown(self):
        await self.bot.close()

    async def test_ready_initialization_runs_once(self):
        self.bot.cache_guild_ids = AsyncMock()
        self.bot.apply_server_nicknames = AsyncMock()
        self.bot.sync_all_commands = AsyncMock()
        self.bot.apply_personalization_settings = AsyncMock()

        await self.bot.on_ready()
        await self.bot.on_ready()

        self.bot.cache_guild_ids.assert_awaited_once()
        self.bot.apply_server_nicknames.assert_awaited_once()
        self.bot.sync_all_commands.assert_awaited_once()
        self.bot.apply_personalization_settings.assert_awaited_once()

    async def test_close_releases_owned_resources(self):
        session = SimpleNamespace(closed=False, close=AsyncMock())
        pool = SimpleNamespace(close=AsyncMock())
        self.bot.http_session = session
        self.bot.db_pool = pool

        await self.bot.close()

        session.close.assert_awaited_once()
        pool.close.assert_awaited_once()
        self.assertIsNone(self.bot.db_pool)

    async def test_required_cog_load_failure_propagates(self):
        with (
            patch("bot.Path.glob", return_value=[Path("cogs/admin.py")]),
            patch.object(
                self.bot,
                "load_extension",
                new=AsyncMock(side_effect=RuntimeError("broken cog")),
            ),
            self.assertRaisesRegex(RuntimeError, "broken cog"),
        ):
            await self.bot.load_all_cogs()


if __name__ == "__main__":
    unittest.main()
