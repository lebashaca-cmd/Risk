---
title: vip_plus.py
date: 2026-11-07
tags: [risk, cog, vip]
---

# vip_plus.py

The extra VIP commands. Every command calls `VIP.need(ctx, group)` first, so a server on a lower [plan](../VIP.md) is told which plan it needs.

- File: `discord-bot-python/cogs/vip_plus.py`
- Class: `VIPPlus`
- Data file: `data/vip_plus.json` (custom commands, auto reactions, welcome DMs, auto delete rules and queue, saved lock settings, member counters, messages of the day)
- Background loops: `reaper` (every 30 seconds, deletes due messages) and `counters` (every 10 minutes)
- Event listeners: `on_message` (custom commands, auto reactions, auto delete queue) and `on_member_join` (welcome DM)

## Commands by plan

| Plan | Commands |
|---|---|
| Basic | `vipcolor`, `vippoll`, `vipsay`, `vipannounce`, `viprolecolor`, `servercard`, `topmessages`, `userreport`, `rolereport` |
| White | `customcmd`, `autoreact`, `welcomedm`, `embededit`, `stafflist` |
| Supreme | `autodelete`, `slowmodeall`, `lockall`, `unlockall`, `serverbackup`, `membercounter`, `permaudit` |
| Lifetime | `founder`, `motd` (and every command above, since Lifetime has every group) |

See [VIP commands](../commands/cmd-vip.md) for each command's usage and the permission it needs.

Related: [Cogs index](INDEX.md), [VIP](../VIP.md), [vip.py](cog-vip.md)
