import discord
from discord.ext import commands
import random
import aiohttp

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def roll(self, ctx, dice: str):
        try:
            rolls, limit = map(int, dice.split('d'))
        except Exception:
            await ctx.send('Format has to be NdN!')
            return

        result = ', '.join(str(random.randint(1, limit)) for _ in range(rolls))
        await ctx.send(result)

    @commands.command()
    async def joke(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://official-joke-api.appspot.com/random_joke') as r:
                if r.status == 200:
                    joke_data = await r.json()
                    await ctx.send(f'{joke_data["setup"]} - {joke_data["punchline"]}')
                else:
                    await ctx.send('Could not retrieve joke at this time.')

def setup(bot):
    bot.add_cog(Fun(bot))
