import discord
import os
import math
import traceback
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

from utils.helpers import explain_error

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
STATUS_PORT = int(os.getenv('SERVER_PORT', 25239))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=('!', '?', ','), intents=intents)


async def status_handler(request):
    latency = bot.latency
    online = bot.is_ready() and not math.isnan(latency) and not math.isinf(latency)
    data = {
        "online": online,
        "name": bot.user.name if bot.user else None,
        "latency_ms": round(latency * 1000) if online else None,
    }
    return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})


async def start_status_server():
    app = web.Application()
    app.router.add_get('/', status_handler)
    app.router.add_get('/status', status_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', STATUS_PORT).start()
    print(f'Status page listening on 0.0.0.0:{STATUS_PORT}')


@bot.event
async def setup_hook():
    await start_status_server()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')

    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            ext = f'cogs.{filename[:-3]}'
            if ext in bot.extensions:
                continue
            try:
                await bot.load_extension(ext)
                print(f'Loaded extension: {filename}')
            except Exception as e:
                print(f'Failed to load extension {filename}: {e}')

    if not getattr(bot, 'commands_synced', False):
        bot.commands_synced = True
        try:
            synced = await bot.tree.sync()
            print(f'Synced {len(synced)} slash command(s)')
        except Exception as e:
            print(f'Slash command sync failed: {e}')


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if ctx.command is not None and ctx.command.has_error_handler():
        return
    if ctx.cog is not None and ctx.cog.has_error_handler():
        return
    if await explain_error(ctx, error):
        return
    traceback.print_exception(type(error), error, error.__traceback__)


@bot.command()
async def ping(ctx):
    """Check the bot's latency."""
    await ctx.send(f'Pong! 🏓 {round(bot.latency * 1000)}ms')


if __name__ == "__main__":
    bot.run(TOKEN)
