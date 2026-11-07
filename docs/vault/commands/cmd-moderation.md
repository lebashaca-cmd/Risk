---
title: Moderation commands
date: 2026-11-07
tags: [risk, commands]
---

# Moderation commands

62 commands. Run `!help <command>` or see the examples below.

- **addrole** (needs Manage Roles): Gives one role to a member. Example: `@user @Member`
- **antiinvite** (needs Manage Server): Deletes messages with Discord invite links. Example: `on`
- **antilink** (needs Manage Server): Deletes messages with links from members who can't manage messages. Example: `on`
- **antispam** (needs Manage Server): Deletes message floods and times the sender out for 5 minutes. Example: `on`
- **automod** (needs Manage Server): Shows which automod protections are on.
- **automodignore** (needs Manage Server): Toggles a channel or role that automod leaves alone. Example: `#staff-chat`
- **badwords** (needs Manage Server): Manages words that get a message deleted. Actions: add, import, remove, list, clear. Example: `add word`
- **badwords add** (needs Manage Server): Blocks a word or short phrase. Your command message is deleted so the word isn't shown. Example: `word`
- **badwords clear** (needs Manage Server): Removes every blocked word. Example: `confirm`
- **badwords import** (needs Manage Server): Blocks every word in an attached .txt or .env file (one per line, or comma separated). Example: `(attach the file)`
- **badwords list** (needs Manage Server): Sends you the blocked words in a direct message.
- **badwords remove** (needs Manage Server): Unblocks a word. Example: `word`
- **ban** (needs Ban Members): Bans a member from the server. Example: `@user reason`
- **banlist** (needs Ban Members): Shows the first 25 banned users.
- **clear** (needs Manage Messages): Deletes a specified number of messages. Example: `10`
- **clearwarnings** (needs Manage Server): Clears every warning for a member. Example: `@user`
- **clonechannel** (needs Manage Channels): Makes a copy of a text channel with the same permissions. Example: `#general`
- **createchannel** (needs Manage Channels): Creates a text or voice channel. Example: `text general-2`
- **createrole** (needs Manage Roles): Creates a role with no permissions. Example: `Event Team`
- **deletechannel** (needs Manage Channels): Deletes a channel (this one if you name none) after you confirm. Example: `#old-chat`
- **deleterole** (needs Manage Roles): Deletes a role. Example: `@Old Role`
- **delwarn** (needs Manage Messages): Removes one warning by its number. Example: `@user 2`
- **hide** (needs Manage Channels): Hides a channel from @everyone. Example: `#channel`
- **idban** (needs Ban Members): Bans someone by ID, even if they aren't in the server. Example: `123456789 reason`
- **kick** (needs Kick Members): Kicks a member from the server. Example: `@user reason`
- **lock** (needs Manage Channels): Stops @everyone from sending messages in a channel. Example: `#channel`
- **lockdown** (needs Manage Channels): Stops @everyone from sending messages in every text channel. Example: `raid`
- **maxmentions** (needs Manage Server): Deletes messages that mention more than a number of people or roles, or 0 to turn off. Example: `5`
- **nick** (needs Manage Nicknames): Changes or resets a member's nickname. Example: `@user New Name`
- **nuke** (needs Manage Channels): Clones this channel and deletes the old one to wipe all messages. Example: `confirm`
- **purgebots** (needs Manage Messages): Deletes recent messages sent by bots. Example: `50`
- **purgeuser** (needs Manage Messages): Deletes one member's recent messages from this channel. Example: `@user 50`
- **r**: Gives a member a role by name. Example: `@user ROLE`
- **removerole** (needs Manage Roles): Takes a role away from a member. Example: `@user Role`
- **renamechannel** (needs Manage Channels): Renames a channel. Example: `#general chat-room`
- **resetnick** (needs Manage Nicknames): Clears a member's nickname. Example: `@user`
- **roleall** (needs Manage Roles): Gives a role to every member who doesn't have it. Example: `@Member`
- **rolecolor** (needs Manage Roles): Changes a role's color. Example: `@Member #ff8800`
- **rolename** (needs Manage Roles): Renames a role. Example: `@Member Verified Member`
- **settopic** (needs Manage Channels): Sets this channel's topic, or use `clear` to remove it. Example: `Daily chat`
- **slowmode** (needs Manage Channels): Sets slowmode in a channel, or turns it off. Example: `10s`
- **softban** (needs Ban Members): Bans and unbans a member to delete their recent messages. Example: `@user reason`
- **tempban** (needs Ban Members): Bans a member and unbans them automatically later. Example: `@user 3d reason`
- **tempbans** (needs Ban Members): Lists the temporary bans that will end on their own.
- **timeout** (needs Moderate Members): Times a member out so they can't talk. Example: `@user 10m reason`
- **unban** (needs Ban Members): Unbans a user by their ID. Example: `123456789`
- **unbanall** (needs Administrator): Unbans everyone in this server after you confirm.
- **unhide** (needs Manage Channels): Shows a hidden channel to @everyone again. Example: `#channel`
- **unlock** (needs Manage Channels): Lets @everyone send messages in a channel again. Example: `#channel`
- **unlockdown** (needs Manage Channels): Lets @everyone send messages again in every text channel.
- **unroleall** (needs Manage Roles): Takes a role away from every member who has it. Example: `@Member`
- **untimeout** (needs Moderate Members): Removes a timeout from a member. Example: `@user`
- **vcdeafen** (needs Deafen Members): Server-deafens a member in voice. Example: `@user`
- **vcdisconnectall** (needs Move Members): Disconnects everyone from your voice channel except you.
- **vckick** (needs Move Members): Disconnects a member from voice. Example: `@user`
- **vcmove** (needs Move Members): Moves a member to another voice channel. Example: `@user General`
- **vcmute** (needs Mute Members): Server-mutes a member in voice. Example: `@user`
- **vcmuteall** (needs Mute Members): Mutes or unmutes everyone in your voice channel except you. Example: `on`
- **vcundeafen** (needs Deafen Members): Removes a server deafen in voice. Example: `@user`
- **vcunmute** (needs Mute Members): Removes a server mute in voice. Example: `@user`
- **warn** (needs Manage Messages): Warns a member and records it. Example: `@user reason`
- **warnings** (needs Manage Messages): Lists the warnings a member has. Example: `@user`

Related: [Commands by category](INDEX.md), [Project index](../INDEX.md)
