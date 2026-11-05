---
title: Guide: free Twitch app for stream alerts
date: 2026-11-05
tags: [risk, guide, streams]
---

# Guide: free Twitch app for stream alerts

1. Sign in at dev.twitch.tv/console with a Twitch account (turn on two-factor authentication if asked).
2. Register an application: any name, OAuth redirect `http://localhost`, category Application Integration.
3. Copy the **Client ID** and create a **Client Secret**.
4. On the bot host set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET`, restart.
5. In Discord: `!streamalerts #streams @StreamPing`, then `!twitchadd <channel>`, then `!twitchtest <channel>`.

Risk uses the "client credentials" token, which needs no user login, and asks `GET /helix/streams` for up to 100 channels at once every 60 seconds.

Related: [Stream alerts](../Streams.md), [Setup and environment variables](../Setup-and-Env-Vars.md)
