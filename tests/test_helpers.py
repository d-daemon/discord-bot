import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from utils.helpers import edit_ephemeral_response, send_ephemeral


class EphemeralHelperTests(unittest.TestCase):
    def test_send_ephemeral_uses_initial_response_and_auto_deletes(self):
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                is_done=Mock(return_value=False), send_message=AsyncMock()
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        asyncio.run(send_ephemeral(interaction, "A short notice"))

        interaction.response.send_message.assert_awaited_once_with(
            "A short notice", ephemeral=True, delete_after=10
        )
        interaction.followup.send.assert_not_awaited()

    def test_send_ephemeral_uses_followup_after_defer(self):
        interaction = SimpleNamespace(
            response=SimpleNamespace(is_done=Mock(return_value=True)),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        asyncio.run(send_ephemeral(interaction, "A deferred notice", delete_after=5))

        interaction.followup.send.assert_awaited_once_with(
            "A deferred notice", ephemeral=True, delete_after=5
        )

    def test_edit_ephemeral_response_schedules_deletion(self):
        edited_message = SimpleNamespace(delete=AsyncMock())
        interaction = SimpleNamespace(
            edit_original_response=AsyncMock(return_value=edited_message)
        )

        asyncio.run(edit_ephemeral_response(interaction, "Done"))

        interaction.edit_original_response.assert_awaited_once_with(content="Done")
        edited_message.delete.assert_awaited_once_with(delay=10)
