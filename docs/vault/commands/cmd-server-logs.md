---
title: Server logs commands
date: 2026-11-07
tags: [risk, commands]
---

# Server logs commands

13 commands. Run `!help <command>` or see the examples below.

- **logchannel** (needs Manage Server): Sends one log category to its own channel, or back to the main one with off. Example: `voice #voice-logs`
- **logevents** (needs Manage Server): Lists every log category and whether it's on.
- **logignore** (needs Manage Server): Stops logging message edits and deletes in a channel. Example: `#staff-chat`
- **logignored** (needs Manage Server): Lists the channels whose message logs are off.
- **logrecent** (needs View Audit Log): Shows the most recent logged events since the bot started. Example: `15`
- **logreset** (needs Manage Server): Resets categories, extra channels and ignored channels to the defaults. Example: `confirm`
- **logs** (needs Manage Server): Sets the server log channel (deletes, edits, voice, roles). Example: `#channel`
- **logsearch** (needs View Audit Log): Searches recent logged events for some text. Example: `deleted`
- **logstatus** (needs Manage Server): Shows the log channel and the current log settings.
- **logtest** (needs Manage Server): Sends a test message to the log channel.
- **logtoggle** (needs Manage Server): Turns a log category off or on. Example: `voice`
- **logunignore** (needs Manage Server): Starts logging message edits and deletes in a channel again. Example: `#staff-chat`
- **loguser** (needs View Audit Log): Shows recent logged events about a person. Example: `@user`

Related: [Commands by category](INDEX.md), [Project index](../INDEX.md)
