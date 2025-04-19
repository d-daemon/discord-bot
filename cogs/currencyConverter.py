import re
import discord
from discord.ext import commands
import aiohttp
from decimal import Decimal, InvalidOperation

# NOTE: ISO 4217 Currencies: https://en.wikipedia.org/wiki/ISO_4217

class CurrencyConverter(commands.Cog):
    """Currency Converter"""
    def __init__(self, bot):
        self.bot = bot
        self.default_currencies = [
            'cad', 'hkd', 'inr',
            'idr', 'myr', 'sgd',
            'krw', 'usd'
        ]
        self.currency_flags = {
            'cad': '🇨🇦',
            'hkd': '🇭🇰',
            'inr': '🇮🇳',
            'idr': '🇮🇩',
            'myr': '🇲🇾',
            'sgd': '🇸🇬',
            'krw': '🇰🇷',
            'usd': '🇺🇸',
        }
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

    def format_currency_field(self, currency: str, amount: Decimal) -> str:
        """Format currency value in a box-like format"""
        return f"```\n{amount:,.2f} {currency.upper()}```"

    def get_flag(self, currency: str) -> str:
        """Get flag emoji for currency, with fallback to 💱"""
        return self.currency_flags.get(currency.lower(), '💱')

    @commands.command(name="fx")
    async def convert_command(self, ctx, *, args: str):
        # Parse the command arguments using regex
        match = re.match(
            r'^(\d+(?:[.,]\d{3})*(?:[.,]\d+)?)\s+([A-Za-z]{3})(?:\s+to\s+([A-Za-z]{3}))?$',
            args.strip(),
            re.IGNORECASE
        )
        if not match:
            await ctx.send("**Invalid format!** Use `!fx <amount> <source_currency> [to <target_currency>]`")
            return

        amount_str, source_currency, target_currency = match.groups()
        
        # Normalize the amount string for Decimal parsing
        # First, determine if it's using comma or period as decimal separator
        if ',' in amount_str and '.' in amount_str:
            # If both separators are present, the last one is the decimal separator
            if amount_str.rindex(',') > amount_str.rindex('.'):
                # European format (1.000,00)
                amount_str = amount_str.replace('.', '').replace(',', '.')
            else:
                # US/UK format (1,000.00)
                amount_str = amount_str.replace(',', '')
        elif ',' in amount_str:
            # If only comma is present, check if it's used as decimal or thousands separator
            if amount_str.count(',') == 1 and len(amount_str.split(',')[1]) <= 2:
                # Likely a decimal separator (e.g., 1000,50)
                amount_str = amount_str.replace(',', '.')
            else:
                # Likely thousands separators (e.g., 1,000,000)
                amount_str = amount_str.replace(',', '')
        # If only period is present, no changes needed
        
        # Convert to Decimal for better precision
        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            await ctx.send("**Invalid number format!** Please use a valid number.")
            return
            
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

        # Build the embed with a modern design
        embed = discord.Embed(
            title=f"{self.get_flag(source_currency)} {amount:,.2f} {source_currency.upper()} Conversion",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Exchange rates as of {date}")

        # Prepare conversion results
        conversion_results = []
        
        # Process default currencies first (for grid layout)
        for curr in self.default_currencies:
            if curr in rates:
                rate = Decimal(str(rates[curr]))
                converted = amount * rate
                flag = self.get_flag(curr)
                name = self.currency_names.get(curr, curr.upper())
                conversion_results.append((curr, converted, flag, name))

        # If there's a specific target currency not in defaults, add it to the end
        if target_currency and target_currency not in self.default_currencies and target_currency in rates:
            rate = Decimal(str(rates[target_currency]))
            converted = amount * rate
            flag = self.get_flag(target_currency)
            name = self.currency_names.get(target_currency, target_currency.upper())
            conversion_results.append((target_currency, converted, flag, name))

        # Add fields in a grid layout (3x3)
        for i in range(0, len(conversion_results), 3):
            row = conversion_results[i:i+3]
            for curr, converted, flag, name in row:
                embed.add_field(
                    name=f"{flag} {name}",
                    value=self.format_currency_field(curr, converted),
                    inline=True
                )
            
            # Add empty fields to complete the row if needed
            remaining = 3 - len(row)
            for _ in range(remaining):
                embed.add_field(name="\u200b", value="\u200b", inline=True)

        if not embed.fields:
            await ctx.send("No valid target currencies found.")
            return

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CurrencyConverter(bot))
