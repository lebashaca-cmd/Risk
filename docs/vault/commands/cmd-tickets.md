---
title: Tickets commands
date: 2026-11-05
tags: [risk, commands]
---

# Tickets commands

20 commands. Run `!help <command>` or see the examples below.

- **delpanel** (needs Manage Server): Turns off a ticket panel by its message ID. Example: `123456789012345678`
- **setlogs** (needs Manage Server): Sets the log channel for tickets. Example: `#channel`
- **ticket** (needs Manage Channels): Posts the ticket panel. Example: `"category_id" @staff`
- **ticketadd**: Adds someone to the current ticket. Example: `@user`
- **ticketclaim**: Claims the current ticket so others know you're handling it.
- **ticketclose**: Closes the current ticket with a reason and saves a transcript to the log channel. Example: `resolved`
- **ticketinfo**: Shows details about a ticket. Example: `#ticket-name`
- **ticketlock**: Stops the ticket's opener from sending messages.
- **ticketnote**: Saves a private staff note on the ticket and hides your message. Example: `customer wants a refund`
- **ticketnotes**: Sends you this ticket's staff notes by direct message.
- **ticketpanels** (needs Manage Server): Lists the ticket panels that are active.
- **ticketping**: Pings the ticket's opener to ask for a reply.
- **ticketpriority**: Sets the ticket priority: low, normal, high or urgent. Example: `high`
- **ticketremove**: Removes someone from the current ticket. Example: `@user`
- **ticketrename**: Renames the current ticket channel. Example: `billing-issue`
- **tickets** (needs Manage Channels): Lists the open tickets in this server.
- **ticketstats** (needs Manage Channels): Shows a summary of open tickets.
- **ticketunclaim**: Releases your claim on the current ticket.
- **ticketunlock**: Lets the ticket's opener send messages again.
- **transcript**: Sends a text transcript of the current ticket without closing it.

Related: [Commands by category](INDEX.md), [Project index](../INDEX.md)
