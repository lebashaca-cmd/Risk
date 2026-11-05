---
title: Dashboard: Community
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Community

Smaller community features.

## What it holds

`autorole`, `suggestionChannel`, `starboardChannel` with `starboardThreshold`, `birthdayChannel`, `reportChannel`, `countingChannel`, `ticketLogChannel`, `rules`.

## Where it is stored and how it is applied

Spread over `community.json`, `suggestions.json`, `community_extra.json` and the ticket cog's config.

## Rules and edge cases

The autorole must be assignable by the bot.

API: `GET /api/dash/guild/<id>` returns this section under `settings.community`; `PUT /api/dash/guild/<id>/community` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
