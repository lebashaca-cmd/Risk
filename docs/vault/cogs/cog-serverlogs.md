---
title: serverlogs.py
date: 2026-11-05
tags: [risk, cog]
---

# serverlogs.py

Cog file `cogs/serverlogs.py` (269 lines).

- File: `discord-bot-python/cogs/serverlogs.py` (269 lines)
- Classes: `ServerLogs`
- Data files: none of its own
- Environment variables: none
- Background loops: none
- Event listeners: `on_raw_message_delete`, `on_raw_bulk_message_delete`, `on_message_edit`, `on_voice_state_update`, `on_member_update`, `on_member_join`, `on_member_remove`, `on_member_ban`, `on_member_unban`, `on_guild_channel_create`, `on_guild_channel_delete`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `logs` |  | Sets the server log channel (deletes, edits, voice, roles). Usage: ,logs #channel | Manage Server |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
