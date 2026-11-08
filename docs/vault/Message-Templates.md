---
title: Message templates
date: 2026-11-05
tags: [risk, messages]
---

# Message templates

| Token | Works in | Meaning |
|---|---|---|
| `{user}` | Level-up message | Mentions the member |
| `{name}` | Level-up message | Their display name |
| `{level}` | Level-up message | The new level |
| `New_user` | Welcome and leave messages | Mention (welcome) or name (leave) |
| `{user}`, `{server}` | Auto-replies | Display name and server name |
| `{embed}` at the very start **and** very end | Level-up, welcome, leave | Sends the message as an embed |

## Variables

Since PR 19 (later) every message that takes a template also fills in the variables from `discord-bot-python/utils/variables.py`: about 50 of them for the member, server, channel, time, random picks, emoji and level stats. Examples: `{server.members}`, `{ordinal}`, `{user.age}`, `{random:1-100}`, `{choose:a|b|c}`, `{xp}`, `{nextlevel}`. The registry `VARIABLES` is the single list: `!variables`, the docs site and the tests all read it. Unknown tokens are left as typed, and member-controlled text has `@` broken so it can't ping. `!testvars <text>` previews a message. The public list is on the docs site, [Docs site](website/docs-site.md).

Example: `{embed} GG {user}, you reached level {level}! {embed}`

In an embed the member is shown in bold with their avatar, and a normal mention is sent above it so they still get the ping. Leave messages never ping. The embed uses the VIP accent colour when the server has one.

Related: [Dashboard](Dashboard.md), [VIP](VIP.md)
