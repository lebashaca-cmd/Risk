---
title: Architecture
date: 2026-11-05
tags: [risk, architecture]
---

# Architecture

Three parts, two hosts.

| Part | Where | What it is |
|---|---|---|
| Bot | bot-hosting.cloud, folder `discord-bot-python/` | Python, discord.py 2.x. One file per area in `cogs/`, loaded automatically |
| Website and dashboard | Render, folder `website/` | aiohttp server (`server.py`, `dashboard.py`) serving a TypeScript single-page app from `web/` |
| Data | Bot host, `discord-bot-python/data/*.json` | `JsonStore` files, written atomically. The folder is gitignored |

## How the dashboard talks to the bot

1. The browser only ever talks to the website.
2. Sign-in is Discord OAuth2, but the code exchange happens on the **bot** side, because Discord's Cloudflare firewall answers Render's shared IP with an HTML 429. See [Troubleshooting](Troubleshooting.md).
3. The website proxies settings calls to the bot's `/dash/*` routes (registered in `main.py`, handled by `cogs/dashboard.py`). Each call carries a shared `X-Dashboard-Key` and the signed-in user's id.
4. The bot re-checks that the user has Manage Server, Administrator or owns the server on every request, validates each field, and rolls a save back if any part fails.
5. Website sessions live in memory and are lost on a restart (people just sign in again).

## Things worth knowing

- Cogs load in `on_ready`, after the status server starts, so web routes look cogs up lazily with `bot.get_cog(...)`.
- `Dashboard` also owns the per-server prefix (`get_prefix` in `main.py`), disabled commands, ignored channels, command rules and auto-replies.
- Old host files cause crashes. Per-section "availability" checks in the dashboard report a stale cog instead of failing. See [Deploy guide](Deploy-Guide.md).
- `!cogstatus` (owner only) lists which cog files loaded on the host.

Related: [Dashboard](Dashboard.md), [Setup and environment variables](Setup-and-Env-Vars.md), [Decisions](Decisions.md)
