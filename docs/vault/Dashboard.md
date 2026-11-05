---
title: Dashboard
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard

Owners and admins sign in with Discord, pick a server Risk is in, and change its settings. Address: `dashboard.<domain>/<server id>`.

## Top of the page: bot profile

A card like Discord's "Customize profile". It changes Risk's display name, avatar, banner and bio **in that one server** (Discord keeps these per server). Status is global on Discord, so it cannot be set per server. Needs the Change Nickname permission; Discord limits how often it can change.

## Tabs

| Tab | What it holds |
|---|---|
| Overview | Server stats, setup checklist, what is in use, recent changes |
| General | Prefix, switched-off commands, ignored channels |
| Welcome and leave | Messages and channels (supports `{embed}`, see [Message templates](Message-Templates.md)) |
| Server logs | Log channel and which events to log |
| Levels | Level-up message, channel, rewards, XP multiplier, cooldown, no-XP channels and roles |
| Auto-moderation | Links, invites, spam, blocked words (import from a `.txt` or `.env` file) |
| Community | Auto role, suggestions, starboard, birthdays, reports, counting, rules, tickets |
| Command rules | Per-command roles, channels and cooldown. Managers bypass them |
| Auto-replies | Trigger and reply, with `{user}` and `{server}` |
| Announcements (VIP) | Messages repeated on a timer |
| VIP | Plan status, perks and an accent colour |

## Saving and safety

- Each tab saves on its own. Unsaved changes are kept per tab and the browser warns before leaving.
- The bot validates every field, re-checks permissions, and rolls a failed save back.
- Every save is recorded in "Recent changes" and posted to the server's logs as "Dashboard Updated".
- CSRF: `X-Requested-With: risk` header plus an Origin check. Strict CSP on the site.

Related: [Architecture](Architecture.md), [VIP](VIP.md), [Troubleshooting](Troubleshooting.md)
