---
title: Dashboard: VIP
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: VIP

Plan status and VIP extras.

## What it holds

`active`, `source` (env or granted), `until`, `color` (accent colour, VIP only), plus the perks and the free-versus-VIP limit tables.

## Where it is stored and how it is applied

`vip.json`.

## Rules and edge cases

Only the colour is writable.

API: `GET /api/dash/guild/<id>` returns this section under `settings.vip`; `PUT /api/dash/guild/<id>/vip` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
