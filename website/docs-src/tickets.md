# Tickets

Tickets are private support channels. A member presses a button on a panel, Risk creates a channel only they and your staff can see, and staff close it when it is done.

## Set it up

1. Make a category for tickets and a staff role.
2. Run `!ticket "category_id" @staff` in the channel where you want the panel. Risk posts a message with an **Open ticket** button.
3. Run `!setlogs #ticket-logs` so closed tickets and transcripts have somewhere to go (also in the dashboard under Community as the ticket log channel).

Run `!ticketpanels` to list panels and `!delpanel <message id>` to turn one off.

## Using a ticket

| Command | What it does |
|---|---|
| `!ticketclaim` / `!ticketunclaim` | Tell others you are handling the ticket |
| `!ticketadd @user` / `!ticketremove @user` | Let someone into the ticket or take them out |
| `!ticketrename name` | Rename the channel |
| `!ticketpriority high` | Set the priority: low, normal, high or urgent |
| `!ticketping` | Ping the person who opened it to ask for a reply |
| `!ticketnote text` / `!ticketnotes` | Private notes for staff |
| `!ticketlock` / `!ticketunlock` | Stop or allow the person who opened it from sending messages |
| `!ticketinfo` | Who opened it, when, who claimed it |
| `!transcript` | Sends a text copy of the conversation without closing |
| `!ticketclose reason` | Closes the ticket and saves a transcript to the log channel |

`!tickets` lists open tickets and `!ticketstats` shows totals.

## Good to know

- Risk needs permission to manage channels so it can create and lock ticket channels.
- Transcripts are plain text, so images appear as links.
