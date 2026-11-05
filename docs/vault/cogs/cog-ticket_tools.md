---
title: ticket_tools.py
date: 2026-11-05
tags: [risk, cog]
---

# ticket_tools.py

Cog file `cogs/ticket_tools.py` (371 lines).

- File: `discord-bot-python/cogs/ticket_tools.py` (371 lines)
- Classes: `TicketTools`
- Data files: none of its own
- Environment variables: none
- Background loops: none
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `delpanel` |  | Turns off a ticket panel by its message ID. Usage: !delpanel 123456789012345678 | Manage Server |
| `ticketadd` |  | Adds someone to the current ticket. Usage: !ticketadd @user |  |
| `ticketclaim` |  | Claims the current ticket so others know you're handling it. Usage: !ticketclaim |  |
| `ticketclose` | `closeticket` | Closes the current ticket with a reason and saves a transcript to the log channel. Usage: !ticketclose resolved |  |
| `ticketinfo` |  | Shows details about a ticket. Usage: !ticketinfo #ticket-name |  |
| `ticketlock` |  | Stops the ticket's opener from sending messages. Usage: !ticketlock |  |
| `ticketnote` |  | Saves a private staff note on the ticket and hides your message. Usage: !ticketnote customer wants a refund |  |
| `ticketnotes` |  | Sends you this ticket's staff notes by direct message. Usage: !ticketnotes |  |
| `ticketpanels` |  | Lists the ticket panels that are active. Usage: !ticketpanels | Manage Server |
| `ticketping` |  | Pings the ticket's opener to ask for a reply. Usage: !ticketping |  |
| `ticketpriority` |  | Sets the ticket priority: low, normal, high or urgent. Usage: !ticketpriority high |  |
| `ticketremove` |  | Removes someone from the current ticket. Usage: !ticketremove @user |  |
| `ticketrename` |  | Renames the current ticket channel. Usage: !ticketrename billing-issue |  |
| `tickets_list` | `opentickets` | Lists the open tickets in this server. Usage: !tickets | has_permissions |
| `ticketstats` |  | Shows a summary of open tickets. Usage: !ticketstats | Manage Channels |
| `ticketunclaim` |  | Releases your claim on the current ticket. Usage: !ticketunclaim |  |
| `ticketunlock` |  | Lets the ticket's opener send messages again. Usage: !ticketunlock |  |
| `transcript_command` |  | Sends a text transcript of the current ticket without closing it. Usage: !transcript |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
