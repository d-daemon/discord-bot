import base64
import logging

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)


class Personalization(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def store_settings(self, settings):
        async with self.bot.db_pool.acquire() as connection:
            async with connection.transaction():
                for key, value, guild_id in settings:
                    await connection.execute(
                        "INSERT INTO bot_settings (key, value, guild_id) VALUES ($1, $2, $3) "
                        "ON CONFLICT (key, guild_id) DO UPDATE SET value = EXCLUDED.value, "
                        "updated_at = CURRENT_TIMESTAMP",
                        key,
                        value,
                        guild_id,
                    )

    @app_commands.command(name="personalize", description="Personalize the bot")
    @app_commands.describe(
        name="Set the bot's nickname in this server",
        status="Set the bot's status",
        activity_type="Set the bot's activity type",
        activity_text="Set the text for the bot's activity",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def personalize(
        self,
        interaction: discord.Interaction,
        name: str = None,
        status: str = None,
        activity_type: str = None,
        activity_text: str = None,
    ):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used in a server.", ephemeral=True
            )
            return

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
        normalized_status = status.lower() if status else None
        normalized_activity = activity_type.lower() if activity_type else None

        if normalized_status and normalized_status not in status_map:
            await interaction.followup.send(
                "Choose online, idle, dnd, or invisible.", ephemeral=True
            )
            return
        if normalized_activity and normalized_activity not in activity_map:
            await interaction.followup.send(
                "Choose playing, streaming, listening, watching, or competing.",
                ephemeral=True,
            )
            return
        if bool(normalized_activity) != bool(activity_text):
            await interaction.followup.send(
                "Provide both an activity type and activity text.", ephemeral=True
            )
            return
        if name is not None and (not name.strip() or len(name) > 32):
            await interaction.followup.send(
                "Nickname must be 1 to 32 characters.", ephemeral=True
            )
            return
        if activity_text and len(activity_text) > 128:
            await interaction.followup.send(
                "Activity text must be 128 characters or fewer.", ephemeral=True
            )
            return

        settings = []
        try:
            if name is not None:
                await interaction.guild.me.edit(nick=name)
                settings.append(("nickname", name, interaction.guild_id))
            if normalized_status:
                await self.bot.change_presence(status=status_map[normalized_status])
                settings.append(("status", normalized_status, 0))
            if normalized_activity:
                activity = discord.Activity(
                    type=activity_map[normalized_activity], name=activity_text
                )
                await self.bot.change_presence(activity=activity)
                settings.extend(
                    (
                        ("activity_type", normalized_activity, 0),
                        ("activity_text", activity_text, 0),
                    )
                )
            if settings:
                await self.store_settings(settings)
        except (discord.Forbidden, discord.HTTPException):
            logger.exception(
                "Personalization update failed in guild %s", interaction.guild_id
            )
            await interaction.followup.send(
                "The personalization update failed. Check bot permissions and try again.",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Could not save personalization settings")
            await interaction.followup.send(
                "The personalization settings could not be saved.", ephemeral=True
            )
            return

        changes = []
        if name:
            changes.append(f"Nickname set to: {name}")
        if status:
            changes.append(f"Status set to: {status}")
        if activity_type and activity_text:
            changes.append(f"Activity set to: {activity_type} {activity_text}")

        if changes:
            await interaction.followup.send(
                "Bot personalization updated:\n" + "\n".join(changes), ephemeral=True
            )
        else:
            await interaction.followup.send(
                "No changes were made to the bot's personalization.", ephemeral=True
            )

    @personalize.autocomplete("status")
    async def status_autocomplete(self, interaction: discord.Interaction, current: str):
        statuses = ["online", "idle", "dnd", "invisible"]
        return [
            app_commands.Choice(name=status, value=status)
            for status in statuses
            if current.lower() in status.lower()
        ]

    @personalize.autocomplete("activity_type")
    async def activity_type_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        activity_types = ["playing", "streaming", "listening", "watching", "competing"]
        return [
            app_commands.Choice(name=activity, value=activity)
            for activity in activity_types
            if current.lower() in activity.lower()
        ]

    @app_commands.command(name="set_avatar", description="Set the bot's avatar")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_avatar(
        self, interaction: discord.Interaction, avatar: discord.Attachment
    ):
        await interaction.response.defer(ephemeral=True)

        if (
            not (avatar.content_type or "").startswith("image/")
            or avatar.size > 10 * 1024 * 1024
        ):
            await interaction.followup.send(
                "Please upload an image file.", ephemeral=True
            )
            return

        try:
            avatar_data = await avatar.read()
            await self.bot.user.edit(avatar=avatar_data)
            avatar_base64 = base64.b64encode(avatar_data).decode("ascii")
            await self.store_settings([("avatar", avatar_base64, 0)])
        except (discord.Forbidden, discord.HTTPException):
            logger.exception("Bot avatar update failed")
            await interaction.followup.send(
                "The avatar could not be updated.", ephemeral=True
            )
            return
        except Exception:
            logger.exception("Could not save the bot avatar")
            await interaction.followup.send(
                "The avatar could not be saved.", ephemeral=True
            )
            return

        await interaction.followup.send(
            "Bot avatar updated successfully!", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Personalization(bot))
