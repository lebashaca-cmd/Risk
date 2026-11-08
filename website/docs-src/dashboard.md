# The dashboard

The dashboard is a website where staff change Risk's settings. Everything you can save there is also stored by the bot, so changes take effect right away and the commands and the dashboard always agree.

## Signing in

1. Type `!dashboard` in your server, or open the dashboard link from the main site.
2. Choose **Sign in with Discord** and approve the request. Risk only asks to see your account and the list of servers you are in.
3. Pick a server. Only servers where you have **Manage Server** (or Administrator) and Risk is present are listed.

Risk checks your permissions again on every save, so removing someone's role removes their dashboard access immediately.

## The account bar

At the top you see your Discord profile picture, banner and server tag if you have one, your overall level across the servers Risk shares with you, and quick stats. It is read only.

## Sections

### Overview

A read-only landing page: server stats (members, bots, channels, roles, boosts), a setup checklist that links to the tab each step lives in, how many auto-replies, rules and announcements you have, and the last ten changes made in the dashboard.

### General

- **Prefix.** One to five characters. It is added to the defaults `!`, `?` and `,`.
- **Disabled commands.** Switch a whole command off for the server. Members with Manage Server can still use it.
- **Ignored channels.** Risk does not answer commands in these channels, except for staff.

### Welcome and leave

Pick a channel and write a message. `New_user` is replaced by the member, and you can use any [variable](variables). Wrap the message in `{embed}` to send it as an embed. Turning welcome off keeps your leave settings. See [Welcome and leave](welcome).

### Server logs

Choose the main log channel, send some categories to their own channels, switch categories off and ignore noisy channels. Every dashboard save adds a "Dashboard Updated" entry so you can see who changed what. See [Server logs](logs).

### Levels

Choose where level-ups are announced, write the level-up message, set an XP multiplier and cooldown, add level rewards (a role at a level), choose whether rewards stack or replace each other, and list channels and roles that earn no XP. See [Levels](levels).

### Auto-moderation

Switch on link, invite and spam filters, set the mention limit, manage the blocked-word list (you can import a `.txt` or `.env` file with up to 10,000 words) and list channels and roles that auto-mod ignores. See [Moderation](moderation).

### Community

Autorole, the suggestions channel, starboard channel and threshold, birthday channel, reports channel, counting channel, ticket log channel and the server rules text.

### Commands

Two kinds of rules for commands. **Basic rules** apply to every command, and **command rules** apply to one command. See [Command rules](command-rules).

### Auto-replies

Answer messages that match a trigger. Choose whether the trigger must be contained in the message, be the whole message or start the message. Replies never ping anyone, and the same reply is not repeated more than once every ten seconds. Replies can use [variables](variables). With VIP you can send a reply as an embed.

### Announcements (VIP)

Repeat a message in a channel on a timer from every five minutes up to every 30 days. See [VIP plans](vip).

### VIP

Shows the plan your server is on, when it ends, what it unlocks, and lets you pick the accent colour of Risk's embeds in your server.

## Good to know

- Each section has a **Save** button and a **Discard** button. A section with unsaved changes is marked, and the message under the buttons says so.
- If a section says it is unavailable, the bot is running an older file for that feature. Update the bot and refresh.
- The dashboard cannot do anything your account could not already do in Discord. It cannot grant itself permissions or touch servers you don't manage.
