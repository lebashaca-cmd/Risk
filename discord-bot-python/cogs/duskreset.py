import os
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

CONFIG_ERROR = "The website isn't set up yet. Add `DUSK_URL` and `DUSK_ADMIN_TOKEN` to the bot's `.env`."
FOOTER = (
    "If this wasn't you, someone with access to your Discord account used it. "
    "Change your Discord password and remove unknown authorized apps, "
    "then log in to dusk again to start fresh."
)


def stamp(value, style="F"):
    if not isinstance(value, str):
        return None
    try:
        return f"<t:{int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp())}:{style}>"
    except ValueError:
        return None


def code(value):
    return f"`{str(value).replace('`', '')}`"


def as_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def page_names(data):
    pages = data.get("pages")
    pages = pages if isinstance(pages, list) else []
    return [str(p.get("username")) for p in pages if isinstance(p, dict) and p.get("username")]


class ConfirmView(discord.ui.View):
    def __init__(self, cog, interaction, data):
        super().__init__(timeout=60)
        self.cog = cog
        self.interaction = interaction
        self.user_id = interaction.user.id
        self.data = data
        self.used = False

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your confirmation.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Reset my account", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.used:
            return
        self.used = True
        self.stop()
        await interaction.response.edit_message(content="Resetting your dusk account...", embed=None, view=None)
        await self.cog.perform_reset(interaction, self.interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.used:
            return
        self.used = True
        self.stop()
        await interaction.response.edit_message(content="Cancelled. Nothing was changed.", embed=None, view=None)

    async def on_timeout(self):
        if self.used:
            return
        try:
            await self.interaction.edit_original_response(
                content="This confirmation expired. Run `/duskreset` again if you still want to reset.",
                embed=None,
                view=None,
            )
        except discord.HTTPException:
            pass


class DuskReset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def call(self, method, path):
        base = (os.getenv("DUSK_URL") or "").strip().rstrip("/")
        token = (os.getenv("DUSK_ADMIN_TOKEN") or "").strip()
        if not base.startswith("http") or not token:
            return None, CONFIG_ERROR

        headers = {"Authorization": f"Bearer {token}"}
        timeout = aiohttp.ClientTimeout(total=45)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, f"{base}{path}", headers=headers, allow_redirects=False) as response:
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
                return None, message[:200]
            return None, f"The website returned an error ({status})."
        if not isinstance(body, dict):
            return None, "The website sent back something I couldn't read."
        return body, None

    @app_commands.command(name="duskreset", description="Reset your own dusk account and get a security report in your DMs")
    @app_commands.checks.cooldown(1, 600.0, key=lambda i: i.user.id)
    async def duskreset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        data, error = await self.call("GET", f"/api/admin/accounts/{interaction.user.id}")
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        names = page_names(data)
        pages = data.get("pages") if isinstance(data.get("pages"), list) else []
        links = sum(as_int(p.get("links")) for p in pages if isinstance(p, dict))
        songs = sum(as_int(p.get("songs")) for p in pages if isinstance(p, dict))

        embed = discord.Embed(
            title="⚠️ Reset your dusk account?",
            description="This resets every page on your dusk account to its starting state. **This cannot be undone.**",
            color=discord.Color.red(),
        )
        embed.add_field(
            name=f"Pages ({len(names)})",
            value=", ".join(code(n) for n in names)[:1000] if names else "No pages",
            inline=False,
        )
        embed.add_field(
            name="What will be deleted",
            value=(
                f"**{links}** link{'s' if links != 1 else ''}\n"
                f"**{songs}** song{'s' if songs != 1 else ''}\n"
                "Your look, uploaded picture, community listing and view count"
            ),
            inline=False,
        )
        embed.add_field(
            name="Also",
            value="Page names stay. You'll be logged out of dusk everywhere.",
            inline=False,
        )
        embed.set_footer(text="This confirmation expires in 60 seconds.")

        view = ConfirmView(self, interaction, data)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def perform_reset(self, button_interaction: discord.Interaction, origin: discord.Interaction):
        user = origin.user
        data, error = await self.call("POST", f"/api/admin/accounts/{user.id}/reset")
        if error:
            await button_interaction.edit_original_response(content=f"The reset didn't go through: {error}", embed=None, view=None)
            return

        await button_interaction.edit_original_response(content="Your dusk account was reset.", embed=None, view=None)

        report = self.build_report(data, origin)
        try:
            await user.send(embed=report)
        except (discord.Forbidden, discord.HTTPException):
            await button_interaction.followup.send(
                "The reset worked, but I couldn't DM you because your DMs are closed. "
                "Here's your security report instead:",
                embed=report,
                ephemeral=True,
            )
            return

        await button_interaction.edit_original_response(
            content="Your dusk account was reset. I sent you a security report in your DMs.",
            embed=None,
            view=None,
        )

    def build_report(self, data, origin: discord.Interaction):
        reset = data.get("reset") if isinstance(data.get("reset"), dict) else {}
        names = page_names(data)
        when = stamp(reset.get("at")) or f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>"

        if origin.guild is not None:
            channel_name = getattr(origin.channel, "name", None)
            where = f"This bot, {discord.utils.escape_markdown(origin.guild.name)}"
            if channel_name:
                where += f" · #{discord.utils.escape_markdown(channel_name)}"
        else:
            where = "This bot, a DM with the bot"

        embed = discord.Embed(title="Your dusk account was reset", color=discord.Color.red())
        embed.add_field(
            name="Account",
            value=(
                f"{discord.utils.escape_markdown(str(data.get('discordUsername') or 'unknown'))} "
                f"({code(data.get('discordId') or origin.user.id)})\n"
                f"Pages: {', '.join(code(n) for n in names) if names else 'none'}"
            )[:1000],
            inline=False,
        )
        embed.add_field(
            name="What was removed",
            value=(
                f"Pages reset: **{as_int(reset.get('pages'))}**\n"
                f"Links: **{as_int(reset.get('links'))}**\n"
                f"Songs: **{as_int(reset.get('songs'))}**\n"
                f"Sessions logged out: **{as_int(reset.get('loggedOutSessions'))}**"
            ),
            inline=False,
        )
        embed.add_field(name="When", value=when, inline=False)
        embed.add_field(name="Triggered from", value=where[:1000], inline=False)
        embed.add_field(name="Sign-up IP", value=code(data.get("signupIp") or "unknown"), inline=True)
        embed.add_field(name="Account created", value=stamp(data.get("createdAt")) or "unknown", inline=True)
        embed.add_field(name="​", value="​", inline=False)
        embed.add_field(name="Last login IP", value=code(data.get("lastLoginIp") or "unknown"), inline=True)
        embed.add_field(name="Last login", value=stamp(data.get("lastLoginAt")) or "unknown", inline=True)
        embed.set_footer(text=FOOTER)
        return embed

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            minutes = max(1, int(error.retry_after // 60) + 1)
            message = f"You can only use this once every 10 minutes. Try again in about {minutes} minute{'s' if minutes != 1 else ''}."
        else:
            message = "Something went wrong running that command."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DuskReset(bot))
