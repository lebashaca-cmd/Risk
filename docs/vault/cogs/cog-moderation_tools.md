---
title: moderation_tools.py
date: 2026-11-05
tags: [risk, cog]
---

# moderation_tools.py

Cog file `cogs/moderation_tools.py` (313 lines).

- File: `discord-bot-python/cogs/moderation_tools.py` (313 lines)
- Classes: `ModerationTools`
- Data files: `data/warnings.json`
- Environment variables: none
- Background loops: none
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `banlist` | `bans` | Shows the first 25 banned users. Usage: !banlist | Ban Members |
| `clearwarnings` | `clearwarns` | Clears every warning for a member. Usage: !clearwarnings @user | Manage Server |
| `delwarn` |  | Removes one warning by its number. Usage: !delwarn @user 2 | Manage Messages |
| `hide` |  | Hides a channel from @everyone. Usage: !hide #channel | Manage Channels |
| `idban` | `hackban` | Bans someone by ID, even if they aren't in the server. Usage: !idban 123456789 reason | Ban Members |
| `lock` |  | Stops @everyone from sending messages in a channel. Usage: !lock #channel | Manage Channels |
| `nick` |  | Changes or resets a member's nickname. Usage: !nick @user New Name | Manage Nicknames |
| `nuke` |  | Clones this channel and deletes the old one to wipe all messages. Usage: !nuke confirm | Manage Channels |
| `purgebots` |  | Deletes recent messages sent by bots. Usage: !purgebots 50 | Manage Messages |
| `purgeuser` |  | Deletes one member's recent messages from this channel. Usage: !purgeuser @user 50 | Manage Messages |
| `removerole` | `rr` | Takes a role away from a member. Usage: !removerole @user Role | Manage Roles |
| `slowmode` |  | Sets slowmode in a channel, or turns it off. Usage: !slowmode 10s or !slowmode off | Manage Channels |
| `softban` |  | Bans and unbans a member to delete their recent messages. Usage: !softban @user reason | Ban Members |
| `timeout` | `mute` | Times a member out so they can't talk. Usage: !timeout @user 10m reason | Moderate Members |
| `unhide` |  | Shows a hidden channel to @everyone again. Usage: !unhide #channel | Manage Channels |
| `unlock` |  | Lets @everyone send messages in a channel again. Usage: !unlock #channel | Manage Channels |
| `untimeout` | `unmute` | Removes a timeout from a member. Usage: !untimeout @user | Moderate Members |
| `vckick` |  | Disconnects a member from voice. Usage: !vckick @user | Move Members |
| `warn` |  | Warns a member and records it. Usage: !warn @user reason | Manage Messages |
| `warnings` | `warns` | Lists the warnings a member has. Usage: !warnings @user | Manage Messages |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
