import random
import time
import logging
from dateutil import parser
import asyncio
import discord
from discord.ext import commands

USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    # Safari on iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
]

def get_random_user_agent():
    """Returns a random User-Agent from the list."""
    return random.choice(USER_AGENTS)

def do_sleep():
    """Sleep a short time between requests to avoid rate limiting."""
    sleep_time = min(random.expovariate(0.10), 25.0)
    if sleep_time < 5:  # minimum time to sleep
        sleep_time = 5
    logging.info(f"Rate limiting: Sleeping for {sleep_time} seconds")
    time.sleep(sleep_time)

def format_message(author, content):
    """Format a message nicely for logging or display."""
    return f"{author}: {content}"

def embed_message(title, description, color=discord.Color.blue()):
    """Create a simple Discord embed."""
    embed = discord.Embed(title=title, description=description, color=color)
    return embed

async def send_typing_pause(channel, duration=1.0):
    """Simulate typing in a channel for a brief period."""
    async with channel.typing():
        await asyncio.sleep(duration)

def clean_text(input_text):
    """Clean text to remove mentions or other unwanted parts for safety."""
    return discord.utils.escape_mentions(input_text)

def parse_time(time_str):
    """Parse a time string into a datetime object."""
    return parser.parse(time_str)

def admin_only():
    """Decorator to restrict command access to admins."""
    def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# Additional helpers can be added here as needed
