# Community tools

Smaller features that make a server feel alive.

## Giveaways

- `!giveaway start 30m 1 Steam gift card` runs a giveaway for 30 minutes with one winner. People enter with a reaction or button.
- `!giveaway end`, `!giveaway cancel`, `!giveaway reroll`, `!giveaway list` and `!giveaway info` manage them.
- `!giveaway drop` starts a quick first-to-claim drop.
- `!giveaway require <id> @Member` limits a giveaway to a role, and `off` removes the limit.

All giveaway commands need Manage Server.

## Starboard

Messages that collect enough star reactions are copied to a starboard channel. `!starboard set #starboard` chooses the channel, `!starboard threshold 3` sets how many stars it takes, `!starboard show` shows the settings and `!starboard off` turns it off.

## Suggestions

Members use `!suggest add a music channel` and the suggestion is posted for everyone to vote on. Staff pick the channel with `!suggestchannel #suggestions` and answer with `!approve` or `!deny` and an optional reason.

## Birthdays

Members save theirs with `!birthday set 05-17` (month and day). Staff choose where birthday messages go with `!birthdaychannel #birthdays`. `!birthday list` and `!birthday next` show what's coming.

## Counting game

`!counting set #counting` starts a channel where everyone counts up together. A wrong number resets the count. `!counting reset` and `!counting off` give you control.

## Reaction roles and verify

- `!reactionrole add <message id> 🎮 @Gamer` gives a role to anyone who reacts with that emoji on a message in the current channel. Remove with `!reactionrole remove` and list with `!reactionrole list`.
- `!verifysetup #verify @Member` posts a **Verify** button. Whoever presses it receives the role.
- `!autorole set @Member` gives every new member a role when they join. `!autorole show` and `!autorole off` manage it.

## Tags

Tags are short saved answers. `!tag add rules Be kind to each other` saves one, `!tag rules` shows it, and `!tags` lists them all. `!tag edit`, `!tag remove` and `!tag info` manage them.

## Rules and reports

`!setrules 1. Be kind. 2. No spam.` saves the rules and `!rules` shows them. Members can use `!report @user spamming links`, which goes to the staff channel you choose with `!reportchannel #reports`.

## Staff notes

`!note add @user text`, `!note list @user` and `!note remove` keep private notes about members. Only people with Manage Messages can see them.

## Sticky messages

`!sticky` keeps a message pinned at the bottom of a channel, reposting it as people talk. `!unsticky` removes it.

## Rep

Rep thanks members who put your server invite in their Discord custom status. When someone's custom status contains the rep text, Risk posts a pink embed with their username, profile picture, status text and the time in Central time.

- `!rep text discord.gg/yourinvite` sets the text to look for. Capitals don't matter and it can sit anywhere in the status.
- `!rep channel #rep` picks where the embeds go.
- `!rep test` posts a sample. `!rep` shows the setup and `!rep off` turns it off.

Each member is posted once while Risk is running. If they remove the text and add it back later, they are posted again. Rep needs the **Presence intent**: turn it on in the Developer Portal (Bot, Privileged Gateway Intents), set `PRESENCE_INTENT=1` on the bot host and restart Risk. You need Manage Server to set it up.

## Events, groups and member extras

- **Events:** `!event add in 2h30m Movie night` or `!event add 2026-12-01 18:00 Game night` (UTC). `!event` lists them, `!event join 3` / `!event leave 3` RSVP, `!event info 3` shows who is going, `!event cancel 3` removes one (the host or a moderator).
- **Looking for group:** `!lfg 4 Minecraft survival night` posts a card with a Join / leave button; the host closes it.
- **Games and pronouns:** `!mygames add Valorant`, `!whoplays Valorant`, `!pronouns set she/her`.
- **Conversation starters:** `!icebreaker`, `!debate`, `!hottake`, `!shoutout @user thanks`, `!spotlight` (today's member), `!anniversaries` (join anniversaries this month).
- **Groups and games:** `!pairup @role`, `!bracket a, b, c, d`, `!draftorder a, b, c`, `!bingo`.
- **Server pulse:** `!pulse` shows messages over 1, 7 and 30 days and the busiest channels.

## Good to know

- Most of these settings can also be changed in the dashboard under **Community**.
- Reaction roles, autorole and verify only work for roles that sit below Risk's role.
