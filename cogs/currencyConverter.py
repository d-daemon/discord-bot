import re
import discord
from discord.ext import commands
import aiohttp

# NOTE: ISO 4217 Currencies: https://en.wikipedia.org/wiki/ISO_4217

class CurrencyConverter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.default_currencies = [
            'cad',
            'hkd',
            'inr',
            'idr',
            'myr',
            'krw',
            'sgd',
            'usd',
        ]
        self.currency_names = {
            'cad': 'Canadian Dollar',
            'hkd': 'Hong Kong Dollar',
            'inr': 'Indian Rupee',
            'idr': 'Indonesian Rupiah',
            'myr': 'Malaysian Ringgit',
            'sgd': 'Singapore Dollar',
            'krw': 'South Korean Won',
            'usd': 'US Dollar',
        }

    @commands.command(name="fx")
    async def convert_command(self, ctx, *, args: str):
        # Parse the command arguments using regex
        match = re.match(
            r'^(\d+(?:\.\d+)?)\s+([A-Za-z]{3})(?:\s+to\s+([A-Za-z]{3}))?$',
            args.strip(),
            re.IGNORECASE
        )
        if not match:
            await ctx.send("**Invalid format!** Use `!fx <amount> <source_currency> [to <target_currency>]`")
            return

        amount_str, source_currency, target_currency = match.groups()
        amount = float(amount_str)
        source_currency = source_currency.lower()
        target_currency = target_currency.lower() if target_currency else None

        # Fetch exchange rates from the API
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{source_currency}.json"
                async with session.get(url) as response:
                    if response.status != 200:
                        # Fallback to the secondary API
                        url = f"https://latest.currency-api.pages.dev/v1/currencies/{source_currency}.json"
                        async with session.get(url) as fallback_response:
                            if fallback_response.status != 200:
                                await ctx.send("**Error fetching rates.** Check the currency code and try again.")
                                return
                            data = await fallback_response.json()
                    else:
                        data = await response.json()
        except Exception as e:
            await ctx.send(f"**API Error:** {str(e)}")
            return

        if source_currency not in data:
            await ctx.send(f"**Currency not found:** {source_currency.upper()}")
            return

        rates = data[source_currency]
        date = data.get('date', 'Unknown date')

        # Determine target currencies
        targets = []
        if target_currency:
            targets = [target_currency] + self.default_currencies
            seen = set()
            unique_targets = []
            for curr in targets:
                curr_lower = curr.lower()
                if curr_lower not in seen:
                    seen.add(curr_lower)
                    unique_targets.append(curr_lower)
            targets = unique_targets
        else:
            targets = self.default_currencies.copy()

        # Build the embed
        embed = discord.Embed(
            title=f"💰 {amount:,.2f} {source_currency.upper()} Conversion",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Exchange rates as of {date}")

        # Add conversion fields
        for target in targets:
            if target not in rates:
                continue
            converted = amount * rates[target]
            currency_name = self.currency_names.get(target, target.upper())
            embed.add_field(
                name=currency_name,
                value=f"**{converted:,.2f}** {target.upper()}",
                inline=False
            )

        if not embed.fields:
            await ctx.send("No valid target currencies found.")
            return

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CurrencyConverter(bot))