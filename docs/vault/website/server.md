---
title: Website server
date: 2026-11-05
tags: [risk, website]
---

# Website server

`website/server.py` is a small aiohttp app.

- **Static**: serves `web/` with long cache for assets and short for the page. Unknown paths fall back to the single-page app.
- **Public data**: `/api/config`, `/api/status` (proxies the bot's status endpoint), `/api/commands`, `/api/tos`, `/api/privacy`, `/healthz` for Render.
- **Security headers**: strict Content Security Policy (`connect-src 'self'`, no `unsafe-eval`, images allowed from `self`, `data:` and Discord's CDN), no framing, no sniffing.
- **Dashboard host**: when `DASHBOARD_HOST` is set, requests to that host serve the app at `/<server id>`; `/dashboard...` on the main host redirects to the subdomain.
- **Body limit**: 8 MB, enough for profile pictures. The settings routes enforce their own smaller limits.

Related: [Website file map](file-map.md), [Deploy guide](../Deploy-Guide.md), [Security model](../reference/Security-Model.md)
