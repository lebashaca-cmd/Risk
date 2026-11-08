# Server logs

Server logs write what happens in your server into a channel, so staff can see who deleted a message, who joined, who got a role and what moderators did.

## Turn logging on

1. Make a private channel for staff, like `#server-logs`.
2. Run `!logs #server-logs`. Risk starts posting events there.
3. Run `!logtest` to check it works, and `!logstatus` to see the settings.

## What is logged

Events are grouped into categories. `!logevents` lists them with their on or off state.

| Category | What it records |
|---|---|
| messages | Deleted, bulk-deleted and edited messages |
| voice | Joining, leaving and moving voice channels |
| roles | Roles given or taken, and role changes |
| nicknames | Nickname changes |
| members | Members joining and leaving |
| bans | Bans and unbans |
| channels | Channels created, deleted or changed |
| emojis | Emoji changes |
| invites | Invites created or deleted |
| threads | Threads created, changed or deleted |
| server | Server name, icon and settings |
| timeouts | Timeouts and boosts |
| moderation | Actions from moderation commands (warn, timeout, softban and more) |

## Tuning it

- `!logtoggle voice` turns one category off, and running it again turns it back on.
- `!logchannel voice #voice-logs` sends one category to its own channel. `!logchannel voice off` sends it back to the main one.
- `!logignore #staff-chat` stops logging message edits and deletes in a channel. `!logunignore #staff-chat` undoes it, and `!logignored` lists them.
- `!logreset confirm` puts every setting back to the default.

## Looking things up

- `!logrecent` shows the most recent events since the bot started.
- `!logsearch deleted` searches recent events for some text.
- `!loguser @user` shows recent events about one person.

These three need the View Audit Log permission. They read the bot's recent memory, which is cleared when the bot restarts, so they are for quick checks. The log channel is your permanent record.

## Good to know

- The dashboard has the same controls under **Server logs**, and adds a "Dashboard Updated" entry whenever someone saves a change there.
- Risk needs View Channel and Send Messages in the log channel. If logs stop appearing, check that first.
