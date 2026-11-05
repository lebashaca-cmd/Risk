---
title: Intents and bot permissions
date: 2026-11-05
tags: [risk, reference]
---

# Intents and bot permissions

## Gateway intents

| Intent | State | Why |
|---|---|---|
| Message content | On | Prefix commands, auto-replies, auto-mod |
| Server members | On | Welcome, auto role, member lists, levels |
| Voice states | Default | Go Live detection |
| Presences | Off unless `STREAM_PRESENCE=1` | Discord "Streaming" status alerts. Privileged: needs the portal switch too |

## Useful bot permissions

Send Messages, Embed Links, Attach Files, Add Reactions, Manage Messages (auto-mod, sticky), Manage Roles (rewards, auto role, give role), Manage Nicknames or Change Nickname (bot profile), Kick, Ban, Moderate Members (moderation), Manage Channels (tickets, lockdown), View Audit Log (some logs), Mention Everyone (to ping roles that are not mentionable).

Related: [Developer Portal setup](../guides/developer-portal-setup.md), [Permissions index](Permissions-Index.md)
