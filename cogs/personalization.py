import discord
from discord.ext import commands
from discord import app_commands
import asyncpg
import io
import base64

class Personalization(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def setup(self):
        guild_ids = await self.fetch_guild_ids()
        for guild_id in guild_ids:
            self.bot.tree.add_command(self.personalize, guild=discord.Object(id=guild_id))
            self.bot.tree.add_command(self.set_avatar, guild=discord.Object(id=guild_id))

    async def fetch_guild_ids(self):
        async with self.bot.db_pool.acquire() as connection:
            records = await connection.fetch("SELECT guild_id FROM guilds")
            return [record['guild_id'] for record in records]

    @app_commands.command(name="personalize", description="Personalize the bot")
    @app_commands.describe(
        name="Set the bot's nickname in this server",
        status="Set the bot's status",
        activity_type="Set the bot's activity type",
        activity_text="Set the text for the bot's activity"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def personalize(self, interaction: discord.Interaction, 
                          name: str = None, 
                          status: str = None, 
                          activity_type: str = None,
                          activity_text: str = None):
        await interaction.response.defer(ephemeral=True)
        
        async with self.bot.db_pool.acquire() as conn:
            if name:
                await interaction.guild.me.edit(nick=name)
                await conn.execute(
                    "INSERT INTO bot_settings (key, value, guild_id) VALUES ($1, $2, $3) ON CONFLICT (key, guild_id) DO UPDATE SET value = $2",
                    'nickname', name, interaction.guild_id
                )
            
            if status:
                status_map = {
                    'online': discord.Status.online,
                    'idle': discord.Status.idle,
                    'dnd': discord.Status.dnd,
                    'invisible': discord.Status.invisible
                }
                if status.lower() in status_map:
                    await self.bot.change_presence(status=status_map[status.lower()])
                    await conn.execute(
                        "INSERT INTO bot_settings (key, value, guild_id) VALUES ($1, $2, $3) ON CONFLICT (key, guild_id) DO UPDATE SET value = $2",
                        'status', status.lower(), 0  # Use 0 as a sentinel value for global settings
                    )
                else:
                    await interaction.followup.send(f"Invalid status: {status}. Please choose from online, idle, dnd, or invisible.", ephemeral=True)
                    return
            
            if activity_type and activity_text:
                activity_map = {
                    'playing': discord.ActivityType.playing,
                    'streaming': discord.ActivityType.streaming,
                    'listening': discord.ActivityType.listening,
                    'watching': discord.ActivityType.watching,
                    'competing': discord.ActivityType.competing
                }
                if activity_type.lower() in activity_map:
                    activity = discord.Activity(type=activity_map[activity_type.lower()], name=activity_text)
                    await self.bot.change_presence(activity=activity)
                    await conn.execute(
                        "INSERT INTO bot_settings (key, value, guild_id) VALUES ($1, $2, $3) ON CONFLICT (key, guild_id) DO UPDATE SET value = $2",
                        'activity_type', activity_type.lower(), 0  # Use 0 as a sentinel value for global settings
                    )
                    await conn.execute(
                        "INSERT INTO bot_settings (key, value, guild_id) VALUES ($1, $2, $3) ON CONFLICT (key, guild_id) DO UPDATE SET value = $2",
                        'activity_text', activity_text, 0  # Use 0 as a sentinel value for global settings
                    )
                else:
                    await interaction.followup.send(f"Invalid activity type: {activity_type}. Please choose from playing, streaming, listening, watching, or competing.", ephemeral=True)
                    return

        changes = []
        if name:
            changes.append(f"Nickname set to: {name}")
        if status:
            changes.append(f"Status set to: {status}")
        if activity_type and activity_text:
            changes.append(f"Activity set to: {activity_type} {activity_text}")

        if changes:
            await interaction.followup.send("Bot personalization updated:\n" + "\n".join(changes), ephemeral=True)
        else:
            await interaction.followup.send("No changes were made to the bot's personalization.", ephemeral=True)

    @personalize.autocomplete('status')
    async def status_autocomplete(self, interaction: discord.Interaction, current: str):
        statuses = ['online', 'idle', 'dnd', 'invisible']
        return [app_commands.Choice(name=status, value=status) for status in statuses if current.lower() in status.lower()]

    @personalize.autocomplete('activity_type')
    async def activity_type_autocomplete(self, interaction: discord.Interaction, current: str):
        activity_types = ['playing', 'streaming', 'listening', 'watching', 'competing']
        return [app_commands.Choice(name=activity, value=activity) for activity in activity_types if current.lower() in activity.lower()]

    @app_commands.command(name="set_avatar", description="Set the bot's avatar")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_avatar(self, interaction: discord.Interaction, avatar: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        
        if not avatar.content_type.startswith('image/'):
            await interaction.followup.send("Please upload an image file.", ephemeral=True)
            return

        avatar_data = await avatar.read()
        await self.bot.user.edit(avatar=avatar_data)

        # Convert binary data to base64 string for storage
        avatar_base64 = base64.b64encode(avatar_data).decode('utf-8')

        async with self.bot.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bot_settings (key, value, guild_id) VALUES ($1, $2, $3) ON CONFLICT (key, guild_id) DO UPDATE SET value = $2",
                'avatar', avatar_base64, 0  # Use 0 as a sentinel value for global settings
            )

        await interaction.followup.send("Bot avatar updated successfully!", ephemeral=True)

async def setup(bot):
    cog = Personalization(bot)
    await cog.setup()
    await bot.add_cog(cog)