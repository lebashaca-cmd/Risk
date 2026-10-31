import difflib
import re

import discord
from discord.ext import commands


class GiveRole(commands.Cog):
    """Prefix command to assign a role by name or partial name."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="r")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def give_role(
        self,
        ctx: commands.Context,
        member: str,
        *,
        role_query: str,
    ):
        """Gives a member a role by name. Usage: ,r @user ROLE or ,r USER_ID ROLE"""

        guild = ctx.guild
        if guild is None:
            return

        # Resolve the member from a mention, raw ID, or name.
        member_id_match = re.fullmatch(r"<@!?(\d+)>", member)
        raw_id_match = re.fullmatch(r"\d{15,22}", member)

        target = None
        if member_id_match:
            target = guild.get_member(int(member_id_match.group(1)))
            if target is None:
                try:
                    target = await guild.fetch_member(int(member_id_match.group(1)))
                except (discord.NotFound, discord.HTTPException):
                    target = None
        elif raw_id_match:
            target = guild.get_member(int(member))
            if target is None:
                try:
                    target = await guild.fetch_member(int(member))
                except (discord.NotFound, discord.HTTPException):
                    target = None
        else:
            # Also permit a cached username/display name as a convenience.
            needle = member.casefold()
            matches = [
                m for m in guild.members
                if m.name.casefold() == needle
                or m.display_name.casefold() == needle
            ]
            if len(matches) == 1:
                target = matches[0]

        if target is None:
            await ctx.reply(
                "I couldn't find that user in this server. Mention them or use their Discord user ID.",
                mention_author=False,
            )
            return

        query = role_query.strip()
        if not query:
            await ctx.reply("Please provide a role name. Example: `,r @user VIP`.", mention_author=False)
            return

        # Prefer an exact, case-insensitive role name match.
        roles = [role for role in guild.roles if role != guild.default_role]
        exact = [role for role in roles if role.name.casefold() == query.casefold()]

        if len(exact) == 1:
            role = exact[0]
        else:
            # Fuzzy matching supports partial words and minor typos, but only
            # assigns automatically when there is one clearly best candidate.
            normalized_query = re.sub(r"\s+", " ", query.casefold()).strip()
            scored = []
            for candidate in roles:
                normalized_name = re.sub(r"\s+", " ", candidate.name.casefold()).strip()
                ratio = difflib.SequenceMatcher(
                    None, normalized_query, normalized_name
                ).ratio()
                query_words = set(normalized_query.split())
                role_words = set(normalized_name.split())
                overlap = len(query_words & role_words) / max(len(query_words), 1)
                contains = normalized_query in normalized_name
                score = max(ratio, overlap * 0.9, 0.92 if contains else 0.0)
                if score >= 0.45:
                    scored.append((score, candidate))

            scored.sort(key=lambda item: item[0], reverse=True)
            if not scored:
                await ctx.reply(
                    f"I couldn't find a role related to `{discord.utils.escape_markdown(query)}`.",
                    mention_author=False,
                )
                return

            best_score = scored[0][0]
            close_matches = [
                role for score, role in scored
                if score >= max(0.45, best_score - 0.08)
            ]

            # If several roles are similarly plausible, ask for a more exact name.
            if len(close_matches) > 1 and (
                len(scored) < 2 or scored[1][0] >= best_score - 0.08
            ):
                choices = "\n".join(
                    f"• {discord.utils.escape_markdown(role.name)}"
                    for role in close_matches[:8]
                )
                await ctx.reply(
                    f"I found multiple roles matching `{discord.utils.escape_markdown(query)}`. "
                    f"Please use a more specific name:\n{choices}",
                    mention_author=False,
                )
                return

            role = scored[0][1]

        if role in target.roles:
            await ctx.reply(
                f"{target.mention} already has the {role.mention} role.",
                mention_author=False,
            )
            return

        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_roles:
            await ctx.reply("I need the **Manage Roles** permission to do that.", mention_author=False)
            return

        if role >= bot_member.top_role:
            await ctx.reply(
                "I can't assign that role because it is equal to or higher than my highest role.",
                mention_author=False,
            )
            return

        if role.managed:
            await ctx.reply(
                "I can't assign that role because it is managed by an integration or another system.",
                mention_author=False,
            )
            return

        try:
            await target.add_roles(role, reason=f"Role assigned by {ctx.author} ({ctx.author.id})")
        except discord.Forbidden:
            await ctx.reply(
                "Discord denied the role assignment. Check my **Manage Roles** permission and role hierarchy.",
                mention_author=False,
            )
            return
        except discord.HTTPException:
            await ctx.reply("Discord returned an error while assigning that role. Please try again.", mention_author=False)
            return

        await ctx.reply(
            f"Assigned {role.mention} to {target.mention}.",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
        )

    @give_role.error
    async def give_role_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            message = "You need the **Manage Roles** permission to use this command."
        elif isinstance(error, commands.MissingRequiredArgument):
            message = "Usage: `,r @user ROLE` or `,r USER_ID ROLE`."
        elif isinstance(error, commands.NoPrivateMessage):
            message = "This command only works inside a server."
        else:
            message = "Something went wrong while trying to assign that role."
        await ctx.reply(message, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveRole(bot))
