---
title: Decisions
date: 2026-11-05
tags: [risk, decisions]
---

# Decisions

- **OAuth through the bot.** Render's shared IP is blocked by Discord's Cloudflare, so the bot does the code exchange. The client secret therefore lives on the bot.
- **Re-check on every request.** The bot never trusts the site's claim that someone is an admin.
- **Rollback on failure.** A save that fails halfway leaves the old settings in place.
- **Per-section availability.** A stale cog file disables one tab with a message instead of breaking the dashboard.
- **VIP is manual.** No payment code, no stored payment data. The owner grants it.
- **No plan limits on ordinary settings.** Asked for directly. VIP keeps only extras.
- **Presence intent is opt-in.** Turning on a privileged intent in code without the portal setting would stop the bot from connecting.
- **TikTok is best effort.** No official API exists. State is kept when the answer is unreadable.
- **Bot profile is per server.** Discord stores avatar, banner, bio and nickname per server for bots. Online status is global, so it is not offered.
- **Relative markdown links in these notes**, so they work in Obsidian, GitHub and VS Code.

Related: [Architecture](Architecture.md), [VIP](VIP.md), [Stream alerts](Streams.md)
