---
title: log_tools.py
date: 2026-11-05
tags: [risk, cog]
---

# log_tools.py

Cog file `cogs/log_tools.py` (372 lines).

- File: `discord-bot-python/cogs/log_tools.py` (372 lines)
- Classes: `LogTools`
- Data files: `data/logtools.json`
- Environment variables: none
- Background loops: none
- Event listeners: `on_guild_role_create`, `on_guild_role_delete`, `on_guild_role_update`, `on_guild_channel_update`, `on_webhooks_update`, `on_guild_emojis_update`, `on_invite_create`, `on_invite_delete`, `on_thread_create`, `on_thread_delete`, `on_thread_update`, `on_guild_update`, `on_member_update`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `logchannel` |  | Sends one log category to its own channel, or back to the main one with off. Usage: !logchannel voice #voice-logs | Manage Server |
| `logevents` |  | Lists every log category and whether it's on. Usage: !logevents | Manage Server |
| `logignore` |  | Stops logging message edits and deletes in a channel. Usage: !logignore #staff-chat | Manage Server |
| `logignored` |  | Lists the channels whose message logs are off. Usage: !logignored | Manage Server |
| `logrecent` |  | Shows the most recent logged events since the bot started. Usage: !logrecent 15 | View Audit Log |
| `logreset` |  | Resets categories, extra channels and ignored channels to the defaults. Usage: !logreset confirm | Manage Server |
| `logsearch` |  | Searches recent logged events for some text. Usage: !logsearch deleted | View Audit Log |
| `logstatus` |  | Shows the log channel and the current log settings. Usage: !logstatus | Manage Server |
| `logtest` |  | Sends a test message to the log channel. Usage: !logtest | Manage Server |
| `logtoggle` |  | Turns a log category off or on. Usage: !logtoggle voice | Manage Server |
| `logunignore` |  | Starts logging message edits and deletes in a channel again. Usage: !logunignore #staff-chat | Manage Server |
| `loguser` |  | Shows recent logged events about a person. Usage: !loguser @user | View Audit Log |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
