import discord
from discord.ext import commands
import random
import aiohttp

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()  # Create a ClientSession to be used for all HTTP requests

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())  # Properly close the session when the cog is unloaded

    @commands.command(name='roll', help='Rolls dice in the specified NdN format (e.g., 2d6 for two six-sided dice).')
    async def roll(self, ctx, dice: str):
        """Rolls a dice in NdN format."""
        try:
            rolls, limit = map(int, dice.split('d'))
            result = ', '.join(str(random.randint(1, limit)) for _ in range(rolls))
            await ctx.send(result)
        except ValueError:
            await ctx.send('Format has to be NdN! Example: 2d6')

    @commands.command(name='joke', help='Fetches a random joke from an external API and displays it.')
    async def joke(self, ctx):
        """Tells a random joke fetched from an external API."""
        try:
            async with self.session.get('https://official-joke-api.appspot.com/random_joke') as response:
                if response.status == 200:
                    joke_data = await response.json()
                    await ctx.send(f'{joke_data["setup"]} - {joke_data["punchline"]}')
                else:
                    await ctx.send('Could not retrieve a joke at this time.')
        except aiohttp.ClientError as e:
            await ctx.send(f'Failed to retrieve joke: {str(e)}')

async def setup(bot):
    await bot.add_cog(Fun(bot))
