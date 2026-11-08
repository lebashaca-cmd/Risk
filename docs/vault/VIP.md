---
title: VIP
date: 2026-11-05
tags: [risk, vip]
---

# VIP

A per-server upgrade. It is **not** tied to payments: you decide who gets it.

## What VIP unlocks

- Announcements (messages repeated on a timer, up to 50)
- Embed auto-replies
- An accent colour used for VIP embeds
- Commands: `!vipembed`, `!serverstats`, `!schedule`, `!schedules`, `!unschedule`

## Plans and their commands

A server is on one plan. Each command asks for a group, and the plan decides which groups the server has.

| Plan | Groups it has |
|---|---|
| Basic | Basic |
| Lifetime | Every group: Basic, Lifetime, White and Supreme (never expires) |
| VIP White | Basic and White |
| VIP Supreme | Basic, White and Supreme |
| Server in `VIP_GUILD_IDS` | Every group |

| Group | Commands |
|---|---|
| Basic | `vipcolor`, `vippoll`, `vipsay`, `vipannounce`, `viprolecolor`, `servercard`, `topmessages`, `userreport`, `rolereport`, plus `vipembed`, `serverstats`, `schedule` |
| White | `customcmd` (up to 50, 200 on Supreme), `autoreact`, `welcomedm`, `embededit`, `stafflist` |
| Supreme | `autodelete`, `slowmodeall`, `lockall`, `unlockall`, `serverbackup`, `membercounter`, `permaudit` |
| Lifetime | `founder`, `motd` |

`!vipcommands` shows the same list in Discord and marks what the server has. A server on a lower plan that runs a locked command is told which plan it needs. The code is in [vip-plus.py](cogs/cog-vip-plus.md).

Notes on a few commands:

- `!lockall` saves each channel's old `@everyone` Send Messages setting and `!unlockall` puts exactly that back.
- `!autodelete` only touches messages sent after it is turned on, and keeps pinned messages. It checks every 30 seconds.
- `!membercounter` renames its channel at most every 10 minutes because Discord limits channel renames.
- `!serverbackup` sends a JSON list of roles and channels. It can't restore them by itself.
- Custom commands use the server's prefix and can't reuse the name of a built-in command.

## What is not limited any more

On request, the plan limits on blocked words (up to 10,000), level rewards, XP multiplier (0.1 to 100), auto-replies, command rules and ignored channels were removed. Only very high safety ceilings remain.

## Granting it

- `!vipgrant <server id> [days] [basic|lifetime|white|supreme] [note]`: bot owner only. 0 or no days means no end date. Leave the plan out and it stays as it was (new grants are Basic).
- `!viptier <server id> <plan>`: change the plan of a server that has a grant.
- `!viprevoke <server id>` and `!viplist`.
- Or list ids in `VIP_GUILD_IDS` on the bot host.
- The website's `/vip` page sells four plans in a slider: Basic (monthly), Lifetime, VIP White and VIP Supreme. Buttons use the `VIP_*_URL` variables from the site's environment. The bot has a single VIP level, so White and Supreme extras (priority support and so on) are things you do by hand; their wording is `PLANS` in `website/src/vip.ts`, so any provider that gives a checkout link works. Fulfilment is manual: after a payment, run `!vipgrant <server id> 30` (monthly) or `!vipgrant <server id>` (lifetime).
- `VIP_URL` (an https link) is shown as "Get VIP" in `!vip` and the dashboard.

Settings stay saved if VIP ends. VIP-only features stop running.

Related: [Dashboard](Dashboard.md), [Setup and environment variables](Setup-and-Env-Vars.md), [Decisions](Decisions.md)
