---
title: Owner control panel
date: 2026-11-09
tags: [risk, owner, security]
---

# Owner control panel

Two ways for the owner to control the bot. Both use the same bot-side code, `cogs/owner_control.py`.

## The Windows app

`control-panel/` holds a Go program, built to `RiskPanel.exe`. It serves a page only on `127.0.0.1`, opens it in an Edge or Chrome app window and passes actions to the bot's signed API. The page never sees the key. It quits when the window has been closed for about 25 seconds.

- Local protection: the right `Host`, a random session cookie, and an `X-Panel` header on every change. Content-Security-Policy blocks outside scripts.
- Settings (`RiskPanel.config.json`, mode 0600) hold the bot address and key. It's in `.gitignore`.
- Build: `control-panel/build.bat` on Windows, or `build.sh` anywhere (Go 1.22+, no outside packages).
- Pages: Overview (status, maintenance, presence, restart, shut down), Servers (VIP, ban, leave, post a message), Banned servers, Commands, Blocked users, Staff and roles, Prices, Console, Bot and cogs, Connection.

## The bot's signed API

`/owner/...` on the bot's web server (the `SERVER_PORT`), routed in `main.py` to `OwnerControl.handle`.

- Needs `OWNER_PANEL_KEY` (32+ characters). Without it the answer is 503 and nothing can be reached.
- Each request carries `X-Owner-Time`, `X-Owner-Nonce` and `X-Owner-Sig`: an HMAC-SHA256 of method, path, time, nonce and the body's SHA-256. Requests more than 30 seconds off are refused and a nonce works once. A wrong signature is answered after half a second. There is no lockout, because a lockout would let a stranger shut the owner out.
- Actions: `GET status panel commands blocked logs guild/<id>`, `POST commands blocked/add blocked/remove maintenance presence say leave reload shutdown restart`, and the staff actions `prices vip ban unban roles`. The staff actions go through the `Staff` cog as the first id in `OWNER_IDS` (or the application owner).
- Every change is added to the staff log with its actor.

## Global switches

Kept in `data/owner_control.json` and enforced by a global check (`bot.add_check`):

| Switch | Effect |
|---|---|
| Commands off | The root command and its subcommands answer "turned off right now" |
| Blocked users | Commands from that user are ignored silently (`Silent` error) |
| Maintenance | Every command answers the owner's message |

Owners (`OWNER_IDS` or the application owner) are never affected. The website's staff panel (developer role and up) can change the same three switches under Commands, Blocked users and Maintenance. Shutdown, restart, posting messages and leaving servers are only in the app.

## Not covered

The checks apply to commands. Buttons, auto-replies, XP and logging still work for blocked users and during maintenance.

Related: [Staff panel](dashboard/staff-panel.md), [Setup and env vars](Setup-and-Env-Vars.md), [Testing](Testing.md)
