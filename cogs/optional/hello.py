import discord
from discord.ext import commands
from discord import app_commands

class TestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hello", description="Responds with a greeting.")
    async def hello(self, interaction: discord.Interaction):
        # Responding to the slash command
        await interaction.response.send_message("Shut up.. Shut the fuck up.")

async def setup(bot):
    await bot.add_cog(TestCommands(bot))
