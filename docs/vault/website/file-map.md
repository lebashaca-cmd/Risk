---
title: Website file map
date: 2026-11-05
tags: [risk, website]
---

# Website file map

| Path | What it is |
|---|---|
| `website/server.py` | aiohttp app: static files, public API, security headers, SPA fallback, dashboard host handling |
| `website/dashboard.py` | Dashboard backend: OAuth, sessions, proxy to the bot |
| `website/render.yaml` | Render service definition |
| `website/requirements.txt`, `package.json`, `tsconfig.json` | Dependencies and TypeScript config |
| `website/src/*.ts` | Frontend source |
| `website/web/index.html` | The single page, nav, footer |
| `website/web/assets/css/site.css` | All styles |
| `website/web/assets/js/*.js` | Compiled output, committed |
| `website/data/bot.json` | Command list, terms and privacy text exported from the bot |
| `website/tools/export_bot_data.py` | Regenerates `bot.json` from the cog files |
| `website/README.md` | Setup notes |

## Public pages

Home (with server cards that scroll right to left and the status panel), Commands (searchable, by category), Terms, Privacy, Dashboard.

Related: [Dashboard frontend structure](../dashboard/frontend-structure.md), [Website server](server.md), [Regenerating the command list](../guides/regenerate-command-list.md)
