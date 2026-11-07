---
title: Runbooks
date: 2026-11-05
tags: [risk, reference, ops]
---

# Runbooks

## The bot is up but the dashboard says the bot is offline
1. Open the bot's status URL in a browser. No answer means the status server is down: restart the bot.
2. Check `BOT_STATUS_URL` on Render.
3. Check `DASHBOARD_KEY` is identical on both hosts.

## Sign-in fails
1. Is `DISCORD_CLIENT_SECRET` set on the bot host?
2. Is the redirect URL added in the Developer Portal, exactly?
3. Look at the bot log for `[dashboard]` lines.

## A save fails with "unavailable"
Upload the whole bot folder, restart, run `!cogstatus`.

## Alerts stopped
1. `!streamalerts` shows the channel. Is the bot allowed to send and embed there?
2. Twitch: `!twitchtest <channel>`. TikTok: `!tiktoktest @name`.
3. The bot log shows `[streams]` lines for failed checks.

## Role pings do nothing
Make the role mentionable or give the bot Mention Everyone.

## Roll back a bad release
Upload the previous folder, restart. Data files are compatible because new keys use defaults.

Related: [Troubleshooting](../Troubleshooting.md), [Upload to the host](../guides/upload-to-bot-host.md)
