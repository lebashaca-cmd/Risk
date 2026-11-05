---
title: Dashboard: Command rules
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Command rules

Fine control over single commands.

## What it holds

`rules`: for each command `roles` (only these roles), `channels` (only these channels) and `cooldown` (seconds per member).

## Where it is stored and how it is applied

`dashboard.json` under `rules`. Enforced by the global check `command_allowed` in the Dashboard cog.

## Rules and edge cases

Managers bypass rules. `dashboard` itself cannot have rules.

API: `GET /api/dash/guild/<id>` returns this section under `settings.commands`; `PUT /api/dash/guild/<id>/commands` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
