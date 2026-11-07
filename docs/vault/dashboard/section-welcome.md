---
title: Dashboard: Welcome and leave
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: Welcome and leave

Greeting and goodbye messages.

## What it holds

`enabled` and `channel` with `text`, `leaveEnabled` and `leaveChannel` with `leaveText`. `New_user` is replaced by the member. Wrap in `{embed}` to send an embed.

## Where it is stored and how it is applied

Stored in the Welcome cog's `welcome.json`. Turning welcome off removes only the channel and text, so leave settings survive.

## Rules and edge cases

Channels must be text channels where the bot can send.

API: `GET /api/dash/guild/<id>` returns this section under `settings.welcome`; `PUT /api/dash/guild/<id>/welcome` saves it. See [API reference](api-reference.md).

Related: [Dashboard](../Dashboard.md), [Dashboard sections](INDEX.md), [Validation rules](validation-rules.md)
