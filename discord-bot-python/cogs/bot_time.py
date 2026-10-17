# bot_time.py
import os
import discord
from discord.ext import commands
from datetime import datetime

# Use your bot token from the Discord Developer Portal
TOKEN = os.getenv("DISCORD_TOKEN")  # or replace with a string literal (not recommended)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Ready to tell time!")

@bot.command(name="time")
async def tell_time(ctx):
    now = datetime.utcnow()
    # Format as you like; here we use UTC with a readable format
    time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    await ctx.send(f"The current time is **{time_str}**")

if __name__ == "__main__":
    bot.run(TOKEN)
