---
title: Dashboard: Levels
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Levels

XP, level-up messages and rewards.

## What it holds

`announce` (where level-ups go), `message` (`{user}`, `{name}`, `{level}`, `{embed}`), `mode` (stack or replace roles), `rewards` (level to role), `multiplier` (0.1 to 100), `cooldown` (1 to 3600 seconds), `noxpChannels`, `noxpRoles`.

## Where it is stored and how it is applied

`levels.json` and `level_settings.json`. XP is flushed to disk by a loop.

## Rules and edge cases

Reward roles must be assignable: not managed, not the default role, below the bot's top role.

API: `GET /api/dash/guild/<id>` returns this section under `settings.levels`; `PUT /api/dash/guild/<id>/levels` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
