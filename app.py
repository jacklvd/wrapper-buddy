import discord
import re
from discord.ext import commands
import asyncio
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
    TOKEN = os.environ.get('DISCORD_TOKEN')
except ImportError:
    TOKEN = None

if not TOKEN:
    raise ValueError("No Discord token found. Please set up your token using environment variables or a config file.")

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# This will capture code that is not already in Discord's code blocks
code_regex = re.compile(r"```[\w]*\n[\s\S]*?\n```|`[\s\S]*?`")

# Dictionary to store the last processed message ID for each channel
last_processed = {}

def detect_language(code):
    """
    Detect programming language based on code syntax
    Returns the language name or an empty string if unknown
    """
    # Check for Python patterns
    if re.search(r'def\s+\w+\s*\(.*\):', code) or \
       re.search(r'import\s+[\w\.]+', code) or \
       re.search(r'from\s+[\w\.]+\s+import', code) or \
       re.search(r'print\s*\(', code):
        return "python"
    
    # Check for JavaScript/TypeScript patterns
    if re.search(r'function\s+\w+\s*\(.*\)', code) or \
       re.search(r'const\s+\w+\s*=', code) or \
       re.search(r'let\s+\w+\s*=', code) or \
       re.search(r'var\s+\w+\s*=', code) or \
       re.search(r'=>\s*{', code) or \
       re.search(r'document\.', code) or \
       re.search(r'console\.log', code):
        # Differentiate between JS and TS
        if re.search(r'interface\s+\w+\s*{', code) or \
           re.search(r':\s*(string|number|boolean|any)\s*[,=)]', code):
            return "typescript"
        return "javascript"
    
    # Check for HTML
    if re.search(r'<(!DOCTYPE|html|head|body|div|span|p|a|img)\b', code):
        return "html"
    
    # Check for CSS
    if re.search(r'[.#][\w-]+\s*{', code) or \
       re.search(r'(margin|padding|color|background|font):', code):
        return "css"
    
    # Check for Java/C#/C++
    if re.search(r'(public|private|protected)\s+\w+\s+\w+\s*\(', code) or \
       re.search(r'class\s+\w+\s*(extends|implements|:)', code) or \
       re.search(r'(int|float|double|char|boolean|string)\s+\w+\s*=', code, re.IGNORECASE):
        # More specific checks for each language
        if re.search(r'System\.out\.println', code) or \
           re.search(r'public\s+static\s+void\s+main', code):
            return "java"
        elif re.search(r'Console\.WriteLine', code) or \
             re.search(r'namespace\s+\w+', code):
            return "csharp"
        elif re.search(r'#include', code) or \
             re.search(r'std::', code) or \
             re.search(r'->\w+', code):
            return "cpp"
    
    return ""

async def format_code(message):
    """
    Check if the message contains code that's not already in a code block
    and format it with the username and detected language
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
        # Detect the language
        language = detect_language(content)
        
        # Format with username and code in code block with language tag if detected
        if language:
            formatted = f"{message.author.display_name}\n```{language}\n{content}\n```"
        else:
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
    # Process commands
    await bot.process_commands(message)
    
    # Don't process code detection here, let monitor_channels handle it
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
                async for message in channel.history(limit=10, after=discord.Object(id=last_id)):
                    # Skip bot messages
                    if message.author == bot.user:
                        continue
                    
                    # Try to format code
                    formatted = await format_code(message)
                    
                    # If code was detected and formatted, send it
                    if formatted:
                        await channel.send(formatted)
                    
                    # Update the last processed message ID
                    last_processed[channel.id] = max(last_processed.get(channel.id, 0), message.id)
            
            # Wait a short time before checking again
            await asyncio.sleep(1)  # Check every 1 second for faster response
        
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

This bot automatically detects when you post code and formats it with proper code blocks and language highlighting.

**Commands:**
• `!togglecode` - Enable/disable code detection (requires manage messages permission)
• `!codehelp` - Show this help message

**Tips:**
• The bot tries to detect code based on common patterns
• The bot will try to identify the programming language for syntax highlighting
• If you want to post code manually, use Discord's code blocks: ```language
your code
```
    """
    await ctx.send(help_text)

# Command to test language detection
@bot.command(name="detectlang")
async def detect_language_command(ctx, *, code=None):
    """Test the language detection on a piece of code"""
    if not code:
        await ctx.send("Please provide some code to detect the language.")
        return
    
    language = detect_language(code)
    if language:
        await ctx.send(f"Detected language: **{language}**")
    else:
        await ctx.send("Could not detect the programming language.")


if __name__ == "__main__":
    # Run the bot
    bot.run(TOKEN)