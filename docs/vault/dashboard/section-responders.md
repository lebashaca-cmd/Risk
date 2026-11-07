---
title: Dashboard: Auto-replies
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Auto-replies

Answer messages that match a trigger.

## What it holds

`items`: `trigger` (up to 60), `reply` (up to 500, `{user}` and `{server}`), `match` (contains, exact, starts) and `embed` (VIP).

## Where it is stored and how it is applied

`dashboard.json` under `responders`. The `on_message` listener checks them, skipping bots and ignored channels, with a 10 second repeat guard per trigger.

## Rules and edge cases

Replies never ping anyone.

API: `GET /api/dash/guild/<id>` returns this section under `settings.responders`; `PUT /api/dash/guild/<id>/responders` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
