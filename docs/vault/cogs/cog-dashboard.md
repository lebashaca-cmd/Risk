---
title: dashboard.py
date: 2026-11-05
tags: [risk, cog]
---

# dashboard.py

Settings API for the website dashboard, plus per-server prefix and command switches.

The website signs people in with Discord and forwards their requests here with a shared key
(DASHBOARD_KEY). Every request is checked again in this file: the user must be the server owner
or hold Administrator or Manage Server in that server, and every value is validated.

- File: `discord-bot-python/cogs/dashboard.py` (1020 lines)
- Classes: `ApiError`, `Dashboard`
- Data files: `data/dashboard.json`
- Environment variables: `DASHBOARD_KEY`, `DASHBOARD_URL`, `DISCORD_API`, `DISCORD_CLIENT_SECRET`, `VIP_URL`
- Background loops: none
- Event listeners: `on_message`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `dashboard` | `settings` | Shows the link to the website dashboard where staff change Risk's settings. Usage: !dashboard | guild_only |
| `prefix` |  | Shows or changes this server's extra prefix (the defaults ! ? , always work). Usage: !prefix $ | guild_only |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
