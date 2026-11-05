---
title: Data files
date: 2026-11-05
tags: [risk, reference]
---

# Data files

The bot keeps JSON files in `discord-bot-python/data/` (gitignored, written atomically by `JsonStore`). Back this folder up: it is every server's settings, economy balances, levels and more.

| File | Used by |
|---|---|
| `afk.json` | `utility_tools` |
| `automod.json` | `automod` |
| `community.json` | `community` |
| `community_extra.json` | `community_extra` |
| `dashboard.json` | `dashboard` |
| `economy.json` | `economy` |
| `giveaways.json` | `giveaway` |
| `level_settings.json` | `levels` |
| `levels.json` | `levels` |
| `logtools.json` | `log_tools` |
| `lottery.json` | `economy_more` |
| `reminders.json` | `utility_tools` |
| `streams.json` | `streams` |
| `suggestions.json` | `community` |
| `tags.json` | `community` |
| `tempbans.json` | `moderation_more` |
| `todo.json` | `utility_extra` |
| `vip.json` | `vip` |
| `warnings.json` | `moderation_tools` |
| `welcome.json` | `welcome` |

Some older cogs write their own files (for example server logs use `logs_config.json`). Deleting a file resets that feature for every server.

Related: [Architecture](../Architecture.md), [Troubleshooting](../Troubleshooting.md)
