---
title: Guide: writing tests without Discord
date: 2026-11-05
tags: [risk, guide, testing]
---

# Guide: writing tests without Discord

No live Discord was available, so tests use fakes.

- **Fake guild, channel, role, member**: small classes. A channel must subclass `discord.TextChannel` (with `id` set in `__init__`) so `isinstance` checks pass.
- **Load a cog**: `await bot.load_extension("cogs.name")` on a `commands.Bot(intents=discord.Intents.all())`.
- **Stub the store**: `cog.store.save = lambda: None` and reset `cog.store.data`.
- **Call a command**: `await cog.command.callback(cog, ctx, args...)` with a fake `ctx` that has `reply` and `send` recording what is sent.
- **Pass real types**: a test that passes an int where a `timedelta` arrives hides crashes.
- **Browser tests**: Playwright Chromium against a real aiohttp site plus a fake bot app. Redirects to Discord are done by hand because the page cannot reach Discord.
- **Clean state**: delete `data/*.json` between runs.

Related: [Testing](../Testing.md), [Troubleshooting](../Troubleshooting.md)
