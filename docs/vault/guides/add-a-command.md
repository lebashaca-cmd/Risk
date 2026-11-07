---
title: Guide: add a command
date: 2026-11-05
tags: [risk, guide, dev]
---

# Guide: add a command

1. Pick the cog in `discord-bot-python/cogs/` that fits ([Cogs](../cogs/INDEX.md)), or make a new file with a class and `async def setup(bot)`.
2. Write the command:
   - `@commands.command(name="x")`, optionally `@commands.guild_only()`, `@commands.has_permissions(...)` and `@commands.cooldown(...)`.
   - The first line of the docstring is the help text; end it with `Usage: !x <arg>`.
3. Raise `ModError("message")` for user mistakes. A cog error handler built on `explain_error` turns it into a friendly reply.
4. Mentions: pass `allowed_mentions=NO_MENTIONS` unless a ping is the point.
5. Persist with `JsonStore("name")`: change `store.data`, then `store.save()`.
6. Add the cog's category to `CATEGORY_BY_COG` in `commands_list.py` and in `website/tools/export_bot_data.py`.
7. Regenerate the site list: [Regenerating the command list](regenerate-command-list.md).
8. Test with fake objects: see [Writing tests](writing-tests.md).

Related: [Cogs](../cogs/INDEX.md), [Adding a dashboard section](add-a-dashboard-section.md)
