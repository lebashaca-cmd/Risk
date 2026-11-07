---
title: community_extra.py
date: 2026-11-05
tags: [risk, cog]
---

# community_extra.py

Cog file `cogs/community_extra.py` (442 lines).

- File: `discord-bot-python/cogs/community_extra.py` (442 lines)
- Classes: `VerifyView`, `CommunityExtra`
- Data files: `data/community_extra.json`
- Environment variables: none
- Background loops: `birthday_loop` (every(minutes=10))
- Event listeners: `on_message`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `birthday` | `bday` | Shows a member's birthday. Also: set, remove, list, next. Usage: !birthday @user |  |
| `birthday_list` |  | Lists birthdays in this server by month. Usage: !birthday list |  |
| `birthday_next` | `upcoming` | Shows the next few birthdays. Usage: !birthday next |  |
| `birthday_remove` | `clear` | Removes your saved birthday. Usage: !birthday remove |  |
| `birthday_set` |  | Saves your birthday as month and day. Usage: !birthday set 05-17 |  |
| `birthdaychannel` |  | Sets where birthday messages go, or turns them off. Usage: !birthdaychannel #birthdays | Manage Server |
| `counting` |  | Shows the counting game status. Actions: set, off, reset. Usage: !counting |  |
| `counting_off` |  | Stops the counting game. Usage: !counting off | has_permissions |
| `counting_reset` |  | Resets the count to zero. Usage: !counting reset | has_permissions |
| `counting_set` |  | Starts the counting game in a channel. Usage: !counting set #counting | has_permissions |
| `note` | `usernote` | Keeps private staff notes about members. Actions: add, list, remove. Usage: !note add @user trusted | has_permissions |
| `note_add` |  | Adds a staff note to a member. Usage: !note add @user helped in the last event | has_permissions |
| `note_list` | `show` | Shows the staff notes for a member. Usage: !note list @user | has_permissions |
| `note_remove` | `delete` | Removes one staff note by its number. Usage: !note remove @user 2 | has_permissions |
| `report` |  | Reports a member to the staff team. Usage: !report @user spamming links |  |
| `reportchannel` |  | Sets the staff channel for member reports, or turns reports off. Usage: !reportchannel #reports | Manage Server |
| `rules` |  | Shows this server's rules. Usage: !rules |  |
| `setrules` |  | Saves the server rules shown by the rules command, or reset to clear them. Usage: !setrules 1. Be kind. 2. No spam. | Manage Server |
| `verifysetup` |  | Posts a Verify button that gives a role to whoever presses it. Usage: !verifysetup #verify @Member | Manage Roles |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
