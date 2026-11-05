---
title: FAQ
date: 2026-11-05
tags: [risk, reference, faq]
---

# FAQ

**Why does a command do nothing?** Unknown commands are ignored silently. Usually the new file is not on the host. Run `!cogstatus`.

**Can I change the bot's status per server?** No. Discord has one status for the bot. Nickname, avatar, banner and bio can differ per server.

**How do I give a server VIP?** `!vipgrant <server id> [days]`, or add the id to `VIP_GUILD_IDS`.

**Does VIP cost anything?** There is no payment code. You decide who gets it.

**Where is my data?** In `data/*.json` on the bot host. Back it up.

**Why does the dashboard say a section is unavailable?** An old cog file on the host. Upload the whole folder.

**Can people see each other's servers on the dashboard?** No. They see only servers where they can manage the server and Risk is present.

**Why is TikTok not alerting?** It is unofficial. Run `!tiktoktest @name` while the account is live.

**How do I block lots of words at once?** Dashboard, Auto-moderation, Import from a file (`.txt` or `.env`), or `!badwords import` with the file attached.

**What does `{embed}` do?** Wrap a level, welcome or leave message in it to send an embed.

**How do I add the dashboard subdomain?** [Deploy guide](../Deploy-Guide.md).

Related: [Troubleshooting](../Troubleshooting.md), [Glossary](Glossary.md)
