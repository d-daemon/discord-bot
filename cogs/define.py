import discord
from discord.ext import commands
import aiohttp


class Define(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="define", description="Get the definition of a word")
    async def define(self, ctx, word: str):
        """Get the definition of a word"""

        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        await ctx.send(f"Could not find the definition for **{word}**.")
                        return

                    data = await response.json()

                    if isinstance(data, list) and len(data) > 0:
                        embed = discord.Embed(
                            title=f"Definition of {word}", color=discord.Color.green()
                        )

                        for meaning in data[0]["meanings"]:
                            part_of_speech = meaning["partOfSpeech"]
                            definitions = meaning["definitions"]

                            embed.add_field(
                                name=part_of_speech,
                                value="\n".join(
                                    [
                                        f"{i + 1}. {d['definition']}"
                                        for i, d in enumerate(definitions)
                                    ]
                                ),
                                inline=False,
                            )

                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"Could not find the definition for **{word}**.")

        except Exception as e:
            await ctx.send(f"**API Error:** {str(e)}")
            return


async def setup(bot):
    await bot.add_cog(Define(bot))
