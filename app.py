import discord
import re
from discord.ext import commands
import asyncio

# Bot configuration
import os
import ssl


import os

try:
    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()
    TOKEN = os.environ.get("DISCORD_TOKEN")
except ImportError:
    # If python-dotenv is not installed, try option 2
    TOKEN = None

# Check if token exists
if not TOKEN:
    raise ValueError(
        "No Discord token found. Please set up your token using environment variables or a config file."
    )
COMMAND_PREFIX = "!"
intents = discord.Intents.default()
intents.message_content = True  # Needed to read message content

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Regular expression to detect code blocks
# This will capture code that is not already in Discord's code blocks
code_regex = re.compile(r"```[\w]*\n[\s\S]*?\n```|`[\s\S]*?`")

# Dictionary to store the last processed message ID for each channel
last_processed = {}


async def format_code(message):
    """
    Check if the message contains code that's not already in a code block
    and format it with the username
    """
    content = message.content

    # Skip messages that are already properly formatted or from the bot itself
    if message.author == bot.user or code_regex.search(content):
        return None

    # Simple heuristics to detect potential code
    # Looking for common programming patterns
    code_indicators = [
        # Python indicators
        r"def\s+\w+\s*\(.*\):",
        r"class\s+\w+[:(]",
        r"import\s+\w+",
        r"from\s+\w+\s+import",
        # JavaScript/TypeScript indicators
        r"function\s+\w+\s*\(.*\)",
        r"const\s+\w+\s*=",
        r"let\s+\w+\s*=",
        r"var\s+\w+\s*=",
        r"=>\s*{",
        r"class\s+\w+\s*{",
        # Java/C#/C++ indicators
        r"public\s+\w+\s+\w+\s*\(.*\)",
        r"private\s+\w+\s+\w+\s*\(.*\)",
        r"protected\s+\w+\s+\w+\s*\(.*\)",
        # General code patterns
        r"for\s*\(.+\)",
        r"if\s*\(.+\)",
        r"while\s*\(.+\)",
        r"switch\s*\(.+\)",
        r"case\s+.+:",
        r"}\s*else\s*{",
        # Multiple consecutive lines with indentation
        r"\n\s{2,}.*\n\s{2,}",
        r"\n\t+.*\n\t+",
    ]

    # Check if any code indicators are present
    is_code = any(re.search(pattern, content) for pattern in code_indicators)

    # Also check if there are multiple lines with common code characters
    if not is_code and "\n" in content:
        lines = content.split("\n")
        code_chars = set("{}[]()+*/-=%<>!&|;:.")
        code_lines = sum(1 for line in lines if any(c in code_chars for c in line))
        is_code = code_lines > 2  # If more than 2 lines have code characters

    if is_code:
        # Format with username and code in code block
        formatted = f"{message.author.display_name}\n```\n{content}\n```"
        return formatted

    return None


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    # Start the background task for monitoring channels
    bot.loop.create_task(monitor_channels())


@bot.event
async def on_message(message):
    # Don't process commands here to avoid double-processing
    # The monitor_channels function will handle everything
    pass


async def monitor_channels():
    """
    Background task to monitor channels for new messages
    and format code in near real-time
    """
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            # Process each channel the bot can see
            for channel in bot.get_all_channels():
                # Only process text channels
                if not isinstance(channel, discord.TextChannel):
                    continue

                # Get the last processed message ID for this channel
                last_id = last_processed.get(channel.id, 0)

                # Get recent messages after the last processed one
                async for message in channel.history(
                    limit=10, after=discord.Object(id=last_id)
                ):
                    # Skip bot messages
                    if message.author == bot.user:
                        continue

                    # Try to format code
                    formatted = await format_code(message)

                    # If code was detected and formatted, send it
                    if formatted:
                        await channel.send(formatted)

                    # Update the last processed message ID
                    last_processed[channel.id] = max(
                        last_processed.get(channel.id, 0), message.id
                    )

            # Wait a short time before checking again
            await asyncio.sleep(2)  # Check every 2 seconds

        except Exception as e:
            print(f"Error in monitor task: {e}")
            await asyncio.sleep(5)  # Wait a bit longer if there's an error


# Command to toggle the code detection for a channel
@bot.command(name="togglecode")
@commands.has_permissions(manage_messages=True)
async def toggle_code_detection(ctx):
    """Toggle the code detection for the current channel"""
    channel_id = ctx.channel.id

    if channel_id in last_processed:
        del last_processed[channel_id]
        await ctx.send("Code detection disabled for this channel.")
    else:
        last_processed[channel_id] = ctx.message.id
        await ctx.send("Code detection enabled for this channel.")


# Command to help users
@bot.command(name="codehelp")
async def code_help(ctx):
    """Display help information about the code detection bot"""
    help_text = """
**Code Detection Bot Help**

This bot automatically detects when you post code and formats it with proper code blocks.

**Commands:**
• `!togglecode` - Enable/disable code detection (requires manage messages permission)
• `!codehelp` - Show this help message

**Tips:**
• The bot tries to detect code based on common patterns
• If you want to post code manually, use Discord's code blocks: \```language
your code
\```
    """
    await ctx.send(help_text)


# Run the bot
bot.run(TOKEN)
