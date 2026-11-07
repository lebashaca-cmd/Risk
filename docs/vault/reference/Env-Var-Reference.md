---
title: Environment variable reference
date: 2026-11-05
tags: [risk, reference]
---

# Environment variable reference

Every variable the code reads, found by scanning the source. See [Setup and environment variables](../Setup-and-Env-Vars.md) for what to set first.

| Variable | Read by |
|---|---|
| `AI_API_KEY` | ai_chat |
| `DASHBOARD_KEY` | dashboard |
| `DASHBOARD_URL` | dashboard |
| `DISCORD_API` | dashboard |
| `DISCORD_CLIENT_SECRET` | dashboard |
| `DISCORD_TOKEN` | main |
| `DUSK_ADMIN_TOKEN` | dusklogs, duskreset |
| `DUSK_URL` | dusklogs, duskreset |
| `GROQ_API_KEY` | ai_chat |
| `GROQ_MODEL` | ai_chat |
| `HIDE_SERVER_IDS` | main |
| `NERVE_API_KEY` | nerve |
| `SERVER_PORT` | main |
| `STREAM_PRESENCE` | main |
| `TWITCH_CLIENT_ID` | streams |
| `TWITCH_CLIENT_SECRET` | streams |
| `VIP_GUILD_IDS` | vip |
| `VIP_URL` | dashboard, vip |

Related: [Setup and environment variables](../Setup-and-Env-Vars.md), [Deploy guide](../Deploy-Guide.md)
