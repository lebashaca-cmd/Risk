---
title: Setup and environment variables
date: 2026-11-05
tags: [risk, config]
---

# Setup and environment variables

## Bot host (bot-hosting.cloud)

| Variable | Needed for | Notes |
|---|---|---|
| `TOKEN` / the bot token | Everything | As in the existing `.env` |
| `DASHBOARD_KEY` | Dashboard | At least 16 characters. Must match Render |
| `DASHBOARD_URL` | Dashboard sign-in | The site address, for OAuth redirects |
| `DISCORD_CLIENT_SECRET` | Dashboard sign-in | The OAuth2 client secret from the Developer Portal. Lives on the bot, not on Render |
| `NERVE_API_KEY` | `!tiktok`, `!github`, `!spotify`, `!youtube` | See [Lookups](Lookups.md) |
| `VIP_GUILD_IDS` | VIP | Comma-separated server ids that always have VIP |
| `VIP_URL` | VIP | Optional https link shown as "Get VIP" |
| `STREAM_PRESENCE` | Discord "Streaming" status alerts | Set to `1` only after enabling the Presence intent in the Developer Portal |
| `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` | Twitch alerts | Free app at dev.twitch.tv/console |
| `SERVER_PORT` | Status server | Defaults to 25239 |

## Render (the website)

| Variable | Notes |
|---|---|
| `DASHBOARD_KEY` | Same value as the bot |
| `DASHBOARD_HOST` | For example `dashboard.yourdomain.com`. Turns on `dashboard.<domain>/<server id>` URLs |
| `CLIENT_ID` | The bot's application id |
| `BOT_STATUS_URL` | Where the bot's status server answers |
| `TRUST_PROXY` | Set so the site trusts Render's forwarded headers |
| `BOT_API_URL`, `SITE_URL` | Optional overrides |
| `DISCORD_CLIENT_SECRET` | Fallback only, if the bot can't do the exchange |

## Developer Portal checklist

- Add the dashboard callback as an OAuth2 redirect.
- Server Members intent: already on.
- Presence intent: only if you want the Discord "Streaming" status alerts.

Related: [Deploy guide](Deploy-Guide.md), [Architecture](Architecture.md), [VIP](VIP.md), [Stream alerts](Streams.md)
