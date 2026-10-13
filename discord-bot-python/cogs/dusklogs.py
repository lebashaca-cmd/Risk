import os
from datetime import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

CONFIG_ERROR = "The website isn't set up yet. Add `DUSK_URL` and `DUSK_ADMIN_TOKEN` to the bot's `.env`."


class DuskLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    dusklogs = app_commands.Group(
        name="dusklogs",
        description="Control where dusk sign-up logs are posted",
        guild_only=True,
        default_permissions=discord.Permissions(administrator=True),
    )

    async def call(self, method, path, *, json=None, params=None):
        base = (os.getenv("DUSK_URL") or "").strip().rstrip("/")
        token = (os.getenv("DUSK_ADMIN_TOKEN") or "").strip()
        if not base.startswith("http") or not token:
            return None, CONFIG_ERROR

        headers = {"Authorization": f"Bearer {token}"}
        timeout = aiohttp.ClientTimeout(total=45)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    f"{base}{path}",
                    headers=headers,
                    json=json,
                    params=params,
                    allow_redirects=False,
                ) as response:
                    status = response.status
                    try:
                        body = await response.json(content_type=None)
                    except Exception:
                        body = None
        except aiohttp.ClientError:
            return None, "I couldn't reach the website."
        except TimeoutError:
            return None, "The website took too long to answer. It may be waking up, so try again in a minute."

        if 300 <= status < 400:
            return None, "The website redirected the request. Check that `DUSK_URL` is the exact `https://` address."
        if status in (401, 403):
            return None, "The website rejected the admin token. Check `DUSK_ADMIN_TOKEN`."
        if status >= 400:
            message = body.get("error") if isinstance(body, dict) else None
            if isinstance(message, str) and message:
                return None, f"The website said: {message[:200]}"
            return None, f"The website returned an error ({status})."
        if body is None:
            return None, "The website sent back something I couldn't read."
        return body, None

    @dusklogs.command(name="channel", description="Post new dusk sign-ups in a channel")
    @app_commands.describe(channel="Where sign-up logs should be posted")
    @app_commands.checks.has_permissions(administrator=True)
    async def channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        data, error = await self.call("PUT", "/api/admin/logs", json={"channelId": str(channel.id)})
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await interaction.followup.send(f"New dusk sign-ups will be posted in {channel.mention}.", ephemeral=True)

    @dusklogs.command(name="off", description="Turn sign-up logging off")
    @app_commands.checks.has_permissions(administrator=True)
    async def off(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data, error = await self.call("PUT", "/api/admin/logs", json={"channelId": None})
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await interaction.followup.send("Sign-up logging is off.", ephemeral=True)

    @dusklogs.command(name="status", description="Show where sign-up logs go and how many accounts exist")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data, error = await self.call("GET", "/api/admin/logs")
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        if not isinstance(data, dict):
            await interaction.followup.send("The website sent back something I couldn't read.", ephemeral=True)
            return

        channel_id = data.get("channelId")
        where = f"Sign-up logs are posted in <#{channel_id}>." if channel_id else "Sign-up logging is off."
        total = data.get("total")
        lines = [where]
        if isinstance(total, int):
            lines.append(f"Total accounts: **{total:,}**")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @dusklogs.command(name="recent", description="Show the latest dusk sign-ups")
    @app_commands.describe(count="How many to show (1-25, default 10)")
    @app_commands.checks.has_permissions(administrator=True)
    async def recent(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 25] = 10):
        await interaction.response.defer(ephemeral=True)
        data, error = await self.call("GET", "/api/admin/signups", params={"limit": count})
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        if not isinstance(data, list):
            await interaction.followup.send("The website sent back something I couldn't read.", ephemeral=True)
            return
        if not data:
            await interaction.followup.send("No sign-ups yet.", ephemeral=True)
            return

        lines = []
        for entry in data[:count]:
            if not isinstance(entry, dict):
                continue
            username = discord.utils.escape_markdown(str(entry.get("username") or "unknown"))
            discord_name = discord.utils.escape_markdown(str(entry.get("discordUsername") or "unknown"))
            ip = entry.get("ip") or "unknown"
            when = ""
            created = entry.get("createdAt")
            if isinstance(created, str):
                try:
                    stamp = int(datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp())
                    when = f"<t:{stamp}:R>"
                except ValueError:
                    when = created
            lines.append(f"**{username}** · Discord: {discord_name} · IP: `{ip}` · {when}")

        embed = discord.Embed(
            title=f"Latest {len(lines)} dusk sign-up{'s' if len(lines) != 1 else ''}",
            description="\n".join(lines)[:4000],
            color=discord.Color.dark_purple(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "Only administrators can use this command."
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "This command only works in a server."
        else:
            message = "Something went wrong running that command."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DuskLogs(bot))
