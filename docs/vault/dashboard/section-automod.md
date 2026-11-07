---
title: Dashboard: Auto-moderation
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Auto-moderation

Automatic message filtering.

## What it holds

`antilink`, `antiinvite`, `antispam`, `maxMentions`, `badWords` (up to 10,000, file import from `.txt` or `.env`), `ignoreChannels`, `ignoreRoles`.

## Where it is stored and how it is applied

`automod.json`.

## Rules and edge cases

Matching is compiled into one pattern, so long word lists stay fast.

API: `GET /api/dash/guild/<id>` returns this section under `settings.automod`; `PUT /api/dash/guild/<id>/automod` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
