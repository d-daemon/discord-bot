import random
import re

import aiohttp
from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="roll",
        help="Rolls dice in the specified NdN format (e.g., 2d6 for two six-sided dice).",
    )
    async def roll(self, ctx, dice: str):
        """Rolls a dice in NdN format."""
        match = re.fullmatch(r"\s*(\d{1,3})[dD](\d{1,9})\s*", dice)
        if not match:
            await ctx.send("Use NdN format, for example 2d6 (up to 100 dice).")
            return

        rolls, limit = map(int, match.groups())
        if not 1 <= rolls <= 100 or not 1 <= limit <= 1_000_000:
            await ctx.send("Roll between 1 and 100 dice, with 1 to 1,000,000 sides.")
            return

        result = ", ".join(str(random.randint(1, limit)) for _ in range(rolls))
        await ctx.send(result)

    @commands.command(
        name="joke", help="Fetches a random joke from an external API and displays it."
    )
    async def joke(self, ctx):
        """Tells a random joke fetched from an external API."""
        session = self.bot.http_session
        if session is None or session.closed:
            await ctx.send("The joke service is temporarily unavailable.")
            return

        try:
            async with session.get(
                "https://official-joke-api.appspot.com/random_joke"
            ) as response:
                if response.status == 200:
                    joke_data = await response.json()
                    setup = joke_data.get("setup")
                    punchline = joke_data.get("punchline")
                    if not setup or not punchline:
                        raise ValueError("Joke response is incomplete")
                    await ctx.send(f"{setup} - {punchline}")
                else:
                    await ctx.send("Could not retrieve a joke at this time.")
        except (aiohttp.ClientError, TimeoutError, ValueError):
            await ctx.send("Failed to retrieve a joke. Please try again later.")


async def setup(bot):
    await bot.add_cog(Fun(bot))
