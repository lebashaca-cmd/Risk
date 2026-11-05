---
title: Dashboard: Server logs
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Server logs

Where log events go and which ones.

## What it holds

`channel` (main log channel), `disabled` (log categories switched off), `routes` (a category sent to its own channel), `ignoredChannels`.

## Where it is stored and how it is applied

Two stores: ServerLogs keeps `logs_config.json`, LogTools keeps `logtools.json`.

## Rules and edge cases

The dashboard posts a "Dashboard Updated" entry here after each save.

API: `GET /api/dash/guild/<id>` returns this section under `settings.logs`; `PUT /api/dash/guild/<id>/logs` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
