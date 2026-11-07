---
title: VIP commands
date: 2026-11-07
tags: [risk, commands]
---

# VIP commands

50 commands. Run `!help <command>` or see the examples below.

- **autodelete** (needs Manage Channels): VIP Supreme. Deletes new messages in a channel after a delay. Example: `set #channel <minutes> | off #channel | list`
- **autodelete list** (needs Manage Channels): Lists the channels.
- **autodelete off** (needs Manage Channels): Stops deleting in a channel. Example: `#channel`
- **autodelete set** (needs Manage Channels): Deletes messages in the channel after some minutes. Example: `#channel <minutes>`
- **autoreact**: VIP White. Reacts to messages that contain a word. Example: `add <word> <emoji> | remove <word> | list`
- **autoreact add** (needs Manage Server): Reacts with an emoji whenever the word appears. Example: `<word> <emoji>`
- **autoreact list**: Lists the auto reactions.
- **autoreact remove** (needs Manage Server): Removes an auto reaction. Example: `<word>`
- **customcmd**: VIP White. Your own commands that reply with text. Example: `add <name> <reply> | remove <name> | list`
- **customcmd add** (needs Manage Server): Adds a custom command. Example: `<name> <reply>`
- **customcmd list**: Lists this server's custom commands.
- **customcmd remove** (needs Manage Server): Removes a custom command. Example: `<name>`
- **embededit** (needs Manage Messages): VIP White. Edits an embed Risk posted. Example: `<message id`
- **founder**: VIP Lifetime. Shows this server's founding supporter card.
- **lockall** (needs Administrator): VIP Supreme. Stops everyone from sending in every text channel. Example: `[reason]. Undo with !unlockall`
- **membercounter** (needs Manage Channels): VIP Supreme. Keeps a channel's name showing the member count. Example: `set #voice [Members: {count}] | off`
- **membercounter off** (needs Manage Channels): Stops updating.
- **membercounter set** (needs Manage Channels): Picks the channel. Example: `#channel [Members: {count}]`
- **motd**: VIP Lifetime. Shows the server's message of the day. Example: `(set with !motd set <text>, clear with !motd clear)`
- **motd clear** (needs Manage Server): Clears the message of the day.
- **motd set** (needs Manage Server): Sets the message of the day. Example: `<text>`
- **permaudit** (needs Administrator): VIP Supreme. Shows which roles hold powerful permissions and how many members have them.
- **rolereport**: VIP. Lists a role's members, colour and permissions. Example: `@role`
- **schedule** (needs Manage Server): VIP. Repeats a message in a channel. Example: `#channel 6h Your message`
- **schedules** (needs Manage Server): Lists this server's scheduled messages.
- **serverbackup** (needs Administrator): VIP Supreme. Sends a file listing the server's roles and channels.
- **servercard**: VIP. Shows a card with the server's icon, banner and numbers.
- **serverstats**: VIP. Shows a detailed server report.
- **slowmodeall** (needs Manage Channels): VIP Supreme. Sets slowmode on every text channel. Example: `<seconds> (0 turns it off)`
- **stafflist**: VIP White. Lists the staff, grouped by their top role.
- **topmessages**: VIP. Shows who sent the most messages (counted for levels).
- **unlockall** (needs Administrator): VIP Supreme. Undoes !lockall and restores each channel.
- **unschedule** (needs Manage Server): Removes a scheduled message. Example: `<number>`
- **userreport**: VIP. A detailed report on a member: dates, roles, level and money. Example: `[@member]`
- **vip**: Shows this server's VIP status and what VIP unlocks.
- **vipannounce** (needs Manage Messages): VIP. Posts an announcement embed and can ping one role. Example: `#channel [@role] Title | Body`
- **vipcolor** (needs Manage Server): VIP. Sets the accent colour of Risk's embeds here. Example: `#5865f2 (or !vipcolor reset)`
- **vipcommands**: Lists every VIP command and which plan unlocks it.
- **vipembed** (needs Manage Messages): VIP. Posts a custom embed. Example: `#channel #5865f2 Title | Body text`
- **vipgrant**: Owner only. Gives a server VIP for some days (0 = no end). Example: `<server id> [days] [basic|lifetime|white|supreme] [note]`
- **viplist**: Owner only. Lists servers that have VIP.
- **vippoll** (needs Manage Messages): VIP. Posts an embed poll with number reactions. Example: `Question | Option 1 | Option 2 (up to 10)`
- **viprevoke**: Owner only. Removes a server's VIP. Example: `<server id>`
- **viprolecolor** (needs Manage Roles): VIP. Changes a role's colour. Example: `@role #ff0000`
- **vipsay** (needs Manage Messages): VIP. Makes Risk say something, in this or another channel. Example: `[#channel] message`
- **viptier**: Owner only. Changes which plan a VIP server is on. Example: `<server id> <basic|lifetime|white|supreme>`
- **welcomedm** (needs Manage Server): VIP White. Sends new members a private message. Example: `set <text> | off | show`
- **welcomedm off** (needs Manage Server): Turns it off.
- **welcomedm set** (needs Manage Server): Sets the message. Example: `<text>`
- **welcomedm show** (needs Manage Server): Shows the message.

Related: [Commands by category](INDEX.md), [Project index](../INDEX.md)
