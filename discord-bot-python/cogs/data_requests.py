"""Data requests. People ask for their data to be shown or deleted on the website (or with !mydata / !forgetme in
Discord). The bot posts each website request to the owner with buttons: Show data, Send copy to user,
Delete all data (with a confirm step) and Mark handled. The data itself is found by utils/userdata.py.

Where the message goes: the channel in PRIVACY_CHANNEL_ID if that is set, otherwise the bot owner's DMs.
Only the bot owner (OWNER_IDS, or the Discord application's owner or team) can press the buttons."""
import io
import os
import re
import time

import discord
from discord.ext import commands

from utils import userdata
from utils.helpers import ModError, NO_MENTIONS, explain_error
from utils.store import JsonStore

REF = re.compile(r"DEL-[0-9A-F]{8}")
SNOWFLAKE = re.compile(r"\d{15,21}")
KINDS = {"delete": "Delete my data", "export": "Show / send me my data", "both": "Send me a copy, then delete it"}
MAX_STORED = 1000


def owner_ids():
    return {int(p) for p in re.split(r"[,\s]+", os.getenv("OWNER_IDS", "")) if SNOWFLAKE.fullmatch(p)}


class RequestButton(discord.ui.DynamicItem[discord.ui.Button], template=r"dreq:(?P<action>show|send|delete|confirm|done):(?P<ref>DEL-[0-9A-F]{8})"):
    """One button on a request message. Works after a restart because it is rebuilt from its custom id."""

    LOOKS = {
        "show": ("Show data", discord.ButtonStyle.primary),
        "send": ("Send copy to user", discord.ButtonStyle.secondary),
        "delete": ("Delete all data", discord.ButtonStyle.danger),
        "confirm": ("Yes, delete everything", discord.ButtonStyle.danger),
        "done": ("Mark handled", discord.ButtonStyle.success),
    }

    def __init__(self, action, ref):
        label, style = self.LOOKS[action]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"dreq:{action}:{ref}"))
        self.action, self.ref = action, ref

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["ref"])

    async def callback(self, interaction):
        cog = interaction.client.get_cog("DataRequests")
        if cog is None:
            await interaction.response.send_message("The data request tools aren't loaded.", ephemeral=True)
            return
        await cog.pressed(interaction, self.action, self.ref)


def buttons(ref):
    view = discord.ui.View(timeout=None)
    for action in ("show", "send", "delete", "done"):
        view.add_item(RequestButton(action, ref))
    return view


class DataRequests(commands.Cog, name="DataRequests"):
    """Show or delete everything Risk saved about a person."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("data_requests", default={"requests": []})
        self.store.data.setdefault("requests", [])

    async def cog_load(self):
        self.bot.add_dynamic_items(RequestButton)

    async def cog_unload(self):
        self.bot.remove_dynamic_items(RequestButton)

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # ---------------------------------------------------------------- helpers
    async def is_owner(self, user):
        if user.id in owner_ids():
            return True
        try:
            return await self.bot.is_owner(user)
        except Exception:
            return False

    async def owner_user(self):
        ids = sorted(owner_ids())
        if ids:
            uid = ids[0]
        else:
            info = await self.bot.application_info()
            team = getattr(info, "team", None)
            uid = team.owner_id if team else info.owner.id
        return await self.bot.fetch_user(uid)

    def find(self, ref):
        return next((r for r in self.store.data["requests"] if r["reference"] == ref), None)

    def embed(self, entry, counts=None, kept=None):
        done = entry["status"] != "received"
        embed = discord.Embed(
            title=f"Data request {entry['reference']}",
            description=f"**{KINDS.get(entry['kind'], entry['kind'])}** for <@{entry['user_id']}> (`{entry['user_id']}`)",
            color=discord.Color.green() if done else discord.Color.orange(),
        )
        if entry.get("server_id"):
            embed.add_field(name="Server", value=f"`{entry['server_id']}`", inline=True)
        if entry.get("reach"):
            embed.add_field(name="Reach them at", value=discord.utils.escape_markdown(entry["reach"])[:200], inline=True)
        if entry.get("details"):
            embed.add_field(name="Note", value=discord.utils.escape_markdown(entry["details"])[:500], inline=False)
        if counts is not None:
            text = "\n".join(f"`{name}`: {n}" for name, n in sorted(counts.items())) or "Nothing saved about this user."
            embed.add_field(name="Saved data found", value=text[:1000], inline=False)
        status = {"received": "Waiting for you", "copy_sent": "Copy sent", "deleted": "Data deleted", "handled": "Marked handled"}.get(entry["status"], entry["status"])
        if entry.get("handled_by"):
            status += f" by <@{entry['handled_by']}>"
        embed.add_field(name="Status", value=status, inline=False)
        embed.set_footer(text="Anyone can type another person's ID into the form, so check it's really them before deleting.")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def refresh(self, entry):
        """Updates the original request message after a button was used."""
        if not (entry.get("channel_id") and entry.get("message_id")):
            return
        try:
            channel = self.bot.get_channel(entry["channel_id"]) or await self.bot.fetch_channel(entry["channel_id"])
            message = channel.get_partial_message(entry["message_id"])
            done = entry["status"] in ("deleted", "handled")
            await message.edit(embed=self.embed(entry), view=None if done else buttons(entry["reference"]))
        except discord.HTTPException:
            pass

    # ---------------------------------------------------------------- the website sends requests here
    async def submit(self, body):
        ref = str(body.get("reference", ""))
        user_id = str(body.get("user_id", ""))
        kind = body.get("kind") if body.get("kind") in KINDS else "delete"
        if not REF.fullmatch(ref) or not SNOWFLAKE.fullmatch(user_id):
            return {"error": "That request wasn't valid."}
        entry = self.find(ref)
        if entry is None:
            entry = {
                "reference": ref, "kind": kind, "user_id": user_id,
                "server_id": str(body.get("server_id") or "")[:21] or None,
                "reach": str(body.get("reach") or "")[:120] or None,
                "details": str(body.get("details") or "")[:500] or None,
                "received": str(body.get("received") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                "status": "received", "source": "website",
            }
            self.store.data["requests"] = self.store.data["requests"][-(MAX_STORED - 1):] + [entry]
            self.store.save()
        counts, _ = userdata.summary(self.bot, user_id)
        target = None
        channel_id = os.getenv("PRIVACY_CHANNEL_ID", "").strip()
        try:
            if SNOWFLAKE.fullmatch(channel_id):
                target = self.bot.get_channel(int(channel_id)) or await self.bot.fetch_channel(int(channel_id))
            else:
                target = await (await self.owner_user()).create_dm()
            message = await target.send(embed=self.embed(entry, counts), view=buttons(ref), allowed_mentions=NO_MENTIONS)
        except (discord.HTTPException, AttributeError) as error:
            print(f"[data_requests] could not post {ref}: {error}")
            return {"reference": ref, "delivered": False}
        entry["channel_id"], entry["message_id"] = message.channel.id, message.id
        self.store.save()
        return {"reference": ref, "delivered": True}

    # ---------------------------------------------------------------- buttons
    async def pressed(self, interaction, action, ref):
        if not await self.is_owner(interaction.user):
            await interaction.response.send_message("Only the bot owner can use these buttons.", ephemeral=True)
            return
        entry = self.find(ref)
        if entry is None:
            await interaction.response.send_message(f"I can't find request {ref}. It may have been cleared.", ephemeral=True)
            return
        uid = entry["user_id"]
        if action == "show":
            await interaction.response.defer(ephemeral=True, thinking=True)
            data, counts = userdata.export_json(self.bot, uid)
            text = "\n".join(f"`{name}`: {n}" for name, n in sorted(counts.items())) or "Nothing saved about this user."
            await interaction.followup.send(f"Everything saved about <@{uid}>:\n{text}", file=discord.File(io.BytesIO(data), filename=f"risk-data-{uid}.json"), ephemeral=True, allowed_mentions=NO_MENTIONS)
        elif action == "send":
            await interaction.response.defer(ephemeral=True, thinking=True)
            data, counts = userdata.export_json(self.bot, uid)
            try:
                user = await self.bot.fetch_user(int(uid))
                await user.send(
                    f"Here is a copy of the data Risk has saved about you (request {ref}). If you didn't ask for this, you can ignore it.",
                    file=discord.File(io.BytesIO(data), filename=f"risk-data-{uid}.json"),
                )
            except discord.HTTPException:
                await interaction.followup.send("I couldn't DM them. They may have DMs closed, so use **Show data** and send the file another way.", ephemeral=True)
                return
            entry["status"], entry["handled_by"] = ("copy_sent" if entry["status"] == "received" else entry["status"]), interaction.user.id
            self.store.save()
            await interaction.followup.send("Sent the copy to their DMs.", ephemeral=True)
            await self.refresh(entry)
        elif action == "delete":
            view = discord.ui.View(timeout=300)
            view.add_item(RequestButton("confirm", ref))
            await interaction.response.send_message(
                f"This permanently deletes everything Risk saved about <@{uid}> in every server. It can't be undone. Press the button to confirm.",
                view=view, ephemeral=True, allowed_mentions=NO_MENTIONS,
            )
        elif action == "confirm":
            await interaction.response.defer(ephemeral=True, thinking=True)
            removed = userdata.erase(self.bot, uid)
            entry["status"], entry["handled_by"], entry["handled_at"] = "deleted", interaction.user.id, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            entry["removed"] = removed
            self.store.save()
            try:
                user = await self.bot.fetch_user(int(uid))
                await user.send(f"Risk has deleted the data it saved about you (request {ref}).")
            except discord.HTTPException:
                pass
            text = "\n".join(f"`{name}`: {n}" for name, n in sorted(removed.items())) or "There was nothing saved."
            await interaction.followup.send(f"Deleted everything for <@{uid}>:\n{text}", ephemeral=True, allowed_mentions=NO_MENTIONS)
            await self.refresh(entry)
        elif action == "done":
            entry["status"], entry["handled_by"], entry["handled_at"] = "handled", interaction.user.id, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.store.save()
            await interaction.response.send_message("Marked as handled.", ephemeral=True)
            await self.refresh(entry)

    # ---------------------------------------------------------------- commands for people to use themselves
    @commands.command(name="mydata", aliases=["exportme"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def mydata(self, ctx):
        """Sends you a copy of everything Risk has saved about you, in a private message. Usage: !mydata"""
        data, counts = userdata.export_json(self.bot, ctx.author.id)
        try:
            await ctx.author.send(
                "Here is everything Risk has saved about you:\n" + ("\n".join(f"`{n}`: {c}" for n, c in sorted(counts.items())) or "Nothing is saved about you."),
                file=discord.File(io.BytesIO(data), filename=f"risk-data-{ctx.author.id}.json"),
            )
        except discord.HTTPException:
            raise ModError("I couldn't DM you. Open your DMs for this server and try again.")
        if ctx.guild:
            await ctx.reply("📬 I sent your data to your DMs.", mention_author=False)

    @commands.command(name="forgetme", aliases=["deletemydata"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def forgetme(self, ctx):
        """Deletes everything Risk has saved about you (asks you to confirm first). Usage: !forgetme"""
        counts, _ = userdata.summary(self.bot, ctx.author.id)
        if not counts:
            await ctx.reply("Nothing is saved about you, so there's nothing to delete.", mention_author=False)
            return
        text = "\n".join(f"`{n}`: {c}" for n, c in sorted(counts.items()))
        view = ConfirmForget(ctx.author)
        message = await ctx.reply(f"This permanently deletes the data below in every server. It can't be undone. Your coins, items, levels and warnings all go.\n{text}", view=view, mention_author=False)
        await view.wait()
        if view.confirmed:
            removed = userdata.erase(self.bot, ctx.author.id)
            ref = "DEL-" + os.urandom(4).hex().upper()
            self.store.data["requests"].append({"reference": ref, "kind": "delete", "user_id": str(ctx.author.id), "received": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                "status": "deleted", "source": "command", "removed": removed, "handled_by": ctx.author.id})
            self.store.save()
            await message.edit(content=f"✅ Deleted your data (reference {ref}).", view=None)
        else:
            await message.edit(content="Cancelled. Nothing was deleted.", view=None)


class ConfirmForget(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author, self.confirmed = author, False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your confirmation.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Delete everything", style=discord.ButtonStyle.danger)
    async def yes(self, interaction, button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def no(self, interaction, button):
        await interaction.response.defer()
        self.stop()


async def setup(bot):
    await bot.add_cog(DataRequests(bot))
