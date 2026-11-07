---
title: Dashboard: bot profile
date: 2026-11-05
tags: [risk, dashboard]
---

# Dashboard: bot profile

The card at the top of every server's dashboard. It edits how Risk looks in **that server only**.

| Field | Limit | Notes |
|---|---|---|
| Display name | 32 characters | Empty means the bot's normal name |
| About me (bio) | 190 characters | Kept in `dashboard.json` as well, because the bot cannot read its own per-server bio back |
| Avatar | PNG, JPG or GIF, under 2 MB | Checked by file signature, not just the name |
| Banner | PNG, JPG or GIF, under 3 MB | Same checks |

## How it works

1. The browser reads the file with `FileReader` and shows a live preview.
2. Only changed fields are sent: `PUT /api/dash/guild/<id>/profile`. Images travel as base64 data URLs.
3. The site checks the session and size (up to 7.5 MB), then forwards with a 30 second timeout.
4. The bot decodes and validates, then calls `guild.me.edit(...)`.
5. Discord errors become readable messages: Forbidden asks for Change Nickname, 429 says wait a few minutes.

## Why not status

Discord has one online status for the whole bot, so it cannot differ per server. The card says so.

## Past bug

Large uploads failed with "The request wasn't valid JSON" because the bot read only the first chunk of the body. It now reads the whole body. See [Troubleshooting](../Troubleshooting.md).

Related: [Dashboard](../Dashboard.md), [API reference](api-reference.md), [Validation rules](validation-rules.md)
