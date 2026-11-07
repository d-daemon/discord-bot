import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="kick", help="Kicks a member from the server with an optional reason."
    )
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """
        Kicks a member from the server.
        Parameters:
            member (discord.Member): The member to kick.
            reason (str, optional): The reason for the kick.
        """
        hierarchy_error = self._hierarchy_error(ctx, member)
        if hierarchy_error:
            await ctx.send(hierarchy_error)
            return

        try:
            await member.kick(reason=reason[:512] if reason else None)
        except discord.Forbidden:
            await ctx.send("I can't kick that member. Check my role and permissions.")
            return
        except discord.HTTPException:
            logger.exception("Kick request failed in guild %s", ctx.guild.id)
            await ctx.send("The member could not be kicked due to a Discord API error.")
            return

        reason_message = f" for {reason}" if reason else ""
        await ctx.send(f"Kicked {member.mention}{reason_message}")

    @commands.command(
        name="ban", help="Bans a member from the server with an optional reason."
    )
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """
        Bans a member from the server.
        Parameters:
            member (discord.Member): The member to ban.
            reason (str, optional): The reason for the ban.
        """
        hierarchy_error = self._hierarchy_error(ctx, member)
        if hierarchy_error:
            await ctx.send(hierarchy_error)
            return

        try:
            await member.ban(reason=reason[:512] if reason else None)
        except discord.Forbidden:
            await ctx.send("I can't ban that member. Check my role and permissions.")
            return
        except discord.HTTPException:
            logger.exception("Ban request failed in guild %s", ctx.guild.id)
            await ctx.send("The member could not be banned due to a Discord API error.")
            return

        reason_message = f" for {reason}" if reason else ""
        await ctx.send(f"Banned {member.mention}{reason_message}")

    @staticmethod
    def _hierarchy_error(ctx, member):
        if member.id == ctx.guild.owner_id:
            return "The server owner can't be moderated."
        if (
            ctx.author.id != ctx.guild.owner_id
            and member.top_role >= ctx.author.top_role
        ):
            return "You can't moderate a member with an equal or higher role."
        bot_member = ctx.guild.me
        if bot_member is None or member.top_role >= bot_member.top_role:
            return "I can't moderate a member with an equal or higher role than mine."
        return None

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this moderation command.")
            return
        raise error


async def setup(bot):
    await bot.add_cog(Moderation(bot))
