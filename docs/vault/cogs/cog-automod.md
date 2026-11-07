---
title: automod.py
date: 2026-11-05
tags: [risk, cog]
---

# automod.py

Cog file `cogs/automod.py` (331 lines).

- File: `discord-bot-python/cogs/automod.py` (331 lines)
- Classes: `AutoMod`
- Data files: `data/automod.json`
- Environment variables: none
- Background loops: none
- Event listeners: `on_message`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `antiinvite` |  | Deletes messages with Discord invite links. Usage: !antiinvite on | Manage Server |
| `antilink` |  | Deletes messages with links from members who can't manage messages. Usage: !antilink on | Manage Server |
| `antispam` |  | Deletes message floods and times the sender out for 5 minutes. Usage: !antispam on | Manage Server |
| `automod` |  | Shows which automod protections are on. Usage: !automod | Manage Server |
| `automodignore` |  | Toggles a channel or role that automod leaves alone. Usage: !automodignore #staff-chat | Manage Server |
| `badwords` | `blockedwords` | Manages words that get a message deleted. Actions: add, import, remove, list, clear. Usage: !badwords add word | has_permissions |
| `badwords_add` |  | Blocks a word or short phrase. Your command message is deleted so the word isn't shown. Usage: !badwords add word | has_permissions |
| `badwords_clear` |  | Removes every blocked word. Usage: !badwords clear confirm | has_permissions |
| `badwords_import` | `upload`, `file` | Blocks every word in an attached .txt or .env file (one per line, or comma separated). Usage: !badwords import (attach the file) | has_permissions |
| `badwords_list` |  | Sends you the blocked words in a direct message. Usage: !badwords list | has_permissions |
| `badwords_remove` | `delete` | Unblocks a word. Usage: !badwords remove word | has_permissions |
| `maxmentions` |  | Deletes messages that mention more than a number of people or roles, or 0 to turn off. Usage: !maxmentions 5 | Manage Server |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
