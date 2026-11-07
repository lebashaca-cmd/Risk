---
title: Guide: Discord Developer Portal setup
date: 2026-11-05
tags: [risk, guide]
---

# Guide: Discord Developer Portal setup

1. Open the application at discord.com/developers, **Bot** page.
2. **Privileged Gateway Intents**: keep Server Members on. Turn on Presence only if you want alerts for the Discord "Streaming" status, then set `STREAM_PRESENCE=1` on the bot host.
3. **OAuth2** page: copy the Client Secret into `DISCORD_CLIENT_SECRET` on the bot host.
4. **OAuth2, Redirects**: add the dashboard callback, `https://<your site>/api/auth/callback` (and the same on the dashboard subdomain if you use one).
5. **Installation**: the bot should be invited with permissions for the features you use (Manage Roles, Manage Nicknames for the profile, Send Messages, Embed Links, Manage Messages for auto-mod).

Related: [Setup and environment variables](../Setup-and-Env-Vars.md), [Sign-in flow](../dashboard/sign-in-flow.md)
