import random
import time

import discord
from discord.ext import commands, tasks

from utils.helpers import Duration, NO_MENTIONS, explain_error
from utils.store import JsonStore

MIN_SECONDS = 10
MAX_SECONDS = 30 * 86400
MAX_WINNERS = 20
PARTY = "🎉"


class EnterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Enter", style=discord.ButtonStyle.primary, emoji=PARTY, custom_id="giveaway:enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Giveaway")
        if cog is None:
            await interaction.response.send_message("Giveaways are unavailable right now.", ephemeral=True)
            return
        await cog.handle_click(interaction)


class Giveaway(commands.Cog):
    """Timed giveaways with an Enter button. Entries and winners are saved, so they survive restarts."""

    def __init__(self, bot):
        self.bot = bot
        self.store = JsonStore("giveaways")

    async def cog_load(self):
        self.bot.add_view(EnterView())
        self.sweep.start()

    def cog_unload(self):
        self.sweep.cancel()

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Data
    def guild_data(self, guild_id):
        return self.store.data.setdefault(str(guild_id), {})

    def find(self, guild_id, message_id):
        return self.guild_data(guild_id).get(str(message_id))

    def latest(self, guild_id, ended=None):
        items = [(int(mid), g) for mid, g in self.guild_data(guild_id).items() if ended is None or g["ended"] == ended]
        return max(items, key=lambda item: item[0], default=(None, None))

    def won_count(self, guild_id, user_id):
        return sum(1 for g in self.guild_data(guild_id).values() if user_id in g.get("winners", []))

    def entered_count(self, guild_id, user_id):
        return sum(1 for g in self.guild_data(guild_id).values() if user_id in g.get("entries", []))

    # Embeds
    def build_embed(self, giveaway, host):
        ended = giveaway["ended"]
        if giveaway.get("drop"):
            title = f"{PARTY} Drop: {giveaway['prize']}"
        else:
            title = f"{PARTY} {giveaway['prize']}"
        embed = discord.Embed(title=title[:250], color=discord.Color.dark_grey() if ended else discord.Color.gold())
        if giveaway.get("drop"):
            embed.description = "First to press **Enter** wins." if not ended else "This drop is over."
        else:
            when = f"<t:{giveaway['ends']}:R> (<t:{giveaway['ends']}:f>)"
            embed.description = ("Ended " if ended else "Ends ") + when
        embed.add_field(name="Hosted by", value=f"<@{giveaway['host']}>")
        embed.add_field(name="Winners", value=str(giveaway["winner_count"]))
        embed.add_field(name="Entries", value=str(len(giveaway["entries"])))
        if giveaway.get("role"):
            embed.add_field(name="Requires", value=f"<@&{giveaway['role']}>", inline=False)
        if ended and giveaway.get("winners"):
            embed.add_field(name="Won by", value=" ".join(f"<@{uid}>" for uid in giveaway["winners"])[:1000], inline=False)
        elif ended:
            embed.add_field(name="Won by", value="Nobody entered.", inline=False)
        embed.set_footer(text="Giveaway ended" if ended else "Press the button to enter. Press again to leave.")
        return embed

    async def message_for(self, guild, message_id, giveaway):
        channel = guild.get_channel(giveaway["channel"])
        if channel is None:
            return None, None
        try:
            return channel, await channel.fetch_message(int(message_id))
        except discord.HTTPException:
            return channel, None

    # Buttons
    async def handle_click(self, interaction):
        giveaway = self.find(interaction.guild_id, interaction.message.id) if interaction.guild_id else None
        if giveaway is None:
            await interaction.response.send_message("I can't find this giveaway any more.", ephemeral=True)
            return
        if giveaway["ended"]:
            await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
            return
        user = interaction.user
        if user.bot:
            return
        role_id = giveaway.get("role")
        if role_id and not any(role.id == role_id for role in getattr(user, "roles", [])):
            await interaction.response.send_message(f"You need the <@&{role_id}> role to enter.", ephemeral=True)
            return
        if giveaway.get("drop"):
            giveaway["entries"].append(user.id)
            giveaway["winners"] = [user.id]
            await self.finish(interaction.guild, interaction.message.id, giveaway, message=interaction.message)
            await interaction.response.send_message("You got it!", ephemeral=True)
            return
        if user.id in giveaway["entries"]:
            giveaway["entries"].remove(user.id)
            text = "You left the giveaway."
        else:
            giveaway["entries"].append(user.id)
            text = f"You're in! There are now {len(giveaway['entries'])} entries."
        giveaway["dirty"] = True
        self.store.save()
        await interaction.response.send_message(text, ephemeral=True)

    # Finishing
    def pick(self, guild, giveaway, exclude=()):
        pool = []
        for uid in dict.fromkeys(giveaway["entries"]):
            member = guild.get_member(uid)
            if member is None or member.bot or uid in exclude:
                continue
            role_id = giveaway.get("role")
            if role_id and not any(role.id == role_id for role in member.roles):
                continue
            pool.append(uid)
        return random.sample(pool, min(giveaway["winner_count"], len(pool)))

    async def finish(self, guild, message_id, giveaway, message=None):
        if giveaway["ended"]:
            return
        giveaway["ended"] = True
        giveaway.pop("dirty", None)
        if not giveaway.get("drop"):
            giveaway["winners"] = self.pick(guild, giveaway)
        self.store.save()
        channel = guild.get_channel(giveaway["channel"])
        if channel is None:
            return
        if message is None:
            try:
                message = await channel.fetch_message(int(message_id))
            except discord.HTTPException:
                message = None
        if message is not None:
            try:
                await message.edit(embed=self.build_embed(giveaway, None), view=None)
            except discord.HTTPException:
                pass
        winners = giveaway.get("winners", [])
        if winners:
            mentions = " ".join(f"<@{uid}>" for uid in winners)
            text = f"{PARTY} Congratulations {mentions}! You won **{giveaway['prize']}**."
            allowed = discord.AllowedMentions(users=[discord.Object(uid) for uid in winners])
        else:
            text = f"No valid entries, so nobody won **{giveaway['prize']}**."
            allowed = NO_MENTIONS
        try:
            await channel.send(text[:1900], reference=message if message is not None else None, allowed_mentions=allowed)
        except discord.HTTPException:
            pass

    @tasks.loop(seconds=15)
    async def sweep(self):
        now = int(time.time())
        for guild_id, items in list(self.store.data.items()):
            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue
            for message_id, giveaway in list(items.items()):
                if giveaway["ended"]:
                    continue
                if not giveaway.get("drop") and giveaway["ends"] <= now:
                    await self.finish(guild, message_id, giveaway)
                elif giveaway.pop("dirty", False):
                    channel, message = await self.message_for(guild, message_id, giveaway)
                    if message is not None:
                        try:
                            await message.edit(embed=self.build_embed(giveaway, None))
                        except discord.HTTPException:
                            pass

    @sweep.before_loop
    async def before_sweep(self):
        await self.bot.wait_until_ready()

    # Commands
    async def launch(self, ctx, seconds, winners, prize, drop=False, role=None):
        seconds = int(seconds.total_seconds()) if hasattr(seconds, "total_seconds") else seconds
        if not drop and not MIN_SECONDS <= seconds <= MAX_SECONDS:
            await ctx.reply("A giveaway must last between 10 seconds and 30 days.", mention_author=False)
            return
        if not 1 <= winners <= MAX_WINNERS:
            await ctx.reply(f"Pick between 1 and {MAX_WINNERS} winners.", mention_author=False)
            return
        prize = prize.strip()
        if not prize or len(prize) > 200:
            await ctx.reply("Give a prize name of up to 200 characters.", mention_author=False)
            return
        permissions = ctx.channel.permissions_for(ctx.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await ctx.reply("I need Send Messages and Embed Links in this channel.", mention_author=False)
            return
        active = sum(1 for g in self.guild_data(ctx.guild.id).values() if not g["ended"])
        if active >= 10:
            await ctx.reply("This server already has 10 active giveaways. End one first.", mention_author=False)
            return
        giveaway = {
            "channel": ctx.channel.id, "host": ctx.author.id, "prize": prize, "winner_count": 1 if drop else winners,
            "ends": int(time.time()) + (0 if drop else seconds), "ended": False, "entries": [], "winners": [],
            "role": role.id if role else None, "drop": drop, "created": int(time.time()),
        }
        message = await ctx.send(embed=self.build_embed(giveaway, ctx.author), view=EnterView(), allowed_mentions=NO_MENTIONS)
        self.guild_data(ctx.guild.id)[str(message.id)] = giveaway
        self.store.save()
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

    @commands.group(name="giveaway", aliases=["gw", "gstart"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def giveaway(self, ctx, duration: Duration = None, winners: int = 1, *, prize: str = ""):
        """Starts a giveaway: duration, winners, prize. Also: start, drop, end, reroll, cancel, list, info, require. Usage: ,giveaway 1h 2 Discord Nitro"""
        if duration is None or not prize:
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{PARTY} Giveaways",
                    description=(
                        "`,giveaway 1h 2 Discord Nitro` starts one (1 hour, 2 winners)\n"
                        "`,giveaway drop Free role` first person to press Enter wins\n"
                        "`,giveaway end [id]` ends one now\n"
                        "`,giveaway reroll [id]` picks new winners\n"
                        "`,giveaway cancel [id]` removes one without a winner\n"
                        "`,giveaway list` shows the active ones\n"
                        "`,giveaway info [id]` shows entries and winners\n"
                        "`,giveaway require <id> @role|off` limits who can enter"
                    ),
                    color=discord.Color.gold(),
                ),
                mention_author=False,
            )
            return
        await self.launch(ctx, duration, winners, prize)

    @giveaway.command(name="start", aliases=["create"])
    @commands.has_permissions(manage_guild=True)
    async def giveaway_start(self, ctx, duration: Duration, winners: int, *, prize: str):
        """Starts a giveaway with a time limit. Usage: ,giveaway start 30m 1 Steam gift card"""
        await self.launch(ctx, duration, winners, prize)

    @giveaway.command(name="drop")
    @commands.has_permissions(manage_guild=True)
    async def giveaway_drop(self, ctx, *, prize: str):
        """Starts a drop where the first person to press Enter wins. Usage: ,giveaway drop Free role"""
        await self.launch(ctx, 0, 1, prize, drop=True)

    async def resolve(self, ctx, message_id, ended=None):
        if message_id is not None:
            giveaway = self.find(ctx.guild.id, message_id)
            if giveaway is None:
                await ctx.reply("I can't find a giveaway with that message ID. See `,giveaway list`.", mention_author=False)
                return None, None
            return message_id, giveaway
        mid, giveaway = self.latest(ctx.guild.id, ended)
        if giveaway is None:
            await ctx.reply("There's no giveaway to use. Start one with `,giveaway 1h 1 Prize`.", mention_author=False)
            return None, None
        return mid, giveaway

    @giveaway.command(name="end", aliases=["stop"])
    @commands.has_permissions(manage_guild=True)
    async def giveaway_end(self, ctx, message_id: int = None):
        """Ends a giveaway now and picks winners. Usage: ,giveaway end 123456789012345678"""
        mid, giveaway = await self.resolve(ctx, message_id, ended=False)
        if giveaway is None:
            return
        if giveaway["ended"]:
            await ctx.reply("That giveaway already ended. Use `,giveaway reroll` for new winners.", mention_author=False)
            return
        await self.finish(ctx.guild, mid, giveaway)

    @giveaway.command(name="reroll")
    @commands.has_permissions(manage_guild=True)
    async def giveaway_reroll(self, ctx, message_id: int = None):
        """Picks new winners for a finished giveaway. Usage: ,giveaway reroll 123456789012345678"""
        mid, giveaway = await self.resolve(ctx, message_id, ended=True)
        if giveaway is None:
            return
        if not giveaway["ended"]:
            await ctx.reply("That giveaway is still running. End it first.", mention_author=False)
            return
        winners = self.pick(ctx.guild, giveaway)
        if not winners:
            await ctx.reply("There are no valid entries to pick from.", mention_author=False)
            return
        giveaway["winners"] = winners
        self.store.save()
        _, message = await self.message_for(ctx.guild, mid, giveaway)
        if message is not None:
            try:
                await message.edit(embed=self.build_embed(giveaway, None))
            except discord.HTTPException:
                pass
        mentions = " ".join(f"<@{uid}>" for uid in winners)
        await ctx.send(f"{PARTY} New winner{'s' if len(winners) > 1 else ''}: {mentions}! You won **{giveaway['prize']}**.", allowed_mentions=discord.AllowedMentions(users=[discord.Object(u) for u in winners]))

    @giveaway.command(name="cancel", aliases=["delete"])
    @commands.has_permissions(manage_guild=True)
    async def giveaway_cancel(self, ctx, message_id: int = None):
        """Removes a giveaway without picking a winner. Usage: ,giveaway cancel 123456789012345678"""
        mid, giveaway = await self.resolve(ctx, message_id, ended=False)
        if giveaway is None:
            return
        self.guild_data(ctx.guild.id).pop(str(mid), None)
        self.store.save()
        _, message = await self.message_for(ctx.guild, mid, giveaway)
        if message is not None:
            try:
                await message.edit(content="🚫 This giveaway was cancelled.", embed=None, view=None)
            except discord.HTTPException:
                pass
        await ctx.reply("Giveaway cancelled.", mention_author=False)

    @giveaway.command(name="list")
    async def giveaway_list(self, ctx):
        """Lists the giveaways that are running. Usage: ,giveaway list"""
        rows = []
        for mid, g in sorted(self.guild_data(ctx.guild.id).items(), key=lambda item: item[1]["ends"]):
            if g["ended"]:
                continue
            when = "first click" if g.get("drop") else f"<t:{g['ends']}:R>"
            rows.append(f"**{g['prize'][:60]}**: {len(g['entries'])} entries, {when}, <#{g['channel']}> (`{mid}`)")
        if not rows:
            await ctx.reply("No giveaways are running.", mention_author=False)
            return
        await ctx.reply(embed=discord.Embed(title="Active giveaways", description="\n".join(rows[:10]), color=discord.Color.gold()), mention_author=False, allowed_mentions=NO_MENTIONS)

    @giveaway.command(name="info", aliases=["entries"])
    async def giveaway_info(self, ctx, message_id: int = None):
        """Shows a giveaway's entries and winners. Usage: ,giveaway info 123456789012345678"""
        mid, giveaway = await self.resolve(ctx, message_id)
        if giveaway is None:
            return
        embed = self.build_embed(giveaway, None)
        embed.add_field(name="Message ID", value=f"`{mid}`", inline=False)
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    @giveaway.command(name="require")
    @commands.has_permissions(manage_guild=True)
    async def giveaway_require(self, ctx, message_id: int, role: str):
        """Limits a giveaway to members with a role, or removes the limit with off. Usage: ,giveaway require 123456789012345678 @Member"""
        giveaway = self.find(ctx.guild.id, message_id)
        if giveaway is None or giveaway["ended"]:
            await ctx.reply("I can't find a running giveaway with that message ID.", mention_author=False)
            return
        if role.lower() == "off":
            giveaway["role"] = None
            text = "Anyone can enter now."
        else:
            try:
                found = await commands.RoleConverter().convert(ctx, role)
            except commands.BadArgument:
                await ctx.reply("I couldn't find that role. Use a @role mention, a name or `off`.", mention_author=False)
                return
            giveaway["role"] = found.id
            text = f"Only members with {found.mention} can enter now."
        giveaway["dirty"] = True
        self.store.save()
        await ctx.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
