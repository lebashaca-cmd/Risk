---
title: Guide: regenerate the website command list
date: 2026-11-05
tags: [risk, guide, website]
---

# Guide: regenerate the website command list

The site's Commands page and the Terms and Privacy text come from `website/data/bot.json`.

```
cd website
python3 tools/export_bot_data.py ../discord-bot-python
```

Commit the changed `bot.json`. The exporter reads each cog, maps it to a category with its own table (so a new cog needs an entry there), and copies the terms and privacy text from `cogs/tos.py` and `cogs/privacy.py`.

Related: [Website file map](../website/file-map.md), [Add a command](add-a-command.md)
