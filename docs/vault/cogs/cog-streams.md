---
title: streams.py
date: 2026-11-05
tags: [risk, cog]
---

# streams.py

Stream alerts: Risk says when someone starts and stops streaming.

Sources (all free):
- Discord Go Live (screen share in a voice channel). Works with no extra setup.
- Discord "Streaming" status (a linked Twitch or YouTube account). Needs the Presence intent: turn it on in the
  Developer Portal (Bot, Privileged Gateway Intents) and set STREAM_PRESENCE=1 on the bot host.
- Twitch channels by name (`!twitchadd`). Needs a free Twitch app: set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET.
- TikTok accounts by name (`!tiktokadd`). TikTok has no public API, so this reads the same page data the website uses.
  It needs no keys but is unofficial: TikTok can change it or block a host, and `!tiktoktest` shows what Risk sees.

- File: `discord-bot-python/cogs/streams.py` (598 lines)
- Classes: `Streams`
- Data files: `data/streams.json`
- Environment variables: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`
- Background loops: `twitch_loop` (every(seconds=TWITCH_POLL)), `tiktok_loop` (every(seconds=TIKTOK_POLL))
- Event listeners: `on_voice_state_update`, `on_presence_update`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `streamalerts` | `streamalert` | Sets the channel for stream alerts, and optionally a role to ping. Usage: !streamalerts #streams @StreamPing (or !streamalerts off) | guild_only, has_permissions |
| `streamalerts_off` |  | Turns stream alerts off. Usage: !streamalerts off | has_permissions |
| `streamers` | `streamboard` | Ranks members by total time streamed. Usage: !streamers | guild_only |
| `streaming` | `live`, `whoslive` | Shows who is streaming right now. Usage: !streaming | guild_only |
| `streamrole` |  | Picks a role to ping when someone starts streaming (leave empty to stop pinging). Usage: !streamrole @Streams | Manage Server |
| `streamstats` | `laststream` | Shows a member's stream count, total time and last stream. Usage: !streamstats @user | guild_only |
| `streamtest` |  | Posts a sample 'is live' and 'stopped' alert in the alert channel. Usage: !streamtest | Manage Server |
| `tiktokadd` |  | Watches a TikTok account and posts when it goes live and ends. Usage: !tiktokadd @name @StreamPing | Manage Server |
| `tiktoklist` |  | Lists the TikTok accounts this server watches. Usage: !tiktoklist | guild_only |
| `tiktokremove` |  | Stops watching a TikTok account. Usage: !tiktokremove @name | Manage Server |
| `tiktoktest` |  | Checks one TikTok account right now and says what Risk sees. Usage: !tiktoktest @name | Manage Server |
| `twitchadd` |  | Watches a Twitch channel and posts when it goes live and offline. Usage: !twitchadd shroud @StreamPing | Manage Server |
| `twitchlist` |  | Lists the Twitch channels this server watches. Usage: !twitchlist | guild_only |
| `twitchremove` |  | Stops watching a Twitch channel. Usage: !twitchremove shroud | Manage Server |
| `twitchtest` |  | Checks one Twitch channel right now and shows what the alert looks like. Usage: !twitchtest shroud | Manage Server |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
