---
title: Account bar
date: 2026-11-07
tags: [risk, dashboard, frontend]
---

# Account bar

The card at the top of the server list and of every server's editor. It shows who is signed in and how they do across all of Risk.

## What it shows

| Part | Source |
|---|---|
| Avatar, display name, `@username` | Discord `/users/@me` at sign-in |
| Banner (or accent colour if no banner) | `banner` and `accent_color` |
| Server tag chip with its badge | `primary_guild` (tag, badge hash, guild id) |
| Nitro and badge chips | `premium_type` and `public_flags` |
| On Discord since | Date inside the user id (snowflake) |
| Overall level and progress bar | Total XP summed across every server, run through `level_for` |
| Total XP, rank, messages, best server level | Levels data in every server |
| Money | Wallet plus bank in every server |
| Servers with Risk, servers you manage, how many are VIP | Bot guild list and the person's permissions |
| Streams and time streamed | Stream stats, keyed by user id |

Rank is the position by total XP among everyone Risk has seen.

## How it works

1. At sign-in the site stores the profile fields on the session. Every field is checked, and only CDN addresses built by the site are used (the page's CSP allows images from Discord's CDN).
2. The page calls `GET /api/dash/account`. The site caches the answer for 30 seconds per session.
3. The site asks the bot with `GET /dash/account`, which reads the person from `X-Dashboard-User`. The route only returns the caller's own numbers.
4. If the stats can't load, the bar still shows the Discord profile and says so.

Code: `read_account` in `cogs/dashboard.py`, `extras` and `account` in `website/dashboard.py`, `accountBar` in `website/src/dashboard.ts`, `.acct-*` in `site.css`.

## Caveats

- The server tag fields come from Discord's newer user object. If a profile has no tag or Discord omits it, the chip is hidden.
- Banner needs the person to have one on Discord.
- Stats only count servers the bot is in.

Related: [Dashboard index](INDEX.md), [Frontend structure](frontend-structure.md), [Sign-in flow](sign-in-flow.md), [API reference](api-reference.md)
