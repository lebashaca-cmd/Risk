---
title: giveaway.py
date: 2026-11-05
tags: [risk, cog]
---

# giveaway.py

Cog file `cogs/giveaway.py` (393 lines).

- File: `discord-bot-python/cogs/giveaway.py` (393 lines)
- Classes: `EnterView`, `Giveaway`
- Data files: `data/giveaways.json`
- Environment variables: none
- Background loops: `sweep` (every(seconds=15))
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `giveaway` | `gw`, `gstart` | Starts a giveaway: duration, winners, prize. Also: start, drop, end, reroll, cancel, list, info, require. Usage: ,giveaway 1h 2 Discord Nitro | has_permissions |
| `giveaway_cancel` | `delete` | Removes a giveaway without picking a winner. Usage: ,giveaway cancel 123456789012345678 | has_permissions |
| `giveaway_drop` |  | Starts a drop where the first person to press Enter wins. Usage: ,giveaway drop Free role | has_permissions |
| `giveaway_end` | `stop` | Ends a giveaway now and picks winners. Usage: ,giveaway end 123456789012345678 | has_permissions |
| `giveaway_info` | `entries` | Shows a giveaway's entries and winners. Usage: ,giveaway info 123456789012345678 |  |
| `giveaway_list` |  | Lists the giveaways that are running. Usage: ,giveaway list |  |
| `giveaway_require` |  | Limits a giveaway to members with a role, or removes the limit with off. Usage: ,giveaway require 123456789012345678 @Member | has_permissions |
| `giveaway_reroll` |  | Picks new winners for a finished giveaway. Usage: ,giveaway reroll 123456789012345678 | has_permissions |
| `giveaway_start` | `create` | Starts a giveaway with a time limit. Usage: ,giveaway start 30m 1 Steam gift card | has_permissions |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
