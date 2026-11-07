---
title: vip.py
date: 2026-11-05
tags: [risk, cog]
---

# vip.py

Risk VIP: a per-server upgrade that raises limits and unlocks extra features.

VIP is granted by the bot owner (`!vipgrant`) or by listing server ids in the VIP_GUILD_IDS environment
variable. It is not tied to any payment system. Other cogs ask `is_vip(guild_id)` and `limit(guild_id, key)`.

- File: `discord-bot-python/cogs/vip.py` (285 lines)
- Classes: `VIP`
- Data files: `data/vip.json`
- Environment variables: `VIP_GUILD_IDS`, `VIP_URL`
- Background loops: `sender` (every(seconds=60))
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `schedule` |  | VIP. Repeats a message in a channel. Usage: !schedule #channel 6h Your message | Manage Server |
| `schedules_cmd` |  | Lists this server's scheduled messages. Usage: !schedules | guild_only, has_permissions |
| `serverstats` |  | VIP. Shows a detailed server report. Usage: !serverstats | guild_only |
| `unschedule` |  | Removes a scheduled message. Usage: !unschedule <number> | Manage Server |
| `vip` |  | Shows this server's VIP status and what VIP unlocks. Usage: !vip | guild_only |
| `vipembed` |  | VIP. Posts a custom embed. Usage: !vipembed #channel #5865f2 Title / Body text | Manage Messages |
| `vipgrant` |  | Owner only. Gives a server VIP for some days (0 = no end). Usage: !vipgrant <server id> [days] [note] | is_owner |
| `viplist` |  | Owner only. Lists servers that have VIP. Usage: !viplist | is_owner |
| `viprevoke` |  | Owner only. Removes a server's VIP. Usage: !viprevoke <server id> | is_owner |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
