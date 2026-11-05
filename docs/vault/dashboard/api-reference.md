---
title: Dashboard API reference
date: 2026-11-05
tags: [risk, dashboard, reference]
---

# Dashboard API reference

## Browser to website (Render)

| Route | Method | What it does |
|---|---|---|
| `/api/auth/login` | GET | Starts Discord sign-in, sets the `risk_oauth` state cookie |
| `/api/auth/callback` | GET | Finishes sign-in, sets the `risk_session` cookie |
| `/api/auth/me` | GET | The signed-in user and the servers they can manage that Risk is in |
| `/api/auth/logout` | POST | Ends the session and revokes the Discord token |
| `/api/dash/guild/<id>` | GET | Settings for all sections, `meta` (channels, roles, commands, limits), `unavailable`, `profile` |
| `/api/dash/guild/<id>/<section>` | PUT | Saves one section |
| `/api/dash/guild/<id>/profile` | PUT | Saves the bot profile (large body allowed) |
| `/api/config`, `/api/status`, `/api/commands`, `/api/tos`, `/api/privacy`, `/healthz` | GET | Public site data |

Writes need the header `X-Requested-With: risk` and a matching Origin.

## Website to bot

All under `/dash/*` on the bot's status server (`main.py` forwards to `Dashboard.handle`). Every call carries `X-Dashboard-Key` (must equal `DASHBOARD_KEY`, compared in constant time) and `X-Dashboard-User`.

| Route | Method | Purpose |
|---|---|---|
| `/dash/oauth` | POST | Exchange the OAuth code, read the user and their servers, revoke the token |
| `/dash/present` | POST | Which of these server ids is Risk in |
| `/dash/guild/<id>` | GET | Read everything for one server |
| `/dash/guild/<id>/<section>` | PUT | Save a section |
| `/dash/guild/<id>/profile` | PUT | Save the bot profile |

## Errors

The bot answers JSON `{ "error": "message" }` with a status code: 400 invalid input, 403 not allowed or VIP only, 404 unknown, 413 too large, 429 Discord rate limit, 500 unexpected (the traceback is printed in the bot log). The site maps non-JSON answers to a readable message.

Related: [Sign-in flow](sign-in-flow.md), [Validation rules](validation-rules.md), [Architecture](../Architecture.md)
