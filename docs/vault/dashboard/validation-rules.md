---
title: Dashboard validation rules
date: 2026-11-05
tags: [risk, dashboard, reference]
---

# Dashboard validation rules

Every field is validated on the bot, never trusted from the browser.

| Helper | Rule |
|---|---|
| `as_bool` | Real booleans only |
| `as_int`, `as_float` | Numbers within a range, not booleans or strings |
| `as_text` | Strings with a maximum length, optionally required |
| `as_snowflake` | A Discord id as a string of digits |
| `as_list` | A list up to a maximum length |
| `pick_channel(s)` | Text channels that exist in this server and where the bot can send |
| `pick_role(s)` | Roles that exist. For roles Risk hands out: not `@everyone`, not managed, below the bot's top role |

Saves are all or nothing: a snapshot is taken first and restored if any part fails. Body limits: 20,000 characters for settings (larger for word lists), 7.5 MB for the profile.

Permission check on every request: the user must be Administrator, have Manage Server, or own the server, and must still be in it.

Related: [API reference](api-reference.md), [Security model](../reference/Security-Model.md)
