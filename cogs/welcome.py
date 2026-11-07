import discord
from discord.ext import commands


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.welcome_channel_name = self.config.get("welcome_channel", "general")
        self.goodbye_channel_name = self.config.get("goodbye_channel", "general")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Sends a welcome message when a new member joins the server."""
        channel = discord.utils.get(
            member.guild.text_channels, name=self.welcome_channel_name
        )
        if channel:
            await channel.send(
                f"Welcome to the server, {member.mention}! We're glad to have you here."
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Sends a message when a member leaves the server."""
        channel = discord.utils.get(
            member.guild.text_channels, name=self.goodbye_channel_name
        )
        if channel:
            await channel.send("RIP BOZO")


async def setup(bot):
    await bot.add_cog(Welcome(bot))
