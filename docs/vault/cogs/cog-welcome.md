---
title: welcome.py
date: 2026-11-05
tags: [risk, cog]
---

# welcome.py

Cog file `cogs/welcome.py` (83 lines).

- File: `discord-bot-python/cogs/welcome.py` (83 lines)
- Classes: `Welcome`
- Data files: `data/welcome.json`
- Environment variables: none
- Background loops: none
- Event listeners: `on_member_join`, `on_member_remove`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `welcome` |  | Greets new members in a channel. Write New_user where the name goes. Put {embed} at the start and the end to send it as an embed. Usage: !welcome #channel {embed} Welcome New_user to Risk {embed} | Manage Server |
| `welcomeoff` |  | Turns welcome messages off. Usage: !welcomeoff | Manage Server |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
