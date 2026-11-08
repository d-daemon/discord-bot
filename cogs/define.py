import asyncio
import logging
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from PyMultiDictionary import DICT_MW, MultiDictionary

from utils.paginator import PaginatorView

logger = logging.getLogger(__name__)


class Define(commands.Cog):
    """A cog that provides word definition functionality.

    This cog allows users to look up definitions of words from multiple sources,
    including Dictionary API, Merriam-Webster, and Urban Dictionary.
    """

    def __init__(self, bot):
        self.bot = bot

    def get_mw_fallback_embed(self, word: str) -> discord.Embed | None:
        """Get the definition of a word from Merriam-Webster"""
        md = MultiDictionary()
        try:
            results = md.meaning("en", word, dictionary=DICT_MW)
            if not results:
                return None

            embed = discord.Embed(
                title=f"Definition of {word}", color=discord.Color.green()
            )

            if isinstance(results, tuple) and len(results) > 0:
                definitions = results[0]
                if definitions:
                    embed.add_field(
                        name="Definition",
                        value="\n".join(
                            [f"{i + 1}. {d}" for i, d in enumerate(definitions)]
                        ),
                        inline=False,
                    )

            embed.set_footer(text="Source: Merriam-Webster (PyMultiDictionary)")
            return embed

        except Exception:
            logger.exception("Merriam-Webster lookup failed for %r", word)
            return None

    async def get_urban_definitions(self, word):
        """Get the definitions from Urban Dictionary"""
        session = self.bot.http_session
        if session is None or session.closed:
            raise RuntimeError("HTTP session is not available")

        async with session.get(
            "https://api.urbandictionary.com/v0/define", params={"term": word}
        ) as response:
            if response.status != 200:
                return None
            data = await response.json()
            results = data.get("list")
            return results if isinstance(results, list) else None

    async def send_fallback_definition(self, ctx, word):
        fallback_embed = await asyncio.to_thread(self.get_mw_fallback_embed, word)
        if fallback_embed:
            await ctx.send(embed=fallback_embed)
            return

        results = await self.get_urban_definitions(word)
        if results:
            paginator = PaginatorView(
                self.build_urban_embeds(results, word), author=ctx.author, loop=True
            )
            await paginator.send(ctx)
            return

        await ctx.send(f"Could not find the definition for **{word}**.")

    def build_urban_embeds(self, results: list, word: str) -> list[discord.Embed]:
        """Build Urban Dictionary embeds"""
        pages = []
        for i, entry in enumerate(results):
            description = entry["definition"].replace("[", "").replace("]", "")
            embed = discord.Embed(
                title=entry["word"][:256],
                description=description[:4096],
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
        try:
            results = await self.get_urban_definitions(word)
        except (aiohttp.ClientError, TimeoutError, ValueError, RuntimeError):
            logger.exception("Urban Dictionary lookup failed for %r", word)
            await ctx.send("Urban Dictionary is temporarily unavailable.")
            return

        if not results or len(results) == 0:
            return await ctx.send(f"Could not find the definition for **{word}**.")

        pages = self.build_urban_embeds(results, word)
        paginator = PaginatorView(pages, author=ctx.author, loop=True)
        await paginator.send(ctx)

    @commands.command()
    async def define(self, ctx, *, word: str):
        """Get the definition of a word"""

        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word, safe='')}"

        try:
            session = self.bot.http_session
            if session is None or session.closed:
                raise RuntimeError("HTTP session is not available")

            async with session.get(url) as response:
                if response.status != 200:
                    await self.send_fallback_definition(ctx, word)
                    return
                data = await response.json()

            if not isinstance(data, list) or not data:
                await self.send_fallback_definition(ctx, word)
                return

            embed = discord.Embed(
                title=f"Definition of {word}", color=discord.Color.green()
            )
            for meaning in data[0].get("meanings", []):
                definitions = meaning.get("definitions", [])
                value = "\n".join(
                    f"{index + 1}. {definition.get('definition', '')}"
                    for index, definition in enumerate(definitions)
                )
                if value:
                    embed.add_field(
                        name=meaning.get("partOfSpeech", "Definition")[:256],
                        value=value[:1024],
                        inline=False,
                    )

            if not embed.fields:
                await self.send_fallback_definition(ctx, word)
                return
            embed.set_footer(text="Source: Dictionary API")
            await ctx.send(embed=embed)
        except (aiohttp.ClientError, TimeoutError, ValueError, RuntimeError):
            logger.exception("Definition lookup failed for %r", word)
            await ctx.send("Definition services are temporarily unavailable.")


async def setup(bot):
    await bot.add_cog(Define(bot))
