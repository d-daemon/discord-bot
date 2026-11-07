import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="addrole", help="Adds a specified role to a specified member."
    )
    @commands.has_permissions(manage_roles=True)
    async def addrole(self, ctx, member: discord.Member, role: discord.Role):
        """Adds a role to a member."""
        error = self._role_hierarchy_error(ctx, member, role)
        if error:
            await ctx.send(error)
            return
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            await ctx.send(
                "I can't assign that role. Check role hierarchy and permissions."
            )
            return
        except discord.HTTPException:
            logger.exception("Role assignment failed in guild %s", ctx.guild.id)
            await ctx.send("The role could not be assigned due to a Discord API error.")
            return
        await ctx.send(f"Added {role.mention} to {member.mention}")

    @commands.command(
        name="removerole", help="Removes a specified role from a specified member."
    )
    @commands.has_permissions(manage_roles=True)
    async def removerole(self, ctx, member: discord.Member, role: discord.Role):
        """Removes a role from a member."""
        error = self._role_hierarchy_error(ctx, member, role)
        if error:
            await ctx.send(error)
            return
        try:
            await member.remove_roles(role)
        except discord.Forbidden:
            await ctx.send(
                "I can't remove that role. Check role hierarchy and permissions."
            )
            return
        except discord.HTTPException:
            logger.exception("Role removal failed in guild %s", ctx.guild.id)
            await ctx.send("The role could not be removed due to a Discord API error.")
            return
        await ctx.send(f"Removed {role.mention} from {member.mention}")

    @staticmethod
    def _role_hierarchy_error(ctx, member, role):
        bot_member = ctx.guild.me
        if bot_member is None or role >= bot_member.top_role:
            return "I can't manage a role equal to or higher than my highest role."
        if ctx.author.id != ctx.guild.owner_id and role >= ctx.author.top_role:
            return "You can't manage a role equal to or higher than your highest role."
        if (
            ctx.author.id != ctx.guild.owner_id
            and member.top_role >= ctx.author.top_role
        ):
            return "You can't manage roles for a member with an equal or higher role."
        return None

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the Manage Roles permission to use this command.")
            return
        raise error


async def setup(bot):
    await bot.add_cog(Admin(bot))
