import discord
from discord.ext import commands
import aiohttp
from utils.paginator import PaginatorView
from PyMultiDictionary import MultiDictionary, DICT_MW


class Define(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_mw_fallback_embed(self, word: str) -> discord.Embed | None:
        md = MultiDictionary()
        try:
            results = md.meaning("en", word, dictionary=DICT_MW)
            if not results:
                return None

            embed = discord.Embed(
                title=f"Definition of {word}", color=discord.Color.green()
            )

            for part_of_speech, definitions in results.items():
                if not definitions:
                    continue
                embed.add_field(
                    name=part_of_speech,
                    value="\n".join(
                        [f"{i + 1}. {d}" for i, d in enumerate(definitions)]
                    ),
                    inline=False,
                )

            embed.set_footer(text="Source: Merriam-Webster (PyMultiDictionary)")
            return embed

        except Exception as e:
            print(f"**MW Error:** {e}")
            return None

    async def get_urban_definitions(self, word):
        """Get the definitions from Urban Dictionary"""
        url = f"https://api.urbandictionary.com/v0/define?term={word}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["list"]
                else:
                    return None

    def build_urban_embeds(self, results: list, word: str) -> list[discord.Embed]:
        pages = []
        for i, entry in enumerate(results):
            embed = discord.Embed(
                title=entry["word"],
                description=entry["definition"].replace("[", "").replace("]", ""),
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=f"Definition {i + 1}/{len(results)} • Source: Urban Dictionary"
            )
            pages.append(embed)
        return pages

    @commands.command()
    async def ud(self, ctx, *, word: str):
        """Get the definition of a word from Urban Dictionary"""
        results = await self.get_urban_definitions(word)

        if not results or len(results) == 0:
            return await ctx.send(f"Could not find the definition for **{word}**.")

        pages = self.build_urban_embeds(results, word)
        paginator = PaginatorView(pages, loop=True)
        await paginator.send(ctx)

    @commands.command()
    async def define(self, ctx, *, word: str):
        """Get the definition of a word"""

        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        fallback_embed = self.get_mw_fallback_embed(word)
                        if fallback_embed:
                            await ctx.send(embed=fallback_embed)
                            return

                        results = await self.get_urban_definitions(word)
                        if results:
                            embeds = self.build_urban_embeds(results, word)
                            paginator = PaginatorView(embeds, loop=True)
                            await paginator.send(ctx)
                            return
                        
                        else:
                            await ctx.send(
                                f"Could not find the definition for **{word}**."
                            )
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

                        embed.set_footer(text="Source: Dictionary API")

                        await ctx.send(embed=embed)
                    else:
                        fallback_embed = self.get_mw_fallback_embed(word)
                        if fallback_embed:
                            await ctx.send(embed=fallback_embed)
                            return

                        results = await self.get_urban_definitions(word)
                        if results:
                            embeds = self.build_urban_embeds(results, word)
                            paginator = PaginatorView(embeds, loop=True)
                            await paginator.send(ctx)
                            return
                        
                        else:
                            await ctx.send(
                                f"Could not find the definition for **{word}**."
                            )
                            return

        except Exception as e:
            await ctx.send(f"**API Error:** {str(e)}")
            return


async def setup(bot):
    await bot.add_cog(Define(bot))
