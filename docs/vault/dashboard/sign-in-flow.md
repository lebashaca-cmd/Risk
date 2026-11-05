---
title: Dashboard sign-in flow
date: 2026-11-05
tags: [risk, dashboard, oauth]
---

# Dashboard sign-in flow

1. The user opens the dashboard and clicks sign in. The site sends them to Discord with a random `state` stored in the `risk_oauth` cookie.
2. Discord sends them back to `/api/auth/callback?code=...&state=...`. The site checks the state.
3. The site passes the code to the bot (`POST /dash/oauth`). The **bot** exchanges it with Discord using `DISCORD_CLIENT_SECRET`, reads the user and their servers, then revokes the token.
4. The site makes a session (kept in memory, cookie `risk_session`) holding the user and the servers they manage.
5. `/api/auth/me` lists those servers where Risk is present (the bot answers `/dash/present`, cached for 20 seconds).

## Why the bot does the exchange

Discord's Cloudflare firewall answers Render's shared IP with an HTML 429 page, so the exchange from Render fails with "Discord didn't complete the sign-in". The bot host's address is not blocked. The site can fall back to doing it itself if it has the secret.

## Failure messages

The site turns specific problems into messages: sign-in blocked, bot offline, secret missing, Discord rejected the code. See [Troubleshooting](../Troubleshooting.md).

Related: [API reference](api-reference.md), [Architecture](../Architecture.md), [Setup and environment variables](../Setup-and-Env-Vars.md)
