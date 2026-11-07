---
title: Guide: backup and restore
date: 2026-11-05
tags: [risk, guide, ops]
---

# Guide: backup and restore

Everything a server has configured or earned lives in `discord-bot-python/data/*.json` plus `.env`.

**Back up**: copy the `data/` folder from the host regularly, especially before uploading a new version. See [Data files](../reference/Data-Files.md) for what each file holds.

**Restore**: stop the bot, put the files back into `data/`, start the bot.

**Reset one feature**: delete its single file (for example `data/streams.json` resets stream alerts for every server). Restart so the bot reloads.

Related: [Data files](../reference/Data-Files.md), [Upload to the host](upload-to-bot-host.md)
