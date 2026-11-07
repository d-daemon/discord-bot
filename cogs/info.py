import discord
from discord.ext import commands


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="userinfo", help="Displays information about a user.")
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        joined_at = getattr(member, "joined_at", None)
        embed = discord.Embed(title=f"User Info - {member}", color=discord.Color.blue())
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Name", value=member.display_name, inline=True)
        embed.add_field(
            name="Created At",
            value=discord.utils.format_dt(member.created_at, style="F"),
            inline=True,
        )
        embed.add_field(
            name="Joined At",
            value=discord.utils.format_dt(joined_at, style="F")
            if joined_at
            else "Not available",
            inline=True,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
