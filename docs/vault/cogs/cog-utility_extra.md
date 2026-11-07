---
title: utility_extra.py
date: 2026-11-05
tags: [risk, cog]
---

# utility_extra.py

Cog file `cogs/utility_extra.py` (239 lines).

- File: `discord-bot-python/cogs/utility_extra.py` (239 lines)
- Classes: `UtilityExtra`
- Data files: `data/todo.json`
- Environment variables: none
- Background loops: none
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `announce` |  | Sends an announcement to a channel. Usage: !announce #news Server maintenance tonight | Manage Server |
| `base64_command` | `b64` | Encodes or decodes Base64 text. Usage: !base64 encode hello |  |
| `binary` |  | Converts text to binary, or binary back to text. Usage: !binary hi |  |
| `embed_command` |  | Posts an embed in a channel. Separate the title and text with a pipe. Usage: !embed #news Title / The text | has_permissions, guild_only |
| `hash_command` |  | Hashes text with md5, sha1, sha256 or sha512. Usage: !hash sha256 hello |  |
| `morse` |  | Converts text to Morse code, or Morse code back to text. Usage: !morse hello world |  |
| `password` | `pass` | Sends you a random password in a direct message. Usage: !password 20 |  |
| `rot13` |  | Applies the ROT13 letter swap. Usage: !rot13 hello |  |
| `timestamp` | `ts` | Makes a Discord timestamp from a UTC date. Usage: !timestamp 2026-12-25 18:00 |  |
| `todo` |  | Keeps a personal to-do list. Actions: add, list, done, remove, clear. Usage: !todo add buy milk |  |
| `wiki` | `wikipedia` | Shows the summary of a Wikipedia article. Usage: !wiki Alan Turing |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
