---
title: community.py
date: 2026-11-05
tags: [risk, cog]
---

# community.py

Cog file `cogs/community.py` (501 lines).

- File: `discord-bot-python/cogs/community.py` (501 lines)
- Classes: `Community`
- Data files: `data/community.json`, `data/suggestions.json`, `data/tags.json`
- Environment variables: none
- Background loops: none
- Event listeners: `on_member_join`, `on_raw_reaction_add`, `on_raw_reaction_remove`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `approve` |  | Approves a suggestion, with an optional reason. Usage: !approve 12 great idea | Manage Messages |
| `autorole` |  | Shows the role new members get automatically. Usage: !autorole |  |
| `autorole_off` | `remove` | Stops giving new members a role. Usage: !autorole off | has_permissions |
| `autorole_set` |  | Gives new members a role when they join. Usage: !autorole set @Member | has_permissions |
| `autorole_show` |  | Shows the role new members get automatically. Usage: !autorole show |  |
| `deny` |  | Denies a suggestion, with an optional reason. Usage: !deny 12 not right now | Manage Messages |
| `reactionrole` |  | Gives roles when members react to a message. Use add, remove or list. Usage: !reactionrole list |  |
| `reactionrole_add` |  | Adds a reaction role to a message in this channel. Usage: !reactionrole add 123456789012345678 🎮 @Gamer | has_permissions |
| `reactionrole_list` |  | Lists the reaction roles in this server. Usage: !reactionrole list |  |
| `reactionrole_remove` | `delete` | Removes a reaction role from a message. Usage: !reactionrole remove 123456789012345678 🎮 | has_permissions |
| `starboard` |  | Shows the starboard settings. Usage: !starboard |  |
| `starboard_off` |  | Turns the starboard off. Usage: !starboard off | has_permissions |
| `starboard_set` |  | Chooses the starboard channel. Usage: !starboard set #starboard | has_permissions |
| `starboard_show` |  | Shows the starboard channel and star threshold. Usage: !starboard show |  |
| `starboard_threshold` |  | Sets how many stars a message needs, from 1 to 25. Usage: !starboard threshold 5 | has_permissions |
| `suggest` |  | Posts a suggestion for the server to vote on. Usage: !suggest add a music channel |  |
| `suggestchannel` |  | Sets the channel suggestions are posted in, or turns them off. Usage: !suggestchannel #suggestions | Manage Server |
| `tag` |  | Shows a saved tag. Manage them with tag add, edit, remove, list and info. Usage: !tag rules |  |
| `tag_add` | `create` | Creates a tag. Usage: !tag add rules Be kind to each other |  |
| `tag_edit` |  | Changes a tag's text. Usage: !tag edit rules Be kind and have fun |  |
| `tag_info` |  | Shows who made a tag and how often it's used. Usage: !tag info rules |  |
| `tag_list` |  | Lists the tags in this server. Usage: !tag list 2 |  |
| `tag_remove` | `delete`, `del` | Deletes a tag. Usage: !tag remove rules |  |
| `tags_command` |  | Lists the tags in this server. Usage: !tags |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
