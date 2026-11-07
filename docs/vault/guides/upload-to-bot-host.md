---
title: Guide: upload the bot to the host
date: 2026-11-05
tags: [risk, guide, deploy]
---

# Guide: upload the bot to bot-hosting.cloud

1. Download or pull the latest `discord-bot-python` folder.
2. In the host's file manager upload the **whole folder contents**, replacing files. Do not skip new files such as `cogs/vip.py` and `cogs/streams.py`.
3. Do not overwrite or delete the `data/` folder or `.env`: that is your saved data and secrets.
4. Add or change environment variables in `.env`: see [Environment variable reference](../reference/Env-Var-Reference.md).
5. Restart the bot.
6. Run `!cogstatus` in Discord. Anything listed as not loaded shows its error.
7. Check the startup log for lines starting `Failed to load extension`.

Related: [Deploy guide](../Deploy-Guide.md), [Troubleshooting](../Troubleshooting.md)
