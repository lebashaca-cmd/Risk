---
title: utility_tools.py
date: 2026-11-05
tags: [risk, cog]
---

# utility_tools.py

Cog file `cogs/utility_tools.py` (485 lines).

- File: `discord-bot-python/cogs/utility_tools.py` (485 lines)
- Classes: `UtilityTools`
- Data files: `data/afk.json`, `data/reminders.json`
- Environment variables: none
- Background loops: `reminder_loop` (every(seconds=15))
- Event listeners: `on_message`, `on_message_delete`, `on_message_edit`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `afk_command` |  | Marks you as away. Anyone who pings you is told. Usage: !afk lunch | guild_only |
| `avatar` | `av`, `pfp` | Shows someone's avatar in full size. Usage: !avatar @user |  |
| `banner` |  | Shows someone's profile banner. Usage: !banner @user |  |
| `botinfo` | `about`, `stats` | Shows stats about the bot. Usage: !botinfo |  |
| `calc` | `math` | Does math with + - * / // % and **. Usage: !calc (12 + 8) * 3 |  |
| `channelinfo` |  | Shows details about a channel. Usage: !channelinfo #general | guild_only |
| `color` | `colour` | Previews a hex color. Usage: !color #ff8800 |  |
| `define` | `dictionary` | Looks up the definition of a word. Usage: !define serendipity |  |
| `editsnipe` | `esnipe` | Shows the last edited message in this channel. Usage: !editsnipe | Manage Messages |
| `emojis` |  | Lists this server's custom emojis. Usage: !emojis | guild_only |
| `enlarge` | `emoji` | Shows a custom emoji at full size. Usage: !enlarge :custom_emoji: |  |
| `firstmessage` | `firstmsg` | Links to the first message in this channel. Usage: !firstmessage | guild_only |
| `inrole` |  | Lists members who have a role. Usage: !inrole Moderator | guild_only |
| `invite` |  | Gives the link to add the bot to a server. Usage: !invite |  |
| `membercount` | `members` | Shows how many members the server has. Usage: !membercount | guild_only |
| `permissions` | `perms` | Lists the permissions a member has here. Usage: !permissions @user | guild_only |
| `poll` |  | Starts a reaction poll. Usage: !poll Pizza or tacos? / Pizza / Tacos | guild_only |
| `qr` |  | Makes a QR code from text or a link. Usage: !qr https://example.com |  |
| `reminders_list` |  | Lists your pending reminders. Usage: !reminders |  |
| `remindme` | `remind` | Reminds you later in this channel. Usage: !remindme 1h take out the trash |  |
| `roleinfo` |  | Shows details about a role. Usage: !roleinfo Moderator | guild_only |
| `roles` |  | Lists every role in the server. Usage: !roles | guild_only |
| `serverbanner` |  | Shows the server banner. Usage: !serverbanner | guild_only |
| `servericon` | `guildicon` | Shows the server icon. Usage: !servericon | guild_only |
| `snipe` |  | Shows the last deleted message in this channel. Usage: !snipe | Manage Messages |
| `snowflake` |  | Shows when a Discord ID was created. Usage: !snowflake 123456789012345678 |  |
| `weather` |  | Shows the current weather for a city. Usage: !weather Chicago |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
