---
title: Discord limits that shape the code
date: 2026-11-05
tags: [risk, reference]
---

# Discord limits that shape the code

| Limit | Value | Where it matters |
|---|---|---|
| Message content | 2,000 characters | Announcements, auto-replies, level messages are trimmed |
| Embed description | 4,096 | Embeds are cut at 4,000 |
| Embed total | 6,000 | Long lists are paged |
| Embed field value | 1,024 | Field text is trimmed |
| Select menu options | 25 | The command list uses pages |
| Nickname | 32 | Bot profile |
| Per-server bio | 190 | Bot profile |
| Profile edits | Rate limited | A 429 becomes "wait a few minutes" |
| Role hierarchy | Bot can only manage roles below its top role | Reward and auto roles are checked |

Related: [Dashboard validation rules](../dashboard/validation-rules.md), [Message templates](../Message-Templates.md)
