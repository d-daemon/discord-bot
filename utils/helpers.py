import discord

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
    from dateutil import parser
    return parser.parse(time_str)

def admin_only():
    """Decorator to restrict command access to admins."""
    def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# Additional helpers can be added here as needed
