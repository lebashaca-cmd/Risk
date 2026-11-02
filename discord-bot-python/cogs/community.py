import time
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from utils.helpers import NO_MENTIONS, explain_error
from utils.store import JsonStore

TAG_RESERVED = {"add", "edit", "remove", "delete", "del", "list", "info"}
STAR = "⭐"
MAX_TAGS = 200


def emoji_key(emoji):
    """A stable key for an emoji: the ID for custom emoji, the character for Unicode ones."""
    return str(emoji.id) if getattr(emoji, "id", None) else str(emoji.name if hasattr(emoji, "name") else emoji)


async def parse_channel(ctx, target):
    try:
        return await commands.TextChannelConverter().convert(ctx, target)
    except commands.BadArgument:
        return None


class Community(commands.Cog):
    """Suggestions, tags, auto roles, reaction roles and the starboard."""

    def __init__(self, bot):
        self.bot = bot
        self.suggestions = JsonStore("suggestions")
        self.tags = JsonStore("tags")
        self.settings = JsonStore("community")

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def cog_command_error(self, ctx, error):
        if not await explain_error(ctx, error):
            raise error

    # Data helpers
    def sugg(self, guild_id):
        data = self.suggestions.data.setdefault(str(guild_id), {})
        data.setdefault("channel", None)
        data.setdefault("count", 0)
        data.setdefault("items", {})
        return data

    def tag_data(self, guild_id):
        return self.tags.data.setdefault(str(guild_id), {})

    def cfg(self, guild_id):
        data = self.settings.data.setdefault(str(guild_id), {})
        data.setdefault("autorole", None)
        data.setdefault("reactionroles", {})
        data.setdefault("starboard", {"channel": None, "threshold": 3, "posted": {}})
        return data

    @staticmethod
    def can_give(guild, role):
        """True if the bot is able to hand out this role."""
        return role is not None and not role.is_default() and not role.managed and role < guild.me.top_role

    # ---------------------------------------------------------------- suggestions
    @commands.command(name="suggestchannel")
    @commands.has_permissions(manage_guild=True)
    async def suggestchannel(self, ctx, target: str):
        """Sets the channel suggestions are posted in, or turns them off. Usage: !suggestchannel #suggestions"""
        data = self.sugg(ctx.guild.id)
        if target.lower() == "off":
            data["channel"] = None
            self.suggestions.save()
            await ctx.reply("Suggestions are turned off.", mention_author=False)
            return
        channel = await parse_channel(ctx, target)
        if channel is None:
            await ctx.reply("Use a #channel or `off`.", mention_author=False)
            return
        perms = channel.permissions_for(ctx.guild.me)
        if not (perms.send_messages and perms.embed_links and perms.add_reactions):
            await ctx.reply(f"I need Send Messages, Embed Links and Add Reactions in {channel.mention}.", mention_author=False)
            return
        data["channel"] = channel.id
        self.suggestions.save()
        await ctx.reply(f"Suggestions will be posted in {channel.mention}.", mention_author=False)

    @commands.command(name="suggest")
    async def suggest(self, ctx, *, idea: str):
        """Posts a suggestion for the server to vote on. Usage: !suggest add a music channel"""
        data = self.sugg(ctx.guild.id)
        channel = ctx.guild.get_channel(data["channel"]) if data["channel"] else None
        if channel is None:
            await ctx.reply("Suggestions aren't set up. A staff member can use `!suggestchannel #channel`.", mention_author=False)
            return
        if len(idea) > 1000:
            await ctx.reply("Keep suggestions under 1,000 characters.", mention_author=False)
            return
        data["count"] += 1
        number = data["count"]
        embed = discord.Embed(title=f"Suggestion #{number}", description=idea, color=discord.Color.gold(), timestamp=datetime.now(timezone.utc))
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Status", value="Pending")
        try:
            message = await channel.send(embed=embed, allowed_mentions=NO_MENTIONS)
            await message.add_reaction("👍")
            await message.add_reaction("👎")
        except discord.HTTPException:
            data["count"] -= 1
            await ctx.reply("I couldn't post in the suggestion channel.", mention_author=False)
            return
        data["items"][str(number)] = {"user": ctx.author.id, "text": idea, "message": message.id, "status": "pending", "reason": None}
        self.suggestions.save()
        await ctx.reply(f"Posted as suggestion #{number} in {channel.mention}.", mention_author=False)

    async def decide(self, ctx, number, status, reason):
        data = self.sugg(ctx.guild.id)
        item = data["items"].get(str(number))
        channel = ctx.guild.get_channel(data["channel"]) if data["channel"] else None
        if item is None or channel is None:
            await ctx.reply(f"I can't find suggestion #{number}.", mention_author=False)
            return
        try:
            message = await channel.fetch_message(item["message"])
        except discord.NotFound:
            await ctx.reply("That suggestion's message was deleted.", mention_author=False)
            return
        approved = status == "approved"
        embed = message.embeds[0] if message.embeds else discord.Embed(title=f"Suggestion #{number}", description=item["text"])
        embed.color = discord.Color.green() if approved else discord.Color.red()
        embed.clear_fields()
        embed.add_field(name="Status", value=f"{'✅ Approved' if approved else '❌ Denied'} by {ctx.author.display_name}")
        if reason:
            embed.add_field(name="Reason", value=reason[:1000], inline=False)
        await message.edit(embed=embed)
        item["status"], item["reason"] = status, reason
        self.suggestions.save()
        await ctx.reply(f"Suggestion #{number} {status}.", mention_author=False)

    @commands.command(name="approve")
    @commands.has_permissions(manage_messages=True)
    async def approve(self, ctx, number: int, *, reason: str = None):
        """Approves a suggestion, with an optional reason. Usage: !approve 12 great idea"""
        await self.decide(ctx, number, "approved", reason)

    @commands.command(name="deny")
    @commands.has_permissions(manage_messages=True)
    async def deny(self, ctx, number: int, *, reason: str = None):
        """Denies a suggestion, with an optional reason. Usage: !deny 12 not right now"""
        await self.decide(ctx, number, "denied", reason)

    # ----------------------------------------------------------------------- tags
    @commands.group(name="tag", invoke_without_command=True)
    async def tag(self, ctx, name: str = None):
        """Shows a saved tag. Manage them with tag add, edit, remove, list and info. Usage: !tag rules"""
        if name is None:
            await ctx.reply("Show a tag with `!tag name`, or see `!tag list`.", mention_author=False)
            return
        tags = self.tag_data(ctx.guild.id)
        entry = tags.get(name.lower())
        if entry is None:
            await ctx.reply(f"There's no tag called `{name[:32]}`. See `!tag list`.", mention_author=False, allowed_mentions=NO_MENTIONS)
            return
        entry["uses"] += 1
        self.tags.save()
        await ctx.send(entry["text"], allowed_mentions=NO_MENTIONS)

    @staticmethod
    def clean_tag_name(name):
        name = name.lower().strip()
        if not 1 <= len(name) <= 32:
            return None, "Tag names must be 1 to 32 characters."
        if name in TAG_RESERVED:
            return None, f"`{name}` is reserved. Pick another name."
        return name, None

    @tag.command(name="add", aliases=["create"])
    async def tag_add(self, ctx, name: str, *, text: str):
        """Creates a tag. Usage: !tag add rules Be kind to each other"""
        name, error = self.clean_tag_name(name)
        if error:
            await ctx.reply(error, mention_author=False)
            return
        if len(text) > 1500:
            await ctx.reply("Tag text can be up to 1,500 characters.", mention_author=False)
            return
        tags = self.tag_data(ctx.guild.id)
        if name in tags:
            await ctx.reply(f"A tag named `{name}` already exists. Use `!tag edit`.", mention_author=False)
            return
        if len(tags) >= MAX_TAGS:
            await ctx.reply(f"This server has reached {MAX_TAGS} tags.", mention_author=False)
            return
        tags[name] = {"text": text, "owner": ctx.author.id, "created": int(time.time()), "uses": 0}
        self.tags.save()
        await ctx.reply(f"Created tag `{name}`.", mention_author=False)

    def can_manage_tag(self, ctx, entry):
        return ctx.author.id == entry["owner"] or ctx.author.guild_permissions.manage_messages

    @tag.command(name="edit")
    async def tag_edit(self, ctx, name: str, *, text: str):
        """Changes a tag's text. Usage: !tag edit rules Be kind and have fun"""
        entry = self.tag_data(ctx.guild.id).get(name.lower())
        if entry is None:
            await ctx.reply("I can't find that tag.", mention_author=False)
            return
        if not self.can_manage_tag(ctx, entry):
            await ctx.reply("Only the tag's owner or a moderator can edit it.", mention_author=False)
            return
        if len(text) > 1500:
            await ctx.reply("Tag text can be up to 1,500 characters.", mention_author=False)
            return
        entry["text"] = text
        self.tags.save()
        await ctx.reply(f"Updated tag `{name.lower()}`.", mention_author=False)

    @tag.command(name="remove", aliases=["delete", "del"])
    async def tag_remove(self, ctx, name: str):
        """Deletes a tag. Usage: !tag remove rules"""
        tags = self.tag_data(ctx.guild.id)
        entry = tags.get(name.lower())
        if entry is None:
            await ctx.reply("I can't find that tag.", mention_author=False)
            return
        if not self.can_manage_tag(ctx, entry):
            await ctx.reply("Only the tag's owner or a moderator can remove it.", mention_author=False)
            return
        del tags[name.lower()]
        self.tags.save()
        await ctx.reply(f"Removed tag `{name.lower()}`.", mention_author=False)

    async def send_tag_list(self, ctx, page):
        names = sorted(self.tag_data(ctx.guild.id))
        if not names:
            await ctx.reply("This server has no tags yet. Add one with `!tag add name text`.", mention_author=False)
            return
        pages = -(-len(names) // 30)
        page = max(1, min(page, pages))
        chunk = names[(page - 1) * 30: page * 30]
        embed = discord.Embed(title=f"Tags ({len(names)})", description=", ".join(f"`{n}`" for n in chunk), color=discord.Color.light_grey())
        embed.set_footer(text=f"Page {page} of {pages}")
        await ctx.reply(embed=embed, mention_author=False)

    @tag.command(name="list")
    async def tag_list(self, ctx, page: int = 1):
        """Lists the tags in this server. Usage: !tag list 2"""
        await self.send_tag_list(ctx, page)

    @commands.command(name="tags")
    async def tags_command(self, ctx, page: int = 1):
        """Lists the tags in this server. Usage: !tags"""
        await self.send_tag_list(ctx, page)

    @tag.command(name="info")
    async def tag_info(self, ctx, name: str):
        """Shows who made a tag and how often it's used. Usage: !tag info rules"""
        entry = self.tag_data(ctx.guild.id).get(name.lower())
        if entry is None:
            await ctx.reply("I can't find that tag.", mention_author=False)
            return
        embed = discord.Embed(title=name.lower()[:32], color=discord.Color.light_grey())
        embed.add_field(name="Owner", value=f"<@{entry['owner']}>")
        embed.add_field(name="Uses", value=str(entry["uses"]))
        embed.add_field(name="Created", value=f"<t:{entry['created']}:R>")
        await ctx.reply(embed=embed, mention_author=False, allowed_mentions=NO_MENTIONS)

    # ------------------------------------------------------------------- autorole
    async def show_autorole(self, ctx):
        role_id = self.cfg(ctx.guild.id)["autorole"]
        role = ctx.guild.get_role(role_id) if role_id else None
        text = f"New members get {role.mention}." if role else "No auto role is set. Use `!autorole set @role`."
        await ctx.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)

    @commands.group(name="autorole", invoke_without_command=True)
    async def autorole(self, ctx):
        """Shows the role new members get automatically. Usage: !autorole"""
        await self.show_autorole(ctx)

    @autorole.command(name="show")
    async def autorole_show(self, ctx):
        """Shows the role new members get automatically. Usage: !autorole show"""
        await self.show_autorole(ctx)

    @autorole.command(name="set")
    @commands.has_permissions(manage_roles=True)
    async def autorole_set(self, ctx, role: discord.Role):
        """Gives new members a role when they join. Usage: !autorole set @Member"""
        if not self.can_give(ctx.guild, role):
            await ctx.reply("I can't hand out that role. Move my role above it, and don't pick @everyone or a bot role.", mention_author=False)
            return
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.reply("That role is above your highest role.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["autorole"] = role.id
        self.settings.save()
        await ctx.reply(f"New members will get {role.mention}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @autorole.command(name="off", aliases=["remove"])
    @commands.has_permissions(manage_roles=True)
    async def autorole_off(self, ctx):
        """Stops giving new members a role. Usage: !autorole off"""
        self.cfg(ctx.guild.id)["autorole"] = None
        self.settings.save()
        await ctx.reply("The auto role is turned off.", mention_author=False)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        role_id = self.cfg(member.guild.id)["autorole"]
        role = member.guild.get_role(role_id) if role_id else None
        if not self.can_give(member.guild, role):
            return
        try:
            await member.add_roles(role, reason="Auto role")
        except discord.HTTPException:
            pass

    # -------------------------------------------------------------- reaction roles
    @commands.group(name="reactionrole", invoke_without_command=True)
    async def reactionrole(self, ctx):
        """Gives roles when members react to a message. Use add, remove or list. Usage: !reactionrole list"""
        await ctx.reply("Use `!reactionrole add <message id> <emoji> @role`, `remove <message id> <emoji>` or `list`.", mention_author=False)

    @reactionrole.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_add(self, ctx, message_id: int, emoji: str, role: discord.Role):
        """Adds a reaction role to a message in this channel. Usage: !reactionrole add 123456789012345678 🎮 @Gamer"""
        if not self.can_give(ctx.guild, role):
            await ctx.reply("I can't hand out that role. Move my role above it, and don't pick @everyone or a bot role.", mention_author=False)
            return
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.reply("That role is above your highest role.", mention_author=False)
            return
        partial = discord.PartialEmoji.from_str(emoji)
        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            await ctx.reply("I can't find that message. Run this command in the channel it's in.", mention_author=False)
            return
        mapping = self.cfg(ctx.guild.id)["reactionroles"].setdefault(str(message_id), {})
        if len(mapping) >= 20 and emoji_key(partial) not in mapping:
            await ctx.reply("A message can have up to 20 reaction roles.", mention_author=False)
            return
        try:
            await message.add_reaction(partial)
        except discord.HTTPException:
            await ctx.reply("I couldn't react with that emoji. Use a standard emoji or one from this server.", mention_author=False)
            return
        mapping[emoji_key(partial)] = {"role": role.id, "channel": ctx.channel.id, "label": str(partial)}
        self.settings.save()
        await ctx.reply(f"Reacting with {partial} on that message now gives {role.mention}.", mention_author=False, allowed_mentions=NO_MENTIONS)

    @reactionrole.command(name="remove", aliases=["delete"])
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_remove(self, ctx, message_id: int, emoji: str):
        """Removes a reaction role from a message. Usage: !reactionrole remove 123456789012345678 🎮"""
        partial = discord.PartialEmoji.from_str(emoji)
        mapping = self.cfg(ctx.guild.id)["reactionroles"].get(str(message_id), {})
        if mapping.pop(emoji_key(partial), None) is None:
            await ctx.reply("That message doesn't have that reaction role.", mention_author=False)
            return
        if not mapping:
            self.cfg(ctx.guild.id)["reactionroles"].pop(str(message_id), None)
        self.settings.save()
        await ctx.reply("Removed that reaction role.", mention_author=False)

    @reactionrole.command(name="list")
    async def reactionrole_list(self, ctx):
        """Lists the reaction roles in this server. Usage: !reactionrole list"""
        rows = []
        for message_id, mapping in self.cfg(ctx.guild.id)["reactionroles"].items():
            for entry in mapping.values():
                rows.append(f"{entry['label']} → <@&{entry['role']}> on [message](https://discord.com/channels/{ctx.guild.id}/{entry['channel']}/{message_id})")
        if not rows:
            await ctx.reply("There are no reaction roles. Add one with `!reactionrole add`.", mention_author=False)
            return
        await ctx.reply(embed=discord.Embed(title="Reaction roles", description="\n".join(rows)[:4000], color=discord.Color.light_grey()), mention_author=False, allowed_mentions=NO_MENTIONS)

    async def reaction_role(self, payload, add):
        if payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        mapping = self.cfg(guild.id)["reactionroles"].get(str(payload.message_id))
        entry = mapping.get(emoji_key(payload.emoji)) if mapping else None
        if entry is None:
            return
        member = payload.member if add and payload.member else guild.get_member(payload.user_id)
        role = guild.get_role(entry["role"])
        if member is None or member.bot or not self.can_give(guild, role):
            return
        try:
            if add:
                await member.add_roles(role, reason="Reaction role")
            else:
                await member.remove_roles(role, reason="Reaction role")
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.reaction_role(payload, True)
        await self.star_check(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.reaction_role(payload, False)

    # ------------------------------------------------------------------ starboard
    @commands.group(name="starboard", invoke_without_command=True)
    async def starboard(self, ctx):
        """Shows the starboard settings. Usage: !starboard"""
        await self.starboard_show(ctx)

    @starboard.command(name="show")
    async def starboard_show(self, ctx):
        """Shows the starboard channel and star threshold. Usage: !starboard show"""
        board = self.cfg(ctx.guild.id)["starboard"]
        channel = ctx.guild.get_channel(board["channel"]) if board["channel"] else None
        text = f"Messages with {board['threshold']} ⭐ go to {channel.mention}." if channel else "The starboard is off. Use `!starboard set #channel`."
        await ctx.reply(text, mention_author=False)

    @starboard.command(name="set")
    @commands.has_permissions(manage_guild=True)
    async def starboard_set(self, ctx, channel: discord.TextChannel):
        """Chooses the starboard channel. Usage: !starboard set #starboard"""
        perms = channel.permissions_for(ctx.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await ctx.reply(f"I need Send Messages and Embed Links in {channel.mention}.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["starboard"]["channel"] = channel.id
        self.settings.save()
        await ctx.reply(f"Starred messages will be posted in {channel.mention}.", mention_author=False)

    @starboard.command(name="off")
    @commands.has_permissions(manage_guild=True)
    async def starboard_off(self, ctx):
        """Turns the starboard off. Usage: !starboard off"""
        self.cfg(ctx.guild.id)["starboard"]["channel"] = None
        self.settings.save()
        await ctx.reply("The starboard is off.", mention_author=False)

    @starboard.command(name="threshold")
    @commands.has_permissions(manage_guild=True)
    async def starboard_threshold(self, ctx, stars: int):
        """Sets how many stars a message needs, from 1 to 25. Usage: !starboard threshold 5"""
        if not 1 <= stars <= 25:
            await ctx.reply("Pick a number from 1 to 25.", mention_author=False)
            return
        self.cfg(ctx.guild.id)["starboard"]["threshold"] = stars
        self.settings.save()
        await ctx.reply(f"Messages now need {stars} ⭐.", mention_author=False)

    async def star_check(self, payload):
        if payload.guild_id is None or str(payload.emoji) != STAR:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        board = self.cfg(guild.id)["starboard"]
        target = guild.get_channel(board["channel"]) if board["channel"] else None
        if target is None or payload.channel_id == target.id or str(payload.message_id) in board["posted"]:
            return
        source = guild.get_channel(payload.channel_id)
        if source is None:
            return
        try:
            message = await source.fetch_message(payload.message_id)
        except discord.HTTPException:
            return
        reaction = next((r for r in message.reactions if str(r.emoji) == STAR), None)
        if reaction is None:
            return
        stars = [user async for user in reaction.users() if user.id != message.author.id and not user.bot]
        if len(stars) < board["threshold"] or str(message.id) in board["posted"]:
            return
        board["posted"][str(message.id)] = 0  # claim it first so two quick reactions don't post twice
        embed = discord.Embed(description=message.content[:3500] or None, color=discord.Color.gold(), timestamp=message.created_at)
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        image = next((a for a in message.attachments if (a.content_type or "").startswith("image/")), None)
        if image:
            embed.set_image(url=image.url)
        embed.add_field(name="Original", value=f"[Jump to message]({message.jump_url})", inline=False)
        try:
            sent = await target.send(content=f"{STAR} **{len(stars)}** in {source.mention}", embed=embed, allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            board["posted"].pop(str(message.id), None)
            return
        board["posted"][str(message.id)] = sent.id
        self.settings.save()


async def setup(bot):
    await bot.add_cog(Community(bot))
