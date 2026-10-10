import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define Bot Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize Bot (any of these prefixes work: !ping  ?ping  ,ping)
bot = commands.Bot(command_prefix=('!', '?', ','), intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')

    # Load Cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded extension: {filename}')
            except Exception as e:
                print(f'Failed to load extension {filename}: {e}')

@bot.command()
async def ping(ctx):
    """Check the bot's latency."""
    await ctx.send(f'Pong! 🏓 {round(bot.latency * 1000)}ms')

if __name__ == "__main__":
    bot.run(TOKEN)
