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

## What is not limited any more

On request, the plan limits on blocked words (up to 10,000), level rewards, XP multiplier (0.1 to 100), auto-replies, command rules and ignored channels were removed. Only very high safety ceilings remain.

## Granting it

- `!vipgrant <server id> [days] [note]`: bot owner only. 0 or no days means no end date.
- `!viprevoke <server id>` and `!viplist`.
- Or list ids in `VIP_GUILD_IDS` on the bot host.
- The website's `/vip` page sells two plans: Monthly and Lifetime. Buttons use `VIP_MONTHLY_URL` and `VIP_LIFETIME_URL` from the site's environment, so any provider that gives a checkout link works. Fulfilment is manual: after a payment, run `!vipgrant <server id> 30` (monthly) or `!vipgrant <server id>` (lifetime).
- `VIP_URL` (an https link) is shown as "Get VIP" in `!vip` and the dashboard.

Settings stay saved if VIP ends. VIP-only features stop running.

Related: [Dashboard](Dashboard.md), [Setup and environment variables](Setup-and-Env-Vars.md), [Decisions](Decisions.md)
