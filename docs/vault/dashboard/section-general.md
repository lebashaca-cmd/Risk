---
title: Dashboard: General
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: General

Bot-wide basics for one server.

## What it holds

`prefix` (1 to 5 characters, replaces the defaults `!`, `?`, `,`), `disabledCommands` (list of top-level command names), `ignoredChannels` (commands are silently ignored there, except from managers).

## Where it is stored and how it is applied

Stored in `dashboard.json`. `get_prefix` in `main.py` reads it for every message.

## Rules and edge cases

Managers (Manage Server or Administrator) bypass disabled commands and ignored channels so they cannot lock themselves out.

API: `GET /api/dash/guild/<id>` returns this section under `settings.general`; `PUT /api/dash/guild/<id>/general` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
