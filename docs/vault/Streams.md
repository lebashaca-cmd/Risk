---
title: Stream alerts
date: 2026-11-05
tags: [risk, streams]
---

# Stream alerts

`!streamalerts #channel @StreamPing` posts an embed titled "<name> is live" with a link to the stream and the live cover, then a "stopped streaming" embed with how long it lasted. The role at the end is optional.

## Sources

| Source | Setup | Cover image |
|---|---|---|
| Discord Go Live (voice screen share) | None | None (links to the voice channel) |
| Discord "Streaming" status | Presence intent in the Developer Portal and `STREAM_PRESENCE=1` | Twitch preview if the link is Twitch |
| Twitch channels (`!twitchadd name @Role`) | Free Twitch app keys, see [Setup](Setup-and-Env-Vars.md). Checked every 60 seconds | Live preview |
| TikTok accounts (`!tiktokadd @name @Role`) | None. Unofficial, so it may break or be blocked. Checked every 90 seconds, 25 accounts per server | Room cover if TikTok sends one |

## Commands

- Setup: `!streamalerts`, `!streamrole`, `!twitchadd`, `!twitchremove`, `!twitchlist`, `!tiktokadd`, `!tiktokremove`, `!tiktoklist`
- Info: `!streaming`, `!streamstats @user`, `!streamers`
- Tests: `!streamtest` (sample alert), `!twitchtest <channel>`, `!tiktoktest @name`

A role given to `!twitchadd` or `!tiktokadd` beats the server-wide role for that streamer.

## Why not "a free API for everything"

Discord events and the Twitch API are official and free. TikTok has no public live API, so Risk reads the same page data the website uses. Run `!tiktoktest` while someone is live to confirm it works from your host. If TikTok answers in a form Risk cannot read, Risk keeps the previous state instead of guessing.

Related: [Troubleshooting](Troubleshooting.md), [Message templates](Message-Templates.md), [Setup and environment variables](Setup-and-Env-Vars.md)
