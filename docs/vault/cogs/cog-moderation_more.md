---
title: moderation_more.py
date: 2026-11-05
tags: [risk, cog]
---

# moderation_more.py

Cog file `cogs/moderation_more.py` (492 lines).

- File: `discord-bot-python/cogs/moderation_more.py` (492 lines)
- Classes: `ConfirmView`, `ModerationMore`
- Data files: `data/tempbans.json`
- Environment variables: none
- Background loops: `unban_loop` (every(minutes=1))
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `addrole` | `giverole` | Gives one role to a member. Usage: !addrole @user @Member | Manage Roles |
| `clonechannel` |  | Makes a copy of a text channel with the same permissions. Usage: !clonechannel #general | Manage Channels |
| `createchannel` | `makechannel` | Creates a text or voice channel. Usage: !createchannel text general-2 | Manage Channels |
| `createrole` |  | Creates a role with no permissions. Usage: !createrole Event Team | Manage Roles |
| `deletechannel` | `delchannel` | Deletes a channel (this one if you name none) after you confirm. Usage: !deletechannel #old-chat | Manage Channels |
| `deleterole` | `delrole` | Deletes a role. Usage: !deleterole @Old Role | Manage Roles |
| `lockdown` |  | Stops @everyone from sending messages in every text channel. Usage: !lockdown raid | Manage Channels |
| `renamechannel` |  | Renames a channel. Usage: !renamechannel #general chat-room | Manage Channels |
| `resetnick` |  | Clears a member's nickname. Usage: !resetnick @user | Manage Nicknames |
| `roleall` |  | Gives a role to every member who doesn't have it. Usage: !roleall @Member | Manage Roles |
| `rolecolor` | `rolecolour` | Changes a role's color. Usage: !rolecolor @Member #ff8800 | Manage Roles |
| `rolename` |  | Renames a role. Usage: !rolename @Member Verified Member | Manage Roles |
| `settopic` |  | Sets this channel's topic, or use `clear` to remove it. Usage: !settopic Daily chat | Manage Channels |
| `tempban` |  | Bans a member and unbans them automatically later. Usage: !tempban @user 3d reason | Ban Members |
| `tempbans` |  | Lists the temporary bans that will end on their own. Usage: !tempbans | Ban Members |
| `unbanall` |  | Unbans everyone in this server after you confirm. Usage: !unbanall | Administrator |
| `unlockdown` |  | Lets @everyone send messages again in every text channel. Usage: !unlockdown | Manage Channels |
| `unroleall` |  | Takes a role away from every member who has it. Usage: !unroleall @Member | Manage Roles |
| `vcdeafen` |  | Server-deafens a member in voice. Usage: !vcdeafen @user | Deafen Members |
| `vcdisconnectall` | `vcclear` | Disconnects everyone from your voice channel except you. Usage: !vcdisconnectall | Move Members |
| `vcmove` |  | Moves a member to another voice channel. Usage: !vcmove @user General | Move Members |
| `vcmute` |  | Server-mutes a member in voice. Usage: !vcmute @user | Mute Members |
| `vcmuteall` |  | Mutes or unmutes everyone in your voice channel except you. Usage: !vcmuteall on | Mute Members |
| `vcundeafen` |  | Removes a server deafen in voice. Usage: !vcundeafen @user | Deafen Members |
| `vcunmute` |  | Removes a server mute in voice. Usage: !vcunmute @user | Mute Members |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
