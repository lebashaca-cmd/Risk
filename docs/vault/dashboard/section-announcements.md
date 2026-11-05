---
title: Dashboard: Announcements
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Announcements

Messages repeated on a timer. VIP.

## What it holds

`items`: `channel`, `everyMinutes` (5 to 43,200), `text` (up to 1,500), `on`. The tab shows an upsell on servers without VIP.

## Where it is stored and how it is applied

`vip.json` under `schedules`, sent by the `sender` loop every 60 seconds.

## Rules and edge cases

Existing items keep their next send time when edited without changing the interval.

API: `GET /api/dash/guild/<id>` returns this section under `settings.announcements`; `PUT /api/dash/guild/<id>/announcements` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
